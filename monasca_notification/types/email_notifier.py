# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
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
import smtplib
import time

from abstract_notifier import AbstractNotifier


class EmailNotifier(AbstractNotifier):
    def __init__(self, log):
        self._log = log
        self._smtp = None

    def config(self, config):
        self._config = config
        self._smtp_connect()

    @property
    def type(self):
        return "email"

    @property
    def statsd_name(self):
        return "sent_smtp_count"

    def send_notification(self, notification):
        """Send the notification via email
             Returns the True upon success, False upon failure
        """

        # Get the "hostname" from the notification metrics if there is one
        hostname = []

        for metric in notification.metrics:
            for dimension in metric['dimensions']:
                if 'hostname' in dimension:
                    if not metric['dimensions'][dimension] in hostname:
                        hostname.append(metric['dimensions'][dimension])

        # Generate the message
        msg = self._create_msg(hostname, notification)

        try:
            self._sendmail(notification, msg)
            return True
        except smtplib.SMTPServerDisconnected:
            self._log.warn('SMTP server disconnected. '
                           'Will reconnect and retry message.')
            self._smtp_connect()
        except smtplib.SMTPException:
            self._email_error(notification)
            return False

        try:
            self._sendmail(notification, msg)
            return True
        except smtplib.SMTPException:
            self._email_error(notification)
            return False

    def _sendmail(self, notification, msg):
        self._smtp.sendmail(self._config['from_addr'], notification.address, msg.as_string())
        self._log.debug("Sent email to {}, notification {}".format(notification.address, notification.to_json()))

    def _email_error(self, notification):
        self._log.exception("Error sending Email Notification")
        self._log.error("Failed email: {}".format(notification.to_json()))

    def _smtp_connect(self):
        """Connect to the smtp server
        """
        self._log.info("Connecting to Email Server {}".format(self._config['server']))

        try:
            smtp = smtplib.SMTP(self._config['server'],
                                self._config['port'],
                                timeout=self._config['timeout'])

            if self._config['user'] is not None:
                smtp.login(self._config['user'], self.config['password'])

            self._smtp = smtp
        except Exception:
            self._log.exception("Unable to connect to email server.")

    def _create_msg(self, hostname, notification):
        """Create two kind of messages:
        1. Notifications that include metrics with a hostname as a dimension. There may be more than one hostname.
           We will only report the hostname if there is only one.
        2. Notifications that do not include metrics and therefore no hostname. Example: API initiated changes.
           * A third notification type which include metrics but do not include a hostname will
           be treated as type #2.
        """
        timestamp = time.asctime(time.gmtime(notification.alarm_timestamp))

        if len(hostname) == 1:  # Type 1
            text = '''On host "{}" {}

                      Alarm "{}" transitioned to the {} state at {} UTC
                      alarm_id: {}'''.format(hostname[0],
                                             notification.message.lower(),
                                             notification.alarm_name,
                                             notification.state,
                                             timestamp,
                                             notification.alarm_id)

            msg = email.mime.text.MIMEText(text)

            msg['Subject'] = '{} "{}" for Host: {}'.format(notification.state,
                                                           notification.alarm_name,
                                                           hostname[0])

        else:  # Type 2
            text = '''{}

                      Alarm "{}" transitioned to the {} state at {} UTC
                      Alarm_id: {}'''.format(notification.message,
                                             notification.alarm_name,
                                             notification.state,
                                             timestamp,
                                             notification.alarm_id)

            msg = email.mime.text.MIMEText(text)
            msg['Subject'] = '{} "{}" '.format(notification.state, notification.alarm_name)

        msg['From'] = self._config['from_addr']
        msg['To'] = notification.address

        return msg
