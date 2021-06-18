# (C) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
# Copyright 2017 Fujitsu LIMITED
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

import email.header
import email.mime.text
import email.utils
import smtplib
import time

from debtcollector import removals
from oslo_config import cfg

from monasca_notification.plugins import abstract_notifier

CONF = cfg.CONF

EMAIL_SINGLE_HOST_BASE = u'''On host "{hostname}" for target "{target_host}" {message}

Alarm "{alarm_name}" transitioned to the {state} state at {timestamp} UTC
alarm_id: {alarm_id}

Lifecycle state: {lifecycle_state}
Link: {link}
Link to Grafana: {grafana_url}

With dimensions:
{metric_dimensions}'''

EMAIL_MULTIPLE_HOST_BASE = u'''On host "{hostname}" {message}

Alarm "{alarm_name}" transitioned to the {state} state at {timestamp} UTC
alarm_id: {alarm_id}

Lifecycle state: {lifecycle_state}
Link: {link}
Link to Grafana: {grafana_url}

With dimensions:
{metric_dimensions}'''

EMAIL_NO_HOST_BASE = u'''On multiple hosts {message}

Alarm "{alarm_name}" transitioned to the {state} state at {timestamp} UTC
Alarm_id: {alarm_id}

Lifecycle state: {lifecycle_state}
Link: {link}
Link to Grafana: {grafana_url}

With dimensions
{metric_dimensions}'''


class EmailNotifier(abstract_notifier.AbstractNotifier):

    type = 'email'

    def __init__(self, log):
        super(EmailNotifier, self).__init__()
        self._log = log
        self._smtp = None

    @removals.remove(
        message='Configuration of notifier is available through oslo.cfg',
        version='1.9.0',
        removal_version='3.0.0'
    )
    def config(self, config=None):
        self._smtp_connect()

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
        self._smtp.sendmail(CONF.email_notifier.from_addr,
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
        self._log.info("Connecting to Email Server {}".format(
            CONF.email_notifier.server))

        try:
            smtp = smtplib.SMTP(CONF.email_notifier.server,
                                CONF.email_notifier.port,
                                timeout=CONF.email_notifier.timeout)

            email_notifier_user = CONF.email_notifier.user
            email_notifier_password = CONF.email_notifier.password
            if email_notifier_user and email_notifier_password:
                smtp.login(email_notifier_user,
                           email_notifier_password)

            self._smtp = smtp
            return True
        except Exception:
            self._log.exception("Unable to connect to email server.")
            return False

    def _create_msg(self, hostname, notification, targethost=None):
        """Create two kind of messages:
        1. Notifications that include metrics with a hostname as a dimension.
        There may be more than one hostname.
           We will only report the hostname if there is only one.
        2. Notifications that do not include metrics and therefore no hostname.
        Example: API initiated changes.
           * A third notification type which include metrics but do not include a hostname will
           be treated as type #2.
        """
        timestamp = time.asctime(time.gmtime(notification.alarm_timestamp))

        alarm_seconds = notification.alarm_timestamp
        alarm_ms = int(round(alarm_seconds * 1000))

        graf_url = self._get_link_url(notification.metrics[0], alarm_ms)

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
                    grafana_url=graf_url,
                    lifecycle_state=notification.lifecycle_state
                )
                subject = u'{} {} "{}" for Host: {} Target: {}'.format(
                    notification.state, notification.severity,
                    notification.alarm_name, hostname[0],
                    targethost[0]
                )
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
                    grafana_url=graf_url,
                    lifecycle_state=notification.lifecycle_state
                )
                subject = u'{} {} "{}" for Host: {}'.format(
                    notification.state, notification.severity,
                    notification.alarm_name, hostname[0])
        else:  # Type 2
            text = EMAIL_NO_HOST_BASE.format(
                message=notification.message.lower(),
                alarm_name=notification.alarm_name,
                state=notification.state,
                timestamp=timestamp,
                alarm_id=notification.alarm_id,
                metric_dimensions=dimensions,
                link=notification.link,
                grafana_url=graf_url,
                lifecycle_state=notification.lifecycle_state
            )
            subject = u'{} {} "{}" '.format(notification.state,
                                            notification.severity,
                                            notification.alarm_name)

        msg = email.mime.text.MIMEText(text, 'plain', 'utf-8')
        msg['Subject'] = email.header.Header(subject, 'utf-8')
        msg['From'] = CONF.email_notifier.from_addr
        msg['To'] = notification.address
        msg['Date'] = email.utils.formatdate(localtime=True, usegmt=True)

        return msg

    def _get_link_url(self, metric, timestamp_ms):
        """Returns the url to Grafana including a query with the
        respective metric info (name, dimensions, timestamp)
        :param metric: the metric for which to display the graph in Grafana
        :param timestamp_ms: timestamp of the alarm for the metric in milliseconds
        :return: the url to the graph for the given metric or None if no Grafana host
        has been defined.
        """

        grafana_url = CONF.email_notifier.grafana_url
        if grafana_url is None:
            return None

        url = ''
        metric_query = ''

        metric_query = "?metric=%s" % metric['name']

        dimensions = metric['dimensions']
        for key, value in dimensions.items():
            metric_query += "&%s=%s" % (key, value)

        # Show the graph within a range of ten minutes before and after the alarm occurred.
        offset = 600000
        from_ms = timestamp_ms - offset
        to_ms = timestamp_ms + offset
        time_query = "&from=%s&to=%s" % (from_ms, to_ms)

        url = grafana_url + '/dashboard/script/drilldown.js'

        return url + metric_query + time_query


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


email_notifier_group = cfg.OptGroup(name='%s_notifier' % EmailNotifier.type)
email_notifier_opts = [
    cfg.StrOpt(name='from_addr'),
    cfg.HostAddressOpt(name='server'),
    cfg.PortOpt(name='port', default=25),
    cfg.IntOpt(name='timeout', default=5, min=1),
    cfg.StrOpt(name='user', default=None),
    cfg.StrOpt(name='password', default=None, secret=True),
    cfg.StrOpt(name='grafana_url', default=None)
]


def register_opts(conf):
    conf.register_group(email_notifier_group)
    conf.register_opts(email_notifier_opts, group=email_notifier_group)


def list_opts():
    return {
        email_notifier_group: email_notifier_opts
    }
