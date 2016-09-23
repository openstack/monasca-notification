# (C) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
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

from monasca_notification.plugins import abstract_notifier

EMAIL_SINGLE_HOST_BASE = u'''On host "{hostname}" for target "{target_host}" {message}

Alarm "{alarm_name}" transitioned to the {state} state at {timestamp} UTC
alarm_id: {alarm_id}
Lifecycle state: {lifecycle_state}
Link: {link}

With dimensions:
{metric_dimensions}'''

EMAIL_MULTIPLE_HOST_BASE = u'''On host "{hostname}" {message}

Alarm "{alarm_name}" transitioned to the {state} state at {timestamp} UTC
alarm_id: {alarm_id}
Lifecycle state: {lifecycle_state}
Link: {link}

With dimensions:
{metric_dimensions}'''

EMAIL_NO_HOST_BASE = u'''On multiple hosts {message}

Alarm "{alarm_name}" transitioned to the {state} state at {timestamp} UTC
Alarm_id: {alarm_id}
Lifecycle state: {lifecycle_state}
Link: {link}

With dimensions
{metric_dimensions}'''


class EmailNotifier(abstract_notifier.AbstractNotifier):
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
        targethost = []

        for metric in notification.metrics:
            dimap = metric['dimensions']

            if 'hostname' in dimap and not dimap['hostname'] in hostname:
                hostname.append(dimap['hostname'])
            if 'target_host' in dimap and not dimap['target_host'] in targethost:
                targethost.append(dimap['target_host'])

        # Generate the message
        msg = self._create_msg(hostname, notification, targethost)

        if not self._smtp and not self._smtp_connect():
            return False

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
        self._smtp.sendmail(self._config['from_addr'],
                            notification.address,
                            msg.as_string())
        self._log.debug("Sent email to {}, notification {}".format(notification.address,
                                                                   notification.to_json()))

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

            if self._config['user']:
                smtp.login(self._config['user'], self._config['password'])

            self._smtp = smtp
            return True
        except Exception:
            self._log.exception("Unable to connect to email server.")
            return False

    def _create_msg(self, hostname, notification, targethost=None):
        """Create two kind of messages:
        1. Notifications that include metrics with a hostname as a dimension. There may be more than one hostname.
           We will only report the hostname if there is only one.
        2. Notifications that do not include metrics and therefore no hostname. Example: API initiated changes.
           * A third notification type which include metrics but do not include a hostname will
           be treated as type #2.
        """
        timestamp = time.asctime(time.gmtime(notification.alarm_timestamp))

        dimensions = _format_dimensions(notification)

        if len(hostname) == 1:  # Type 1
            if targethost:
                text = EMAIL_SINGLE_HOST_BASE.format(
                    hostname=hostname[0],
                    target_host=targethost[0],
                    message=notification.message.lower(),
                    alarm_name=notification.alarm_name,
                    state=notification.state,
                    timestamp=timestamp,
                    alarm_id=notification.alarm_id,
                    metric_dimensions=dimensions,
                    link=notification.link,
                    lifecycle_state=notification.lifecycle_state
                ).encode("utf-8")

                msg = email.mime.text.MIMEText(text)

                msg['Subject'] = (u'{} {} "{}" for Host: {} Target: {}'
                                  .format(notification.state,
                                          notification.severity,
                                          notification.alarm_name,
                                          hostname[0],
                                          targethost[0]).encode("utf-8"))

            else:
                text = EMAIL_MULTIPLE_HOST_BASE.format(
                    hostname=hostname[0],
                    message=notification.message.lower(),
                    alarm_name=notification.alarm_name,
                    state=notification.state,
                    timestamp=timestamp,
                    alarm_id=notification.alarm_id,
                    metric_dimensions=dimensions,
                    link=notification.link,
                    lifecycle_state=notification.lifecycle_state
                ).encode("utf-8")

                msg = email.mime.text.MIMEText(text)

                msg['Subject'] = u'{} {} "{}" for Host: {}'.format(notification.state,
                                                                   notification.severity,
                                                                   notification.alarm_name,
                                                                   hostname[0]).encode("utf-8")
        else:  # Type 2
            text = EMAIL_NO_HOST_BASE.format(
                message=notification.message.lower(),
                alarm_name=notification.alarm_name,
                state=notification.state,
                timestamp=timestamp,
                alarm_id=notification.alarm_id,
                metric_dimensions=dimensions,
                link=notification.link,
                lifecycle_state=notification.lifecycle_state
            ).encode("utf-8")

            msg = email.mime.text.MIMEText(text)
            msg['Subject'] = u'{} {} "{}" '.format(notification.state,
                                                   notification.severity,
                                                   notification.alarm_name).encode("utf-8")

        msg['From'] = self._config['from_addr']
        msg['To'] = notification.address

        return msg


def _format_dimensions(notification):
    dimension_sets = []
    for metric in notification.metrics:
        dimension_sets.append(metric['dimensions'])

    dim_set_strings = []
    for dimension_set in dimension_sets:
        key_value_pairs = []
        for key, value in dimension_set.items():
            key_value_pairs.append(u'    {}: {}'.format(key, value))

        set_string = u'  {\n' + u',\n'.join(key_value_pairs) + u'\n  }'
        dim_set_strings.append(set_string)

    dimensions = u'[\n' + u',\n'.join(dim_set_strings) + u' \n]'

    return dimensions
