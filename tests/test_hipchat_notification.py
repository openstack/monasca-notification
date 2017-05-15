# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import mock

import six

from monasca_notification import notification as m_notification
from monasca_notification.plugins import hipchat_notifier
from tests import base

if six.PY2:
    import Queue as queue
else:
    import queue


def alarm(metrics):
    return {"tenantId": "0",
            "alarmId": "0",
            "alarmDefinitionId": 0,
            "alarmName": "test Alarm",
            "alarmDescription": "test Alarm description",
            "oldState": "OK",
            "newState": "ALARM",
            "severity": "CRITICAL",
            "link": "some-link",
            "lifecycleState": "OPEN",
            "stateChangeReason": "I am alarming!",
            "timestamp": 1429023453632,
            "metrics": metrics}


class requestsResponse(object):
    def __init__(self, status):
        self.status_code = status


class TestHipchat(base.PluginTestCase):
    def setUp(self):
        super(TestHipchat, self).setUp(hipchat_notifier.register_opts)
        self.conf_default(group='hipchat_notifier', timeout=50)

        self.trap = queue.Queue()

    def tearDown(self):
        super(TestHipchat, self).tearDown()
        self.assertTrue(self.trap.empty())

    def _http_post_200(self, url, data, **kwargs):
        self.trap.put(url)
        self.trap.put(data)
        r = requestsResponse(200)
        return r

    @mock.patch('monasca_notification.plugins.hipchat_notifier.requests')
    def notify(self, http_func, mock_requests):
        mock_log = mock.MagicMock()
        mock_log.warn = self.trap.put
        mock_log.error = self.trap.put
        mock_log.exception = self.trap.put

        mock_requests.post = http_func

        hipchat = hipchat_notifier.HipChatNotifier(mock_log)

        hipchat.config()

        metric = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metric.append(metric_data)

        alarm_dict = alarm(metric)

        notification = m_notification.Notification(0, 'hipchat', 'hipchat notification',
                                                   'http://mock:3333/', 0, 0, alarm_dict)

        self.trap.put(hipchat.send_notification(notification))

    def test_hipchat_success(self):
        """hipchat success
        """
        self.notify(self._http_post_200)

        url = self.trap.get(timeout=1)
        data = self.trap.get(timeout=1)

        self.valid_hipchat_message(url, data)

        return_value = self.trap.get()
        self.assertTrue(return_value)

    def valid_hipchat_message(self, url, data):
        self.assertEqual(url, "http://mock:3333/")

        self.assertEqual(data.get('color'), 'red')
        self.assertEqual(data.get('message_format'), 'text')

        message = json.loads(data.get('message'))
        self.assertEqual(message.get('message'), 'I am alarming!')
        self.assertEqual(message.get('alarm_name'), 'test Alarm')
        self.assertEqual(message.get('alarm_description'), 'test Alarm description')
