# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import email.mime.text
import logging
import monascastatsd as mstatsd
import requests
import smtplib
import sys
import time

from monasca_notification.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class NotificationProcessor(BaseProcessor):

    def __init__(self, notification_queue, sent_notification_queue,
                 finished_queue, email_config, webhook_config):
        self.notification_queue = notification_queue
        self.sent_notification_queue = sent_notification_queue
        self.finished_queue = finished_queue

        self.email_config = email_config

        self.webhook_config = {'timeout': 5}
        self.webhook_config.update(webhook_config)

        self.smtp = None
        self._smtp_connect()

        # Types as key, method used to process that type as value
        self.notification_types = {'email': self._send_email,
                                   'webhook': self._post_webhook}

        self.monascastatsd = mstatsd.Client(name='monasca',
                                            dimensions=BaseProcessor.dimensions)

    def _create_msg(self, hostname, notification):
        """Create two kind of messages:
        1. Notifications that include metrics with a hostname as a dimension. There may be more than one hostname.
           We will only report the hostname if there is only one.
        2. Notifications that do not include metrics and therefore no hostname. Example: API initiated changes.
           * A third notification type which include metrics but do not include a hostname will
           be treated as type #2.
        """
        if len(hostname) == 1:  # Type 1
            msg = email.mime.text.MIMEText("On host \"%s\" %s\n\nAlarm \"%s\" transitioned to the %s state at %s UTC"
                                           % (hostname[0],
                                               notification.message.lower(),
                                               notification.alarm_name,
                                               notification.state,
                                               time.asctime(time.gmtime(notification.alarm_timestamp))) +
                                           "\nalarm_id: %s" % notification.alarm_id)

            msg['Subject'] = "%s \"%s\" for Host: %s" % (notification.state, notification.alarm_name, hostname[0])

        else:  # Type 2
            msg = email.mime.text.MIMEText("%s\n\nAlarm \"%s\" transitioned to the %s state at %s UTC\nAlarm_id: %s"
                                           % (notification.message,
                                              notification.alarm_name,
                                              notification.state,
                                              time.asctime(time.gmtime(notification.alarm_timestamp)),
                                              notification.alarm_id))
            msg['Subject'] = "%s \"%s\" " % (notification.state, notification.alarm_name)

        msg['From'] = self.email_config['from_addr']
        msg['To'] = notification.address

        return msg

    def _send_email(self, notification):
        """Send the notification via email
             Returns the notification upon success, None upon failure
        """

        # Get the "hostname" from the notification metrics if there is one
        hostname = []

        for metric in notification.metrics:
            for dimension in metric['dimensions']:
                if 'hostname' in dimension:
                    if not metric['dimensions']['%s' % dimension] in hostname[:]:
                        hostname.append(metric['dimensions']['%s' % dimension])

        # Generate the message
        msg = self._create_msg(hostname, notification)

        # email the notification
        try:
            self.smtp.sendmail(self.email_config['from_addr'], notification.address, msg.as_string())
            log.debug('Sent email to %s, notification %s' % (notification.address, notification.to_json()))
        except smtplib.SMTPServerDisconnected:
            log.debug('SMTP server disconnected. Will reconnect and retry message.')
            self._smtp_connect()
            try:
                self.smtp.sendmail(self.email_config['from_addr'], notification.address, msg.as_string())
                log.debug('Sent email to %s, notification %s' % (notification.address, notification.to_json()))
            except smtplib.SMTPException as e:
                log.error("Error sending Email Notification:%s\nError:%s" % (notification.to_json(), e))
        except smtplib.SMTPException as e:
            log.error("Error sending Email Notification:%s\nError:%s" % (notification.to_json(), e))
        else:
            return notification

    def _smtp_connect(self):
        """Connect to the smtp server
        """
        log.info('Connecting to Email Server %s' % self.email_config['server'])
        smtp = smtplib.SMTP(
            self.email_config['server'], self.email_config['port'], timeout=self.email_config['timeout'])

        if self.email_config['user'] is not None:
            smtp.login(self.email_config['user'], self.email_config['password'])

        self.smtp = smtp

    def _post_webhook(self, notification):
        """Send the notification via webhook
            Posts on the given url
        """

        log.info(
            "Notifying alarm %(alarm_id)s to %(current)s with action %(action)s" %
            ({'alarm_id': notification.alarm_name,
              'current': notification.state,
              'action': notification.address}))
        body = '{"alarm_id": "%s"}' % notification.alarm_name
        headers = {'content-type': 'application/json'}

        url = notification.address

        try:
            # Posting on the given URL
            result = requests.post(url=url,
                                   data=body,
                                   headers=headers,
                                   timeout=self.webhook_config['timeout'])
            if result.status_code in range(200, 300):
                log.info("Notification successfully posted.")
                return notification
            else:
                log.error("Received an HTTP code %s when trying to post on URL %s." % (result.status_code, url))
        except:
            log.error("Error trying to post on URL %s: %s." % (url, sys.exc_info()[0]))

    def run(self):
        """Send the notifications
             For each notification in a message it is sent according to its type.
             If all notifications fail the alarm partition/offset are added to the the finished queue
        """
        counters = {'email': self.monascastatsd.get_counter(name='sent_smtp_count'),
                    'webhook': self.monascastatsd.get_counter(name='sent_webhook_count')}
        timers = {'email': self.monascastatsd.get_timer(),
                  'webhook': self.monascastatsd.get_timer()}
        invalid_type_count = self.monascastatsd.get_counter(name='invalid_type_count')
        sent_failed_count = self.monascastatsd.get_counter(name='sent_failed_count')

        while True:
            notifications = self.notification_queue.get()
            sent_notifications = []
            for notification in notifications:
                if notification.type not in self.notification_types:
                    log.warn('Notification type %s is not a valid type' % notification.type)
                    invalid_type_count += 1
                    continue
                else:
                    timer_name = notification.type + '_time'
                    with timers[notification.type].time(timer_name):
                        sent = self.notification_types[notification.type](notification)

                    if sent is None:
                        sent_failed_count += 1
                    else:
                        sent.notification_timestamp = time.time()
                        sent_notifications.append(sent)
                        counters[notification.type] += 1

            if len(sent_notifications) == 0:  # All notifications failed
                self._add_to_queue(
                    self.finished_queue, 'finished', (notifications[0].src_partition, notifications[0].src_offset))
            else:
                self._add_to_queue(self.sent_notification_queue, 'sent_notification', sent_notifications)
