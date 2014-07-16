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
import multiprocessing
import smtplib
import statsd
import time

from monasca_notification.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class NotificationProcessor(BaseProcessor):

    def __init__(self, notification_queue, sent_notification_queue, finished_queue, email_config):
        self.notification_queue = notification_queue
        self.sent_notification_queue = sent_notification_queue
        self.finished_queue = finished_queue

        self.email_config = email_config
        self.smtp = None
        self._smtp_connect()

        # Types as key, method used to process that type as value
        self.notification_types = {'email': self._send_email}

    def _send_email(self, notification):
        """Send the notification via email
             Returns the notification upon success, None upon failure
        """
        msg = email.mime.text.MIMEText("%s\nAlarm %s transitioned to the %s state at %s UTC\nFull Data:\n%s"
                                       % (notification.message,
                                          notification.alarm_name,
                                          notification.state,
                                          time.asctime(time.gmtime(notification.alarm_timestamp)),
                                          notification.to_json()))
        msg['Subject'] = '%s: %s' % (notification.state, notification.alarm_name)
        msg['From'] = self.email_config['from_addr']
        msg['To'] = notification.address

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

    def run(self):
        """Send the notifications
             For each notification in a message it is sent according to its type.
             If all notifications fail the alarm partition/offset are added to the the finished queue
        """
        pname = multiprocessing.current_process().name
        invalid_count = statsd.Counter('NotificationsInvalidType-%s' % pname)
        failed_count = statsd.Counter('NotificationsSentFailed-%s' % pname)

        smtp_sent_count = statsd.Counter('NotificationsSentSMTP-%s' % pname)
        counters = {'email': smtp_sent_count}

        smtp_time = statsd.Timer('SMTPTime-%s' % pname)
        timers = {'email': smtp_time}

        while True:
            notifications = self.notification_queue.get()
            sent_notifications = []
            for notification in notifications:
                if notification.type not in self.notification_types:
                    log.warn('Notification type %s is not a valid type' % notification.type)
                    invalid_count += 1
                    continue
                else:
                    with timers[notification.type].time():
                        sent = self.notification_types[notification.type](notification)
                    if sent is None:
                        failed_count += 1
                    else:
                        sent.notification_timestamp = time.time()
                        sent_notifications.append(sent)
                        counters[notification.type] += 1

            if len(sent_notifications) == 0:  # All notifications failed
                self._add_to_queue(
                    self.finished_queue, 'finished', (notifications[0].src_partition, notifications[0].src_offset))
            else:
                self._add_to_queue(self.sent_notification_queue, 'sent_notification', sent_notifications)
