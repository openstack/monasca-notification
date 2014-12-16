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

"""Tests NotificationProcessor"""

import mock
import multiprocessing
import requests
import time
import unittest

from monasca_notification.notification import Notification
from monasca_notification.processors import notification_processor


class smtpStub(object):
    def __init__(self, log_queue):
        self.queue = log_queue

    def sendmail(self, from_addr, to_addr, msg):
        self.queue.put("%s %s %s" % (from_addr, to_addr, msg))


class requestsResponse(object):
    def __init__(self, status):
        self.status_code = status


class TestStateTracker(unittest.TestCase):

    def setUp(self):
        self.http_func = self._http_post_200
        self.notification_queue = multiprocessing.Queue(10)
        self.sent_notification_queue = multiprocessing.Queue(10)
        self.finished_queue = multiprocessing.Queue(10)
        self.log_queue = multiprocessing.Queue(10)
        self.email_config = {'server': 'my.smtp.server',
                             'port': 25,
                             'user': None,
                             'password': None,
                             'timeout': 60,
                             'from_addr': 'hpcs.mon@hp.com'}
        self.webhook_config = {'timeout': 50}

    @mock.patch('monasca_notification.processors.notification_processor.requests')
    @mock.patch('monasca_notification.processors.notification_processor.smtplib')
    @mock.patch('monasca_notification.processors.notification_processor.log')
    def _start_processor(self, mock_log, mock_smtp, mock_requests):
        """Start the processor with the proper mocks
        """
        # Since the log runs in another thread I can mock it directly, instead change the methods to put to a queue
        mock_log.warn = self.log_queue.put
        mock_log.error = self.log_queue.put

        mock_requests.post = self.http_func

        mock_smtp.SMTP = self._smtpStub

        self.mock_requests = mock_requests
        self.mock_log = mock_log
        self.mock_smtp = mock_smtp

        nprocessor = (notification_processor.
                      NotificationProcessor(self.notification_queue,
                                            self.sent_notification_queue,
                                            self.finished_queue,
                                            self.email_config,
                                            self.webhook_config))

        self.processor = multiprocessing.Process(target=nprocessor.run)
        self.processor.start()

    def _smtpStub(self, *arg, **kwargs):
        return smtpStub(self.log_queue)

    def _http_post_200(self, url, data, headers, **kwargs):
        self.log_queue.put("%s %s %s" % (url, data, headers))
        r = requestsResponse(200)
        return r

    def _http_post_404(self, url, data, headers, **kwargs):
        r = requestsResponse(404)
        return r

    def _http_post_exception(self, url, data, headers, **kwargs):
        self.log_queue.put("timeout %s" % kwargs["timeout"])
        raise requests.exceptions.Timeout

    def test_invalid_notification(self):
        """Verify invalid notification type is rejected.
        """
        alarm_dict = {"tenantId": "0", "alarmId": "0", "alarmName": "test Alarm", "oldState": "OK", "newState": "ALARM",
                      "stateChangeReason": "I am alarming!", "timestamp": time.time(), "metrics": "cpu_util"}
        invalid_notification = Notification('invalid', 0, 1, 'test notification', 'me@here.com', alarm_dict)

        self.notification_queue.put([invalid_notification])
        self._start_processor()
        finished = self.finished_queue.get(timeout=2)
        log_msg = self.log_queue.get(timeout=1)
        self.processor.terminate()

        self.assertTrue(finished == (0, 1))
        self.assertTrue(log_msg == 'Notification type invalid is not a valid type')

    def test_email_notification_single_host(self):
        """Email with single host
        """

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)

        alarm_dict = {"tenantId": "0",
                      "alarmId": "0",
                      "alarmName": "test Alarm",
                      "oldState": "OK",
                      "newState": "ALARM",
                      "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(),
                      "metrics": metrics}

        notification = Notification('email', 0, 1, 'email notification', 'me@here.com', alarm_dict)

        self.notification_queue.put([notification])
        self._start_processor()
        log_msg = self.log_queue.get(timeout=3)
        self.processor.terminate()

        self.assertRegexpMatches(log_msg, "From: hpcs.mon@hp.com")
        self.assertRegexpMatches(log_msg, "To: me@here.com")
        self.assertRegexpMatches(log_msg, "Content-Type: text/plain")
        self.assertRegexpMatches(log_msg, "Alarm .test Alarm.")
        self.assertRegexpMatches(log_msg, "On host .foo1.")

        self.assertTrue(self.log_queue.empty())

    def test_email_notification_multiple_hosts(self):
        """Email with multiple hosts
        """

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        alarm_dict = {"tenantId": "0",
                      "alarmId": "0",
                      "alarmName": "test Alarm",
                      "oldState": "OK",
                      "newState": "ALARM",
                      "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(),
                      "metrics": metrics}

        notification = Notification('email', 0, 1, 'email notification', 'me@here.com', alarm_dict)

        self.notification_queue.put([notification])
        self._start_processor()
        log_msg = self.log_queue.get(timeout=3)
        self.processor.terminate()

        self.assertRegexpMatches(log_msg, "From: hpcs.mon@hp.com")
        self.assertRegexpMatches(log_msg, "To: me@here.com")
        self.assertRegexpMatches(log_msg, "Content-Type: text/plain")
        self.assertRegexpMatches(log_msg, "Alarm .test Alarm.")
        self.assertNotRegexpMatches(log_msg, "foo1")
        self.assertNotRegexpMatches(log_msg, "foo2")

        self.assertTrue(self.log_queue.empty())

    def test_webhook_good_http_response(self):
        """webhook good response
        """

        self.http_func = self._http_post_200

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        alarm_dict = {"tenantId": "0",
                      "alarmId": "0",
                      "alarmName": "test Alarm",
                      "oldState": "OK",
                      "newState": "ALARM",
                      "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(),
                      "metrics": metrics}

        notification = Notification('webhook', 0, 1, 'email notification', 'me@here.com', alarm_dict)

        self.notification_queue.put([notification])
        self._start_processor()
        log_msg = self.log_queue.get(timeout=3)
        self.processor.terminate()

        self.assertRegexpMatches(log_msg, "me@here.com")
        self.assertRegexpMatches(log_msg, "alarm_id.: '0'")
        self.assertRegexpMatches(log_msg, "content-type.: .application/json")

        self.assertTrue(self.log_queue.empty())

    def test_webhook_bad_http_response(self):
        """webhook bad response
        """

        self.http_func = self._http_post_404

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        alarm_dict = {"tenantId": "0",
                      "alarmId": "0",
                      "alarmName": "test Alarm",
                      "oldState": "OK",
                      "newState": "ALARM",
                      "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(),
                      "metrics": metrics}

        notification = Notification('webhook', 0, 1, 'email notification', 'me@here.com', alarm_dict)

        self.notification_queue.put([notification])
        self._start_processor()
        log_msg = self.log_queue.get(timeout=3)
        self.processor.terminate()

        self.assertNotRegexpMatches(log_msg, "alarm_id.: .test Alarm")
        self.assertNotRegexpMatches(log_msg, "content-type.: .application/json")

        self.assertRegexpMatches(log_msg, "HTTP code 404")
        self.assertRegexpMatches(log_msg, "post on URL me@here.com")

        self.assertTrue(self.log_queue.empty())

    def test_webhook_timeout_exception_on_http_response(self):
        """webhook timeout exception
        """

        self.http_func = self._http_post_exception

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        alarm_dict = {"tenantId": "0",
                      "alarmId": "0",
                      "alarmName": "test Alarm",
                      "oldState": "OK",
                      "newState": "ALARM",
                      "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(),
                      "metrics": metrics}

        notification = Notification('webhook',
                                    0,
                                    1,
                                    'webhook notification',
                                    'http://localhost:21356',
                                    alarm_dict)

        self._start_processor()

        self.notification_queue.put([notification])

        log_msg = self.log_queue.get(timeout=3)

        self.assertEqual(log_msg, "timeout 50")

        log_msg = self.log_queue.get(timeout=3)

        self.assertNotRegexpMatches(log_msg, "alarm_id.: .test Alarm")
        self.assertNotRegexpMatches(log_msg, "content-type.: .application/json")

        self.assertRegexpMatches(log_msg, "Error trying to post on URL http://localhost:21356")
        self.assertRaises(requests.exceptions.Timeout)

        self.assertTrue(self.log_queue.empty())

        self.processor.terminate()
