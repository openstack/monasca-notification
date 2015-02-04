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

import mock
import Queue
import requests
import time
import unittest

from monasca_notification.notification import Notification
from monasca_notification.types import webhook_notifier


def alarm(metrics):
    return {"tenantId": "0",
            "alarmId": "0",
            "alarmName": "test Alarm",
            "oldState": "OK",
            "newState": "ALARM",
            "stateChangeReason": "I am alarming!",
            "timestamp": time.time(),
            "metrics": metrics}


class requestsResponse(object):
    def __init__(self, status):
        self.status_code = status


class TestWebhook(unittest.TestCase):
    def setUp(self):
        self.trap = Queue.Queue()
        self.webhook_config = {'timeout': 50}

    def tearDown(self):
        self.assertTrue(self.trap.empty())

    def _http_post_200(self, url, data, headers, **kwargs):
        self.trap.put(url)
        self.trap.put(data)
        self.trap.put(headers)
        r = requestsResponse(200)
        return r

    def _http_post_404(self, url, data, headers, **kwargs):
        r = requestsResponse(404)
        return r

    def _http_post_exception(self, url, data, headers, **kwargs):
        self.trap.put("timeout %s" % kwargs["timeout"])
        raise requests.exceptions.Timeout

    @mock.patch('monasca_notification.types.webhook_notifier.requests')
    def notify(self, http_func, mock_requests):
        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.put
        mock_log.error = self.trap.put
        mock_log.exception = self.trap.put

        mock_requests.post = http_func

        webhook = webhook_notifier.WebhookNotifier(mock_log)

        webhook.config(self.webhook_config)

        metric = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metric.append(metric_data)

        alarm_dict = alarm(metric)

        notification = Notification('webhook', 0, 1, 'webhook notification', 'me@here.com', 0, alarm_dict)

        self.trap.put(webhook.send_notification(notification))

    def test_webhook_good_http_response(self):
        """webhook 200
        """
        self.notify(self._http_post_200)

        url = self.trap.get(timeout=1)
        data = self.trap.get(timeout=1)
        headers = self.trap.get(timeout=1)

        self.assertEqual(url, "me@here.com")
        self.assertEqual(data, {'alarm_id': '0'})
        self.assertEqual(headers, {'content-type': 'application/json'})

        return_value = self.trap.get()
        self.assertTrue(return_value)

    def test_webhook_bad_http_response(self):
        """webhook bad response
        """

        self.notify(self._http_post_404)

        error = self.trap.get()

        self.assertNotRegexpMatches(error, "alarm_id.: .test Alarm")
        self.assertNotRegexpMatches(error, "content-type.: .application/json")

        self.assertRegexpMatches(error, "HTTP code 404")
        self.assertRegexpMatches(error, "post on URL me@here.com")

        return_value = self.trap.get()
        self.assertFalse(return_value)

    def test_webhook_timeout_exception_on_http_response(self):
        """webhook timeout exception
        """

        self.notify(self._http_post_exception)

        result = self.trap.get()

        self.assertEqual(result, "timeout 50")

        result = self.trap.get()

        self.assertNotRegexpMatches(result, "alarm_id.: .test Alarm")
        self.assertNotRegexpMatches(result, "content-type.: .application/json")

        self.assertRegexpMatches(result, "Error trying to post on URL me@here")
        self.assertRaises(requests.exceptions.Timeout)

        return_value = self.trap.get()
        self.assertFalse(return_value)
