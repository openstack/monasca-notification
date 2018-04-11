# coding=utf-8
# (C) Copyright 2014-2016 Hewlett Packard Enterprise Development LP
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

import base64
import email.header
import mock
import smtplib
import socket
import time

import six

import datetime

if six.PY2:
    import urlparse
else:
    from urllib import parse
    from urllib.parse import urlparse

from monasca_notification.notification import Notification
from monasca_notification.plugins import email_notifier
from tests import base

UNICODE_CHAR = six.unichr(2344)
UNICODE_CHAR_ENCODED = UNICODE_CHAR.encode("utf-8")


def alarm(metrics):
    return {"tenantId": "0",
            "alarmId": "0",
            "alarmName": u"test Alarm " + UNICODE_CHAR,
            "oldState": "OK",
            "newState": "ALARM",
            "severity": "LOW",
            "link": "some-link",
            "lifecycleState": "OPEN",
            "stateChangeReason": u"I am alarming!" + UNICODE_CHAR,
            "timestamp": time.time(),
            "metrics": metrics}


def _parse_email(email_msg):
    raw_mail = {"raw": email_msg}
    email_lines = email_msg.splitlines()

    from_addr, subject, to_addr = _decode_headers(email_lines)

    raw_mail['subject'] = subject[0].decode(subject[1])
    raw_mail['from'] = from_addr[0]
    raw_mail['to'] = to_addr[0]
    raw_mail['body'] = (base64.b64decode('\n'.join(email_lines[8:]))
                        .decode('utf-8'))

    return raw_mail


def _decode_headers(email_lines):
    # message is encoded, so we need to carefully go through all the lines
    # to pick ranges for subject, from and to
    keys = ['Subject', 'From', 'To']
    subject, from_addr, to_addr = None, None, None
    for key_idx, key in enumerate(keys):
        accummulated = []
        for idx in range(3, len(email_lines) - 1):
            line = email_lines[idx]
            if not line:
                break
            if key in line:
                accummulated.append(line)
                try:
                    if keys[key_idx + 1] not in email_lines[idx + 1]:
                        accummulated.append(email_lines[idx + 1])
                    else:
                        break
                except IndexError:
                    pass
        if key == 'Subject':
            subject = email.header.decode_header(''.join(accummulated))[1]
        if key == 'From':
            from_addr = email.header.decode_header(''.join(accummulated))[0]
        if key == 'To':
            to_addr = email.header.decode_header(''.join(accummulated))[0]
    return from_addr, subject, to_addr


class smtpStub(object):
    def __init__(self, trap):
        self.trap = trap

    def sendmail(self, from_addr, to_addr, msg):
        self.trap.append("{} {} {}".format(from_addr, to_addr, msg))


class smtpStubException(object):
    def __init__(self, queue):
        self.queue = queue

    def sendmail(self, from_addr, to_addr, msg):
        raise smtplib.SMTPServerDisconnected


class TestEmail(base.PluginTestCase):
    def setUp(self):
        super(TestEmail, self).setUp(email_notifier.register_opts)

        self.trap = []
        self.conf_override(group='email_notifier', server='my.smtp.server',
                           port=25, user=None,
                           password=None, timeout=60,
                           from_addr='hpcs.mon@hp.com',
                           grafana_url='http://127.0.0.1:3000')

    def _smtpStub(self, *arg, **kwargs):
        return smtpStub(self.trap)

    def _smtbStubException(self, *arg, **kwargs):
        return smtpStubException(self.trap)

    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    def notify(self, smtp_stub, metric, mock_smtp):
        mock_smtp.SMTP = smtp_stub

        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append

        email = email_notifier.EmailNotifier(mock_log)

        alarm_dict = alarm(metric)

        notification = Notification(0, 'email', 'email notification',
                                    'me@here.com', 0, 0, alarm_dict)

        self.trap.append(email.send_notification(notification))

    def test_email_notification_single_host(self):
        """Email with single host
        """

        metrics = []
        metric_data = {'name': 'cpu.percent',
                       'dimensions': {'hostname': u'foo1' + UNICODE_CHAR,
                                      u'service' + UNICODE_CHAR: 'bar1'}}
        metrics.append(metric_data)

        self.notify(self._smtpStub, metrics)

        email = _parse_email(self.trap.pop(0))

        self.assertRegex(email['from'], 'hpcs.mon@hp.com')
        self.assertRegex(email['to'], 'me@here.com')
        self.assertRegex(email['raw'], 'Content-Type: text/plain')
        self.assertRegex(email['raw'], 'Content-Transfer-Encoding: base64')
        self.assertRegex(email['subject'],
                         'ALARM LOW "test Alarm .*" for Host: foo1.*')
        self.assertRegex(email['body'], 'Alarm .test Alarm.')
        self.assertRegex(email['body'], 'On host .foo1.')
        self.assertRegex(email['body'], UNICODE_CHAR)
        self.assertRegex(email['body'], 'Link: some-link')
        self.assertRegex(email['body'], 'Lifecycle state: OPEN')

        return_value = self.trap.pop(0)
        self.assertTrue(return_value)

    def test_email_notification_target_host(self):
        """Email with single host
        """

        metrics = []
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': u'foo1' + UNICODE_CHAR,
                                                             u'service' + UNICODE_CHAR: 'bar1',
                                                             u'target_host': u'some_where'}}
        metrics.append(metric_data)

        self.notify(self._smtpStub, metrics)

        email = _parse_email(self.trap.pop(0))

        self.assertRegex(email['from'], 'hpcs.mon@hp.com')
        self.assertRegex(email['to'], 'me@here.com')
        self.assertRegex(email['raw'], 'Content-Type: text/plain')
        self.assertRegex(email['raw'], 'Content-Transfer-Encoding: base64')
        self.assertRegex(email['subject'],
                         'ALARM LOW .test Alarm.* Target: some_where')
        self.assertRegex(email['body'], "Alarm .test Alarm.")
        self.assertRegex(email['body'], "On host .foo1.")
        self.assertRegex(email['body'], UNICODE_CHAR)

        return_value = self.trap.pop(0)
        self.assertTrue(return_value)

    def worktest_email_notification_multiple_hosts(self):
        """Email with multiple hosts
        """

        metrics = []
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        self.notify(self._smtpStub, metrics)

        email = _parse_email(self.trap.pop(0))

        self.assertRegex(email['from'], "From: hpcs.mon@hp.com")
        self.assertRegex(email['to'], "To: me@here.com")
        self.assertRegex(email['raw'], "Content-Type: text/plain")
        self.assertRegex(email['subject'], "Subject: ALARM LOW .test Alarm.")
        self.assertRegex(email['body'], "Alarm .test Alarm.")
        self.assertRegex(email['body'], "foo1")
        self.assertRegex(email['body'], "foo2")
        self.assertRegex(email['body'], "bar1")
        self.assertRegex(email['body'], "bar2")

        return_value = self.trap.pop(0)
        self.assertTrue(return_value)

    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    def test_smtp_sendmail_failed_connection_twice(self, mock_smtp):
        """Email that fails on smtp_connect twice
        """

        metrics = []
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.debug = self.trap.append
        mock_log.info = self.trap.append
        mock_log.exception = self.trap.append

        # mock_smtp.SMTP.return_value = mock_smtp
        mock_smtp.SMTP.side_effect = [mock_smtp,
                                      smtplib.SMTPServerDisconnected,
                                      socket.error]

        mock_smtp.sendmail.side_effect = [smtplib.SMTPServerDisconnected,
                                          smtplib.SMTPServerDisconnected]

        # There has to be a better way to preserve exception definitions when
        # we're mocking access to a library
        mock_smtp.SMTPServerDisconnected = smtplib.SMTPServerDisconnected
        mock_smtp.SMTPException = smtplib.SMTPException

        email = email_notifier.EmailNotifier(mock_log)

        email.config()

        alarm_dict = alarm(metrics)

        notification = Notification(0, 'email', 'email notification',
                                    'me@here.com', 0, 0, alarm_dict)

        self.trap.append(email.send_notification(notification))

        self.assertIn("SMTP server disconnected. Will reconnect and retry message.", self.trap)
        self.assertIn("Unable to connect to email server.", self.trap)

    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    def test_smtp_sendmail_smtp_None(self, mock_smtp):
        """Email that fails on smtp_connect twice
        """

        metrics = []
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.debug = self.trap.append
        mock_log.info = self.trap.append
        mock_log.exception = self.trap.append

        mock_smtp.SMTP.return_value = None
        mock_smtp.SMTP.side_effect = [socket.error,
                                      socket.error,
                                      socket.error]

        mock_smtp.sendmail.side_effect = [smtplib.SMTPServerDisconnected,
                                          smtplib.SMTPServerDisconnected]

        # There has to be a better way to preserve exception definitions when
        # we're mocking access to a library
        mock_smtp.SMTPServerDisconnected = smtplib.SMTPServerDisconnected
        mock_smtp.SMTPException = smtplib.SMTPException

        email = email_notifier.EmailNotifier(mock_log)

        email.config()

        del self.trap[:]

        alarm_dict = alarm(metrics)

        notification = Notification(0, 'email', 'email notification',
                                    'me@here.com', 0, 0, alarm_dict)

        email_result = email.send_notification(notification)

        self.assertFalse(email_result)
        self.assertIn("Connecting to Email Server my.smtp.server",
                      self.trap)

    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    def test_smtp_sendmail_failed_connection_once_then_email(self, mock_smtp):
        """Email that fails on smtp_connect once then email
        """

        metrics = []
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.debug = self.trap.append
        mock_log.info = self.trap.append
        mock_log.exception = self.trap.append

        mock_smtp.SMTP.return_value = mock_smtp

        mock_smtp.sendmail.side_effect = [smtplib.SMTPServerDisconnected,
                                          smtplib.SMTPException]

        # There has to be a better way to preserve exception definitions when
        # we're mocking access to a library
        mock_smtp.SMTPServerDisconnected = smtplib.SMTPServerDisconnected
        mock_smtp.SMTPException = smtplib.SMTPException

        email = email_notifier.EmailNotifier(mock_log)

        email.config()

        alarm_dict = alarm(metrics)

        notification = Notification(0, 'email', 'email notification',
                                    'me@here.com', 0, 0, alarm_dict)

        self.trap.append(email.send_notification(notification))

        self.assertIn("SMTP server disconnected. Will reconnect and retry message.", self.trap)
        self.assertIn("Error sending Email Notification", self.trap)
        self.assertNotIn("Unable to connect to email server.", self.trap)

    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    def test_smtp_sendmail_failed_connection_once(self, mock_smtp):
        """Email that fails on smtp_connect once
        """

        metrics = []
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.debug = self.trap.append
        mock_log.info = self.trap.append
        mock_log.exception = self.trap.append

        mock_smtp.SMTP.return_value = mock_smtp
        mock_smtp.sendmail.side_effect = [smtplib.SMTPServerDisconnected, None]

        # There has to be a better way to preserve exception definitions when
        # we're mocking access to a library
        mock_smtp.SMTPServerDisconnected = smtplib.SMTPServerDisconnected
        mock_smtp.SMTPException = smtplib.SMTPException

        email = email_notifier.EmailNotifier(mock_log)

        email.config()

        alarm_dict = alarm(metrics)

        notification = Notification(0, 'email', 'email notification',
                                    'me@here.com', 0, 0, alarm_dict)

        self.trap.append(email.send_notification(notification))

        self.assertIn("SMTP server disconnected. Will reconnect and retry message.", self.trap)
        self.assertIn("Sent email to %s, notification %s"
                      % (notification.address, notification.to_json()), self.trap)

    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    def test_smtp_sendmail_failed_exception(self, mock_smtp):
        """Email that fails on exception
        """

        metrics = []
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'name': 'cpu.percent', 'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.debug = self.trap.append
        mock_log.info = self.trap.append
        mock_log.exception = self.trap.append

        mock_smtp.SMTP.return_value = mock_smtp
        mock_smtp.sendmail.side_effect = smtplib.SMTPException

        # There has to be a better way to preserve exception definitions when
        # we're mocking access to a library
        mock_smtp.SMTPServerDisconnected = smtplib.SMTPServerDisconnected
        mock_smtp.SMTPException = smtplib.SMTPException

        email = email_notifier.EmailNotifier(mock_log)

        email.config()

        alarm_dict = alarm(metrics)

        notification = Notification(0, 'email', 'email notification',
                                    'me@here.com', 0, 0, alarm_dict)

        self.trap.append(email.send_notification(notification))

        self.assertNotIn("SMTP server disconnected. Will reconnect and retry message.", self.trap)
        self.assertIn("Error sending Email Notification", self.trap)

    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    def test_get_link_url(self, mock_smtp):
        # Given one metric with name and dimensions
        metrics = []
        metric = {'name': 'cpu.percent',
                  'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric)

        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.debug = self.trap.append
        mock_log.info = self.trap.append
        mock_log.exception = self.trap.append

        mock_smtp.SMTP.return_value = mock_smtp
        mock_smtp.sendmail.side_effect = smtplib.SMTPException

        mock_smtp.SMTPServerDisconnected = smtplib.SMTPServerDisconnected
        mock_smtp.SMTPException = smtplib.SMTPException

        email = email_notifier.EmailNotifier(mock_log)

        # Create alarm timestamp and timestamp for 'from' and 'to' dates in milliseconds.
        alarm_date = datetime.datetime(2017, 6, 7, 18, 0)
        alarm_ms, expected_from_ms, expected_to_ms = self.create_time_data(alarm_date)

        # When retrieving the link to Grafana for the first metric and given timestamp
        result_url = email._get_link_url(metrics[0], alarm_ms)
        self.assertIsNotNone(result_url)

        # Then the following link to Grafana (including the metric info and timestamp) is expected.
        expected_url = "http://127.0.0.1:3000/dashboard/script/drilldown.js" \
                       "?metric=cpu.percent&dim_hostname=foo1&dim_service=bar1" \
                       "&from=%s&to=%s" % (expected_from_ms, expected_to_ms)
        self._assert_equal_urls(expected_url, result_url)

    def create_time_data(self, alarm_date):
        epoch = datetime.datetime.utcfromtimestamp(0)
        alarm_ms = int(round((alarm_date - epoch).total_seconds() * 1000))

        # From and to dates are 10 minutes before and after the alarm occurred.
        from_date = alarm_date - datetime.timedelta(minutes=10)
        to_date = alarm_date + datetime.timedelta(minutes=10)

        expected_from_ms = int(round((from_date - epoch).total_seconds() * 1000))
        expected_to_ms = int(round((to_date - epoch).total_seconds() * 1000))

        return alarm_ms, expected_from_ms, expected_to_ms

    def _assert_equal_urls(self, expected_url, result_url):
        if six.PY2:
            expected_parsed = urlparse.urlparse(expected_url)
            result_parsed = urlparse.urlparse(result_url)
        else:
            expected_parsed = urlparse(expected_url)
            result_parsed = urlparse(result_url)

        self.assertEqual(expected_parsed.netloc, result_parsed.netloc)
        self.assertEqual(expected_parsed.path, result_parsed.path)

        if six.PY2:
            expected_parsed_query = urlparse.parse_qs(expected_parsed.query)
            result_parsed_query = urlparse.parse_qs(result_parsed.query)
        else:
            expected_parsed_query = parse.parse_qs(expected_parsed.query)
            result_parsed_query = parse.parse_qs(result_parsed.query)

        self.assertEqual(len(expected_parsed_query), len(result_parsed_query))

        for key in six.iterkeys(result_parsed_query):
            self.assertEqual(expected_parsed_query[key], result_parsed_query[key])
