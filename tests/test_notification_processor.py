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

"""Tests NotificationProcessor"""

import time
from unittest import mock

from monasca_notification import notification as m_notification
from monasca_notification.plugins import email_notifier
from monasca_notification.processors import notification_processor as np
from tests import base


class smtpStub(object):
    def __init__(self, log_queue):
        self.queue = log_queue

    def sendmail(self, from_addr, to_addr, msg):
        self.queue.put("%s %s %s" % (from_addr, to_addr, msg))


class requestsResponse(object):
    def __init__(self, status):
        self.status_code = status


class TestNotificationProcessor(base.BaseTestCase):

    def setUp(self):
        super(TestNotificationProcessor, self).setUp()
        self.trap = []

        email_notifier.register_opts(base.config.CONF)

        self.conf_default(group='email_notifier', server='my.smtp.server',
                          port=25, user=None, password=None,
                          timeout=60, from_addr='hpcs.mon@hp.com')
        self.conf_default(group='mysql', ssl=None, host='localhost',
                          port='3306', user='mysql_user', db='dbname',
                          passwd='mysql_passwd')
        self.conf_default(group='statsd', host='localhost', port=8125)

        self.conf_default(group='notification_types', enabled=[])

    # ------------------------------------------------------------------------
    # Test helper functions
    # ------------------------------------------------------------------------
    @mock.patch('pymysql.connect')
    @mock.patch('monasca_notification.common.utils.monascastatsd')
    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    @mock.patch('monasca_notification.processors.notification_processor.notifiers.log')
    def _start_processor(self, notifications, mock_log, mock_smtp, mock_statsd, mock_pymsql):
        """Start the processor with the proper mocks
        """
        # Since the log runs in another thread I can mock it directly,
        # instead change the methods to put to a queue
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append

        mock_smtp.SMTP = self._smtpStub

        np.NotificationProcessor.insert_configured_plugins = mock.Mock()
        processor = np.NotificationProcessor()
        processor.send(notifications)

    def _smtpStub(self, *arg, **kwargs):
        return smtpStub(self.trap)

    def email_setup(self, metric):
        alarm_dict = {"tenantId": "0",
                      "alarmId": "0",
                      "alarmName": "test Alarm",
                      "oldState": "OK",
                      "newState": "ALARM",
                      "severity": "LOW",
                      "link": "some-link",
                      "lifecycleState": "OPEN",
                      "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(),
                      "metrics": metric}

        notification = m_notification.Notification(
            0, 'email', 'email notification', 'me@here.com', 0, 0, alarm_dict)

        self._start_processor([notification])

    # ------------------------------------------------------------------------
    # Unit tests
    # ------------------------------------------------------------------------

    def test_invalid_notification(self):
        """Verify invalid notification type is rejected.
        """
        alarm_dict = {
            "tenantId": "0",
            "alarmId": "0",
            "alarmName": "test Alarm",
            "oldState": "OK",
            "newState": "ALARM",
            "stateChangeReason": "I am alarming!",
            "timestamp": time.time(),
            "metrics": "cpu_util",
            "severity": "LOW",
            "link": "http://some-place.com",
            "lifecycleState": "OPEN"}
        invalid_notification = m_notification.Notification(0, 'invalid', 'test notification',
                                                           'me@here.com', 0, 0, alarm_dict)

        self._start_processor([invalid_notification])

        self.assertIn('attempting to send unconfigured notification: invalid', self.trap)

    def test_email_notification_single_host(self):
        """Email with single host
        """

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)

        self.email_setup(metrics)

        for msg in self.trap:
            if "From: hpcs.mon@hp.com" in msg:
                self.assertRegex(msg, "From: hpcs.mon@hp.com")
                self.assertRegex(msg, "To: me@here.com")
                self.assertRegex(msg, "Content-Type: text/plain")
                self.assertRegex(msg, "Alarm .test Alarm.")
                self.assertRegex(msg, "On host .foo1.")
