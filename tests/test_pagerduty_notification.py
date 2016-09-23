# (C) Copyright 2014-2016 Hewlett Packard Enterprise Development LP
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

import json
import mock
import Queue
import requests
import time
import unittest

from monasca_notification import notification as m_notification
from monasca_notification.plugins import pagerduty_notifier


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


class requestsResponse(object):
    def __init__(self, status):
        self.status_code = status


class TestWebhook(unittest.TestCase):
    def setUp(self):
        self.trap = Queue.Queue()
        self.pagerduty_config = {'timeout': 50, 'key': 'foobar'}

    def tearDown(self):
        self.assertTrue(self.trap.empty())

    def _http_post_200(self, url, data, headers, **kwargs):
        self.trap.put(url)
        self.trap.put(data)
        self.trap.put(headers)
        r = requestsResponse(200)
        return r

    def _http_post_201(self, url, data, headers, **kwargs):
        self.trap.put(url)
        self.trap.put(data)
        self.trap.put(headers)
        r = requestsResponse(201)
        return r

    def _http_post_202(self, url, data, headers, **kwargs):
        r = requestsResponse(202)
        return r

    def _http_post_204(self, url, data, headers, **kwargs):
        self.trap.put(url)
        self.trap.put(data)
        self.trap.put(headers)
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
        self.trap.put("timeout %s" % kwargs["timeout"])
        raise requests.exceptions.Timeout

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

    @mock.patch('monasca_notification.plugins.pagerduty_notifier.requests')
    def notify(self, http_func, mock_requests):
        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.put
        mock_log.error = self.trap.put
        mock_log.exception = self.trap.put

        mock_requests.post = http_func

        pagerduty = pagerduty_notifier.PagerdutyNotifier(mock_log)

        pagerduty.config(self.pagerduty_config)

        metric = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metric.append(metric_data)

        alarm_dict = alarm(metric)

        notification = m_notification.Notification(0,
                                                   'pagerduty',
                                                   'pagerduty notification',
                                                   'ABCDEF',
                                                   0,
                                                   0,
                                                   alarm_dict)

        self.trap.put(pagerduty.send_notification(notification))

    def test_pagerduty_200(self):
        """pagerduty 200
        """

        self.notify(self._http_post_200)

        url = self.trap.get(timeout=1)
        data = self.trap.get(timeout=1)
        headers = self.trap.get(timeout=1)

        self.valid_pagerduty_message(url, data, headers)

        return_value = self.trap.get()
        self.assertTrue(return_value)

    def test_pagerduty_201(self):
        """pagerduty 201
        """

        self.notify(self._http_post_201)

        url = self.trap.get(timeout=1)
        data = self.trap.get(timeout=1)
        headers = self.trap.get(timeout=1)

        self.valid_pagerduty_message(url, data, headers)

        return_value = self.trap.get()
        self.assertTrue(return_value)

    def test_pagerduty_204(self):
        """pagerduty 204
        """

        self.notify(self._http_post_204)

        url = self.trap.get(timeout=1)
        data = self.trap.get(timeout=1)
        headers = self.trap.get(timeout=1)

        self.valid_pagerduty_message(url, data, headers)

        return_value = self.trap.get()
        self.assertTrue(return_value)

    def test_pagerduty_202(self):
        """pagerduty 202
        """

        self.notify(self._http_post_202)
        results = self.trap.get(timeout=1)
        self.pagerduty_http_error(results, "202")

        return_value = self.trap.get()
        self.assertFalse(return_value)

    def test_pagerduty_400(self):
        """pagerduty 400
        """

        self.notify(self._http_post_400)
        results = self.trap.get(timeout=1)
        self.pagerduty_http_error(results, "400")

        return_value = self.trap.get()
        self.assertFalse(return_value)

    def test_pagerduty_403(self):
        """pagerduty 403
        """

        self.notify(self._http_post_403)
        results = self.trap.get(timeout=1)
        self.pagerduty_http_error(results, "403")

        return_value = self.trap.get()
        self.assertFalse(return_value)

    def test_pagerduty_500(self):
        """pagerduty 500
        """

        self.notify(self._http_post_500)
        results = self.trap.get(timeout=1)
        self.pagerduty_http_error(results, "500")

        return_value = self.trap.get()
        self.assertFalse(return_value)

    def test_pagerduty_504(self):
        """pagerduty 504
        """

        self.notify(self._http_post_504)
        results = self.trap.get(timeout=1)
        self.pagerduty_http_error(results, "504")

        return_value = self.trap.get()
        self.assertFalse(return_value)

    def test_pagerduty_exception(self):
        """pagerduty exception
        """

        self.notify(self._http_post_exception)

        results = self.trap.get(timeout=1)

        self.assertEqual(results, "timeout 50")

        results = self.trap.get(timeout=1)

        self.assertRegexpMatches(results, "Exception on pagerduty request")
        self.assertRegexpMatches(results, "key=<ABCDEF>")

        self.assertRaises(requests.exceptions.Timeout)

        return_value = self.trap.get()
        self.assertFalse(return_value)
