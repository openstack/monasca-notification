# (C) Copyright 2015-2017 Hewlett Packard Enterprise Development LP
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

import contextlib
import time
from unittest import mock

from monasca_notification import notification as m_notification
from monasca_notification.plugins import email_notifier
from monasca_notification.plugins import pagerduty_notifier
from monasca_notification.plugins import webhook_notifier
from monasca_notification.types import notifiers
from tests import base


def alarm(metrics):
    return {"tenantId": "0",
            "alarmId": "0",
            "alarmName": "test Alarm",
            "oldState": "OK",
            "newState": "ALARM",
            "severity": "LOW",
            "link": "some-link",
            "lifecycleState": "OPEN",
            "stateChangeReason": "I am alarming!",
            "timestamp": time.time(),
            "metrics": metrics}


class NotifyStub(object):
    def __init__(self, trap, config, send, failure):
        self.config_exception = config
        self.send_exception = send
        self.failure = failure
        self.trap = trap

    @property
    def type(self):
        return "email"

    @property
    def statsd_name(self):
        return "smtp_sent"

    def config(self, config_dict):
        if self.config_exception:
            raise Exception
        else:
            pass

    def send_notification(self, notification_obj):
        if self.send_exception:
            raise Exception
        else:
            if self.failure:
                return False
            else:
                return True


class Statsd(object):
    def __init__(self):
        self.timer = StatsdTimer()
        self.counter = StatsdCounter()

    def get_timer(self):
        return self.timer

    def get_counter(self, key):
        return self.counter


class StatsdTimer(object):
    def __init__(self):
        self.timer_calls = {}

    @contextlib.contextmanager
    def time(self, key):
        self.start(key)
        yield
        self.stop(key)

    def start(self, key):
        key = key + "_start"
        if key in self.timer_calls:
            self.timer_calls[key] += 1
        else:
            self.timer_calls[key] = 1

    def stop(self, key):
        key = key + "_stop"
        if key in self.timer_calls:
            self.timer_calls[key] += 1
        else:
            self.timer_calls[key] = 1


class StatsdCounter(object):
    def __init__(self):
        self.counter = 0

    def increment(self, val):
        self.counter += val


class TestInterface(base.BaseTestCase):

    def setUp(self):
        super(TestInterface, self).setUp()
        self.trap = []
        self.statsd = Statsd()

        email_notifier.register_opts(base.config.CONF)
        webhook_notifier.register_opts(base.config.CONF)
        pagerduty_notifier.register_opts(base.config.CONF)

        self.conf_override(group='email_notifier', server='my.smtp.server',
                           port=25, user=None, password=None,
                           timeout=60, from_addr='hpcs.mon@hp.com')

    def tearDown(self):
        super(TestInterface, self).tearDown()
        notifiers.possible_notifiers = []
        notifiers.configured_notifiers = {}
        self.trap = []

    def _configExceptionStub(self, log):
        return NotifyStub(self.trap, True, False, False)

    def _sendExceptionStub(self, log):
        return NotifyStub(self.trap, False, True, False)

    def _sendFailureStub(self, log):
        return NotifyStub(self.trap, False, False, True)

    def _goodSendStub(self, log):
        return NotifyStub(self.trap, False, False, False)

    def test_enabled_notifications_none(self):
        self.conf_override(
            group='notification_types',
            enabled=[]
        )

        notifiers.init(self.statsd)
        notifiers.load_plugins()
        notifiers.config()

        notifications = notifiers.enabled_notifications()

        self.assertEqual(len(notifications), 0)

    def test_enabled_notifications(self):
        self.conf_override(
            group='notification_types',
            enabled=[
                'monasca_notification.plugins.email_notifier:EmailNotifier',
                'monasca_notification.plugins.pagerduty_notifier:PagerdutyNotifier',
                'monasca_notification.plugins.webhook_notifier:WebhookNotifier',
                'monasca_notification.plugins.hipchat_notifier:HipChatNotifier',
                'monasca_notification.plugins.slack_notifier:SlackNotifier',
                'monasca_notification.plugins.jira_notifier:JiraNotifier'
            ]
        )
        notifiers.init(self.statsd)
        notifiers.load_plugins()
        notifiers.config()

        notifications = notifiers.enabled_notifications()
        self.assertEqual(len(notifications), 6)
        self.assertItemsEqual(notifications,
                              ['EMAIL', 'PAGERDUTY', 'WEBHOOK',
                               'HIPCHAT', 'SLACK', 'JIRA'])

    @mock.patch('monasca_notification.plugins.email_notifier')
    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    @mock.patch('monasca_notification.types.notifiers.log')
    @mock.patch('monasca_notification.types.notifiers.importutils')
    def test_send_notification_exception(self, mock_im, mock_log,
                                         mock_smtp, mock_email):
        self.conf_override(
            group='notification_types',
            enabled=[
                'monasca_notification.plugins.email_notifier:EmailNotifier'
            ]
        )

        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.exception = self.trap.append

        mock_email.EmailNotifier = self._sendExceptionStub
        mock_im.import_class.return_value = mock_email.EmailNotifier

        notifiers.init(self.statsd)
        notifiers.load_plugins()
        notifiers.config()

        notifications = [
            m_notification.Notification(0, 'email', 'email notification',
                                        'me@here.com', 0, 0, alarm({}))
        ]

        notifiers.send_notifications(notifications)

        self.assertIn("send_notification exception for email", self.trap)

    @mock.patch('monasca_notification.plugins.email_notifier')
    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    @mock.patch('monasca_notification.types.notifiers.log')
    @mock.patch('monasca_notification.types.notifiers.importutils')
    def test_send_notification_failure(self, mock_im, mock_log,
                                       mock_smtp, mock_email):
        self.conf_override(
            group='notification_types',
            enabled=[
                'monasca_notification.plugins.email_notifier:EmailNotifier'
            ]
        )

        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.exception = self.trap.append

        mock_email.EmailNotifier = self._sendFailureStub
        mock_im.import_class.return_value = mock_email.EmailNotifier

        notifiers.init(self.statsd)
        notifiers.load_plugins()
        notifiers.config()

        notifications = [
            m_notification.Notification(0, 'email', 'email notification',
                                        'me@here.com', 0, 0, alarm({}))
        ]

        sent, failed, invalid = notifiers.send_notifications(notifications)

        self.assertEqual(sent, [])
        self.assertEqual(len(failed), 1)
        self.assertEqual(invalid, [])

    @mock.patch('monasca_notification.types.notifiers.time')
    @mock.patch('monasca_notification.plugins.email_notifier')
    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    @mock.patch('monasca_notification.types.notifiers.log')
    @mock.patch('monasca_notification.types.notifiers.importutils')
    def test_send_notification_correct(self, mock_im, mock_log, mock_smtp,
                                       mock_email, mock_time):
        self.conf_override(
            group='notification_types',
            enabled=[
                'monasca_notification.plugins.email_notifier:EmailNotifier'
            ]
        )

        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append

        mock_email.EmailNotifier = self._goodSendStub
        mock_time.time.return_value = 42
        mock_im.import_class.return_value = mock_email.EmailNotifier

        notifiers.init(self.statsd)
        notifiers.load_plugins()
        notifiers.config()

        notifications = [
            m_notification.Notification(0, 'email', 'email notification',
                                        'me@here.com', 0, 0, alarm({})),
            m_notification.Notification(1, 'email', 'email notification',
                                        'foo@here.com', 0, 0, alarm({})),
            m_notification.Notification(2, 'email', 'email notification',
                                        'bar@here.com', 0, 0, alarm({}))
        ]

        sent, failed, invalid = notifiers.send_notifications(notifications)

        self.assertEqual(len(sent), 3)
        self.assertEqual(failed, [])
        self.assertEqual(invalid, [])

        for n in sent:
            self.assertEqual(n.notification_timestamp, 42)

    @mock.patch('monasca_notification.plugins.email_notifier')
    @mock.patch('monasca_notification.plugins.email_notifier.smtplib')
    @mock.patch('monasca_notification.types.notifiers.log')
    @mock.patch('monasca_notification.types.notifiers.importutils')
    def test_statsd(self, mock_im, mock_log, mock_smtp, mock_email):
        self.conf_override(
            group='notification_types',
            enabled=[
                'monasca_notification.plugins.email_notifier:EmailNotifier'
            ]
        )

        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append

        mock_email.EmailNotifier = self._goodSendStub
        mock_im.import_class.return_value = mock_email.EmailNotifier

        notifiers.init(self.statsd)
        notifiers.load_plugins()
        notifiers.config()

        notifications = [
            m_notification.Notification(0, 'email', 'email notification',
                                        'me@here.com', 0, 0, alarm({})),
            m_notification.Notification(1, 'email', 'email notification',
                                        'foo@here.com', 0, 0, alarm({})),
            m_notification.Notification(2, 'email', 'email notification',
                                        'bar@here.com', 0, 0, alarm({}))
        ]

        notifiers.send_notifications(notifications)

        self.assertEqual(self.statsd.timer.timer_calls['email_time_start'], 3)
        self.assertEqual(self.statsd.timer.timer_calls['email_time_stop'], 3)
        self.assertEqual(self.statsd.counter.counter, 3)

    def test_plugin_load(self):
        self.conf_override(
            group='notification_types',
            enabled=[
                'monasca_notification.plugins.hipchat_notifier:HipChatNotifier',
                'monasca_notification.plugins.slack_notifier:SlackNotifier'
            ]
        )

        notifiers.init(self.statsd)
        notifiers.load_plugins()
        notifiers.config()

        self.assertEqual(len(notifiers.possible_notifiers), 2)
        self.assertItemsEqual(['hipchat', 'slack'],
                              notifiers.configured_notifiers)

    @mock.patch('monasca_notification.types.notifiers.log')
    def test_invalid_plugin_load_exception_ignored(self, mock_log):
        mock_log.exception = self.trap.append
        self.conf_override(
            group='notification_types',
            enabled=[
                'monasca_notification.plugins.hipchat_notifier:UnknownPlugin',
                'monasca_notification.plugins.slack_notifier:SlackNotifier'
            ]
        )

        notifiers.init(self.statsd)
        notifiers.load_plugins()
        self.assertEqual(len(notifiers.possible_notifiers), 1)
        self.assertEqual(len(self.trap), 1)

        configured_plugins = ["email", "webhook", "pagerduty", "slack"]
        for plugin in notifiers.configured_notifiers:
            self.asssertIn(plugin.type in configured_plugins)
