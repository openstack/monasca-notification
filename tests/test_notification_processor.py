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

import json
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
        self.pagerduty_config = {'timeout': 50, 'key': 'foobar'}

    def tearDown(self):
        self.assertTrue(self.log_queue.empty())
        self.assertTrue(self.sent_notification_queue.empty())
        self.assertTrue(self.finished_queue.empty())
        self.processor.terminate()

    # ------------------------------------------------------------------------
    # Test helper functions
    # ------------------------------------------------------------------------

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
                                            self.webhook_config,
                                            self.pagerduty_config))

        self.processor = multiprocessing.Process(target=nprocessor.run)
        self.processor.start()

    def _smtpStub(self, *arg, **kwargs):
        return smtpStub(self.log_queue)

    def _http_post_200(self, url, data, headers, **kwargs):
        self.log_queue.put(url)
        self.log_queue.put(data)
        self.log_queue.put(headers)
        r = requestsResponse(200)
        return r

    def _http_post_201(self, url, data, headers, **kwargs):
        self.log_queue.put(url)
        self.log_queue.put(data)
        self.log_queue.put(headers)
        r = requestsResponse(201)
        return r

    def _http_post_202(self, url, data, headers, **kwargs):
        r = requestsResponse(202)
        return r

    def _http_post_204(self, url, data, headers, **kwargs):
        self.log_queue.put(url)
        self.log_queue.put(data)
        self.log_queue.put(headers)
        r = requestsResponse(204)
        return r

    def _http_post_400(self, url, data, headers, **kwargs):
        r = requestsResponse(400)
        return r

    def _http_post_403(self, url, data, headers, **kwargs):
        r = requestsResponse(403)
        return r

    def _http_post_404(self, url, data, headers, **kwargs):
        r = requestsResponse(404)
        return r

    def _http_post_500(self, url, data, headers, **kwargs):
        r = requestsResponse(500)
        return r

    def _http_post_504(self, url, data, headers, **kwargs):
        r = requestsResponse(504)
        return r

    def _http_post_exception(self, url, data, headers, **kwargs):
        self.log_queue.put("timeout %s" % kwargs["timeout"])
        raise requests.exceptions.Timeout

    def assertSentNotification(self):
        notification_msg = self.sent_notification_queue.get(timeout=3)
        self.assertNotEqual(notification_msg, None)

    def assertSentFinished(self):
        finished_msg = self.finished_queue.get(timeout=3)
        self.assertNotEqual(finished_msg, None)

    def alarm(self, metrics):
        return {"tenantId": "0",
                "alarmId": "0",
                "alarmName": "test Alarm",
                "oldState": "OK",
                "newState": "ALARM",
                "stateChangeReason": "I am alarming!",
                "timestamp": time.time(),
                "metrics": metrics}

    def email_setup(self, metric):
        alarm_dict = self.alarm(metric)

        notification = Notification('email', 0, 1, 'email notification', 'me@here.com', alarm_dict)

        self.notification_queue.put([notification])
        self._start_processor()

    def webhook_setup(self, http_func):
        self.http_func = http_func

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        alarm_dict = self.alarm(metrics)

        notification = Notification('webhook', 0, 1, 'email notification', 'me@here.com', alarm_dict)

        self.notification_queue.put([notification])
        self._start_processor()

    def pagerduty_setup(self, http_stub):
        self.http_func = http_stub

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        alarm_dict = self.alarm(metrics)

        notification = Notification('pagerduty',
                                    0,
                                    1,
                                    'pagerduty notification',
                                    'ABCDEF',
                                    alarm_dict)
        self._start_processor()
        self.notification_queue.put([notification])

    def valid_pagerduty_message(self, url, data, headers):
        self.assertEqual(
            url, 'https://events.pagerduty.com/generic/2010-04-15/create_event.json')

        headers = dict(headers)
        self.assertEqual(headers['content-type'], 'application/json')

        data = dict(json.loads(data))
        self.assertEqual(data['service_key'], 'ABCDEF')
        self.assertEqual(data['event_type'], 'trigger')
        self.assertEqual(data['description'], 'I am alarming!')
        self.assertEqual(data['client'], 'Monasca')
        self.assertEqual(data['client_url'], '')

        details = dict(data['details'])
        self.assertEqual(details['alarm_id'], '0')
        self.assertEqual(details['alarm_name'], 'test Alarm')
        self.assertEqual(details['current'], 'ALARM')
        self.assertEqual(details['message'], 'I am alarming!')

    def pagerduty_http_error(self, log_msg, http_response):
        self.assertRegexpMatches(log_msg, "Error with pagerduty request.")
        self.assertRegexpMatches(log_msg, "key=<ABCDEF>")
        self.assertRegexpMatches(log_msg, "response=%s" % http_response)

    # ------------------------------------------------------------------------
    # Unit tests
    # ------------------------------------------------------------------------

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

        self.email_setup(metrics)

        log_msg = self.log_queue.get(timeout=3)

        self.assertRegexpMatches(log_msg, "From: hpcs.mon@hp.com")
        self.assertRegexpMatches(log_msg, "To: me@here.com")
        self.assertRegexpMatches(log_msg, "Content-Type: text/plain")
        self.assertRegexpMatches(log_msg, "Alarm .test Alarm.")
        self.assertRegexpMatches(log_msg, "On host .foo1.")

        self.assertSentNotification()

    def test_email_notification_multiple_hosts(self):
        """Email with multiple hosts
        """

        metrics = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metrics.append(metric_data)
        metric_data = {'dimensions': {'hostname': 'foo2', 'service': 'bar2'}}
        metrics.append(metric_data)

        self.email_setup(metrics)

        log_msg = self.log_queue.get(timeout=3)

        self.assertRegexpMatches(log_msg, "From: hpcs.mon@hp.com")
        self.assertRegexpMatches(log_msg, "To: me@here.com")
        self.assertRegexpMatches(log_msg, "Content-Type: text/plain")
        self.assertRegexpMatches(log_msg, "Alarm .test Alarm.")
        self.assertNotRegexpMatches(log_msg, "foo1")
        self.assertNotRegexpMatches(log_msg, "foo2")

        self.assertSentNotification()

    def test_webhook_good_http_response(self):
        """webhook 200
        """

        self.webhook_setup(self._http_post_200)

        url = self.log_queue.get(timeout=3)
        data = self.log_queue.get(timeout=3)
        headers = self.log_queue.get(timeout=3)

        self.assertEqual(url, "me@here.com")
        self.assertEqual(data, {'alarm_id': '0'})
        self.assertEqual(headers, {'content-type': 'application/json'})

        self.assertSentNotification()

    def test_webhook_bad_http_response(self):
        """webhook bad response
        """

        self.webhook_setup(self._http_post_404)

        log_msg = self.log_queue.get(timeout=3)

        self.assertNotRegexpMatches(log_msg, "alarm_id.: .test Alarm")
        self.assertNotRegexpMatches(log_msg, "content-type.: .application/json")

        self.assertRegexpMatches(log_msg, "HTTP code 404")
        self.assertRegexpMatches(log_msg, "post on URL me@here.com")

        self.assertSentFinished()

    def test_webhook_timeout_exception_on_http_response(self):
        """webhook timeout exception
        """

        self.webhook_setup(self._http_post_exception)

        log_msg = self.log_queue.get(timeout=3)

        self.assertEqual(log_msg, "timeout 50")

        log_msg = self.log_queue.get(timeout=3)

        self.assertNotRegexpMatches(log_msg, "alarm_id.: .test Alarm")
        self.assertNotRegexpMatches(log_msg, "content-type.: .application/json")

        self.assertRegexpMatches(log_msg, "Error trying to post on URL me@here")
        self.assertRaises(requests.exceptions.Timeout)

        self.assertSentFinished()

    def test_pagerduty_200(self):
        """pagerduty 200
        """

        self.pagerduty_setup(self._http_post_200)

        url = self.log_queue.get(timeout=3)
        data = self.log_queue.get(timeout=3)
        headers = self.log_queue.get(timeout=3)

        self.valid_pagerduty_message(url, data, headers)
        self.assertSentNotification()

    def test_pagerduty_201(self):
        """pagerduty 201
        """

        self.pagerduty_setup(self._http_post_201)

        url = self.log_queue.get(timeout=3)
        data = self.log_queue.get(timeout=3)
        headers = self.log_queue.get(timeout=3)

        self.valid_pagerduty_message(url, data, headers)
        self.assertSentNotification()

    def test_pagerduty_204(self):
        """pagerduty 204
        """

        self.pagerduty_setup(self._http_post_204)

        url = self.log_queue.get(timeout=3)
        data = self.log_queue.get(timeout=3)
        headers = self.log_queue.get(timeout=3)

        self.valid_pagerduty_message(url, data, headers)
        self.assertSentNotification()

    def test_pagerduty_202(self):
        """pagerduty 202
        """

        self.pagerduty_setup(self._http_post_202)
        log_msg = self.log_queue.get(timeout=3)
        self.pagerduty_http_error(log_msg, "202")
        self.assertSentFinished()

    def test_pagerduty_400(self):
        """pagerduty 400
        """

        self.pagerduty_setup(self._http_post_400)
        log_msg = self.log_queue.get(timeout=3)
        self.pagerduty_http_error(log_msg, "400")
        self.assertSentFinished()

    def test_pagerduty_403(self):
        """pagerduty 403
        """

        self.pagerduty_setup(self._http_post_403)
        log_msg = self.log_queue.get(timeout=3)
        self.pagerduty_http_error(log_msg, "403")
        self.assertSentFinished()

    def test_pagerduty_500(self):
        """pagerduty 500
        """

        self.pagerduty_setup(self._http_post_500)
        log_msg = self.log_queue.get(timeout=3)
        self.pagerduty_http_error(log_msg, "500")
        self.assertSentFinished()

    def test_pagerduty_504(self):
        """pagerduty 504
        """

        self.pagerduty_setup(self._http_post_504)
        log_msg = self.log_queue.get(timeout=3)
        self.pagerduty_http_error(log_msg, "504")
        self.assertSentFinished()

    def test_pagerduty_exception(self):
        """pagerduty exception
        """

        self.pagerduty_setup(self._http_post_exception)

        log_msg = self.log_queue.get(timeout=3)

        self.assertEqual(log_msg, "timeout 50")

        log_msg = self.log_queue.get(timeout=3)

        self.assertRegexpMatches(log_msg, "Exception on pagerduty request")
        self.assertRegexpMatches(log_msg, "key=<ABCDEF>")
        self.assertRegexpMatches(
            log_msg, "exception=<class 'requests.exceptions.Timeout'>")

        self.assertRaises(requests.exceptions.Timeout)
        self.assertSentFinished()
