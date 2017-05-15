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
from monasca_notification.plugins import slack_notifier
from tests import base

if six.PY2:
    import Queue as queue
else:
    import queue


def alarm(metrics):
    return {'tenantId': '0',
            'alarmId': '0',
            'alarmDefinitionId': 0,
            'alarmName': 'test Alarm',
            'alarmDescription': 'test Alarm description',
            'oldState': 'OK',
            'newState': 'ALARM',
            'severity': 'CRITICAL',
            'link': 'some-link',
            'lifecycleState': 'OPEN',
            'stateChangeReason': 'I am alarming!',
            'timestamp': 1429023453632,
            'metrics': metrics}


def slack_text():
    return {'old_state': 'OK',
            'alarm_description': 'test Alarm description',
            'message': 'I am alarming!',
            'alarm_definition_id': 0,
            'alarm_name': 'test Alarm',
            'tenant_id': '0',
            'metrics': [
                {'dimensions': {
                    'hostname': 'foo1',
                    'service': 'bar1'}}
            ],
            'alarm_id': '0',
            'state': 'ALARM',
            'alarm_timestamp': 1429023453}


class RequestsResponse(object):
    def __init__(self, status, text, headers):
        self.status_code = status
        self.text = text
        self.headers = headers

    def json(self):
        return json.loads(self.text)


class TestSlack(base.PluginTestCase):

    def setUp(self):
        super(TestSlack, self).setUp(
            slack_notifier.register_opts
        )
        self.conf_default(group='slack_notifier', timeout=50,
                          ca_certs='/etc/ssl/certs/ca-bundle.crt',
                          proxy='http://yourid:password@proxyserver:8080',
                          insecure=False)

        self._trap = queue.Queue()

        mock_log = mock.Mock()
        mock_log.info = self._trap.put
        mock_log.warn = self._trap.put
        mock_log.error = self._trap.put
        mock_log.exception = self._trap.put

        self._slk = slack_notifier.SlackNotifier(mock_log)
        slack_notifier.SlackNotifier._raw_data_url_caches = []

    @mock.patch('monasca_notification.plugins.slack_notifier.requests')
    def _notify(self, response_list, mock_requests):
        mock_requests.post = mock.Mock(side_effect=response_list)

        metric = []
        metric_data = {'dimensions': {'hostname': 'foo1', 'service': 'bar1'}}
        metric.append(metric_data)

        alarm_dict = alarm(metric)

        notification = m_notification.Notification(0, 'slack', 'slack notification',
                                                   'http://test.slack:3333', 0, 0,
                                                   alarm_dict)

        return mock_requests.post, self._slk.send_notification(notification)

    def _validate_post_args(self, post_args, data_format):
        self.assertEqual(slack_text(),
                         json.loads(post_args.get(data_format).get('text')))
        self.assertEqual({'https': 'http://yourid:password@proxyserver:8080'},
                         post_args.get('proxies'))
        self.assertEqual(50, post_args.get('timeout'))
        self.assertEqual('http://test.slack:3333', post_args.get('url'))
        self.assertEqual('/etc/ssl/certs/ca-bundle.crt',
                         post_args.get('verify'))

    def test_slack_webhook_success(self):
        """slack success
        """
        response_list = [RequestsResponse(200, 'ok',
                                          {'Content-Type': 'application/text'})]
        mock_method, result = self._notify(response_list)
        self.assertTrue(result)
        mock_method.assert_called_once()
        self._validate_post_args(mock_method.call_args_list[0][1], 'json')
        self.assertEqual([], slack_notifier.SlackNotifier._raw_data_url_caches)

    def test_slack_webhook_fail(self):
        """data is sent twice as json and raw data, and slack returns failure for
           both requests
        """
        response_list = [RequestsResponse(200, 'failure',
                                          {'Content-Type': 'application/text'}),
                         RequestsResponse(200, '{"ok":false,"error":"failure"}',
                                          {'Content-Type': 'application/json'})]
        mock_method, result = self._notify(response_list)
        self.assertFalse(result)
        self._validate_post_args(mock_method.call_args_list[0][1], 'json')
        self._validate_post_args(mock_method.call_args_list[1][1], 'data')
        self.assertEqual([], slack_notifier.SlackNotifier._raw_data_url_caches)

    def test_slack_post_message_success_no_cache(self):
        """data is sent as json at first and get error, second it's sent as raw data
        """
        response_list = [RequestsResponse(200, '{"ok":false,"error":"failure"}',
                                          {'Content-Type': 'application/json'}),
                         RequestsResponse(200, '{"ok":true}',
                                          {'Content-Type': 'application/json'})]
        mock_method, result = self._notify(response_list)
        self.assertTrue(result)
        self._validate_post_args(mock_method.call_args_list[0][1], 'json')
        self._validate_post_args(mock_method.call_args_list[1][1], 'data')
        self.assertEqual(['http://test.slack:3333'],
                         slack_notifier.SlackNotifier._raw_data_url_caches)

    def test_slack_post_message_success_cached(self):
        """url in cache and data is sent as raw data at first time
        """
        with mock.patch.object(slack_notifier.SlackNotifier,
                               '_raw_data_url_caches',
                               ['http://test.slack:3333']):
            response_list = [RequestsResponse(200, '{"ok":true}',
                                              {'Content-Type': 'application/json'})]
            mock_method, result = self._notify(response_list)
            self.assertTrue(result)
            mock_method.assert_called_once()
            self._validate_post_args(mock_method.call_args_list[0][1], 'data')
            self.assertEqual(['http://test.slack:3333'],
                             slack_notifier.SlackNotifier._raw_data_url_caches)

    def test_slack_post_message_failed_cached(self):
        """url in cache and slack returns failure
        """
        with mock.patch.object(slack_notifier.SlackNotifier,
                               '_raw_data_url_caches',
                               ['http://test.slack:3333']):
            response_list = [RequestsResponse(200, '{"ok":false,"error":"failure"}',
                                              {'Content-Type': 'application/json'})]
            mock_method, result = self._notify(response_list)
            self.assertFalse(result)
            mock_method.assert_called_once()
            self._validate_post_args(mock_method.call_args_list[0][1], 'data')
            self.assertEqual(['http://test.slack:3333'],
                             slack_notifier.SlackNotifier._raw_data_url_caches)

    def test_slack_webhook_success_only_timeout(self):
        """slack success with only timeout config
        """
        self.conf_override(group='slack_notifier', timeout=50,
                           insecure=True, ca_certs=None,
                           proxy=None)

        response_list = [RequestsResponse(200, 'ok',
                                          {'Content-Type': 'application/text'})]
        mock_method, result = self._notify(response_list)
        self.assertTrue(result)
        mock_method.assert_called_once()
        self.assertEqual(slack_notifier.SlackNotifier._raw_data_url_caches, [])

        post_args = mock_method.call_args_list[0][1]
        self.assertEqual(slack_text(),
                         json.loads(post_args.get('json').get('text')))
        self.assertEqual(None, post_args.get('proxies'))
        self.assertEqual(50, post_args.get('timeout'))
        self.assertEqual('http://test.slack:3333', post_args.get('url'))
        self.assertFalse(post_args.get('verify'))

    def test_slack_reponse_400(self):
        """slack returns 400 error
        """
        response_list = [RequestsResponse(400, '{"ok":false,"error":"failure"}',
                                          {'Content-Type': 'application/json'}),
                         RequestsResponse(400, '{"ok":false,"error":"failure"}',
                                          {'Content-Type': 'application/json'})]
        mock_method, result = self._notify(response_list)
        self.assertFalse(result)

        self._validate_post_args(mock_method.call_args_list[0][1], 'json')
        self._validate_post_args(mock_method.call_args_list[1][1], 'data')

    def test_slack_post_message_success_cache_full(self):
        """url in cache and data is sent as raw data at first time
        """
        dummy_cache = [d for d in range(0, 100)]
        with mock.patch.object(slack_notifier.SlackNotifier,
                               '_raw_data_url_caches',
                               dummy_cache):
            response_list = [RequestsResponse(200, '{"ok":false,"error":"failure"}',
                                              {'Content-Type': 'application/json'}),
                             RequestsResponse(200, '{"ok":true}',
                                              {'Content-Type': 'application/json'})]
            mock_method, result = self._notify(response_list)
            self.assertTrue(result)
            self._validate_post_args(mock_method.call_args_list[0][1], 'json')
            self._validate_post_args(mock_method.call_args_list[1][1], 'data')
            self.assertEqual(dummy_cache,
                             slack_notifier.SlackNotifier._raw_data_url_caches)

    def test_config_insecure_true_ca_certs(self):
        self.conf_override(group='slack_notifier', timeout=50,
                           insecure=True,
                           ca_certs='/etc/ssl/certs/ca-bundle.crt')

        response_list = [RequestsResponse(200, 'ok',
                                          {'Content-Type': 'application/text'})]

        mock_method, result = self._notify(response_list)
        self.assertTrue(result)
        mock_method.assert_called_once()
        self.assertEqual(slack_notifier.SlackNotifier._raw_data_url_caches, [])
        post_args = mock_method.call_args_list[0][1]
        self.assertEqual(slack_text(),
                         json.loads(post_args.get('json').get('text')))
        self.assertEqual(50, post_args.get('timeout'))
        self.assertEqual('http://test.slack:3333', post_args.get('url'))
        self.assertEqual('/etc/ssl/certs/ca-bundle.crt', post_args.get('verify'))

    def test_config_insecure_true_no_ca_certs(self):
        self.conf_override(group='slack_notifier', timeout=50,
                           insecure=True,
                           ca_certs=None)

        response_list = [RequestsResponse(200, 'ok',
                                          {'Content-Type': 'application/text'})]

        mock_method, result = self._notify(response_list)
        self.assertTrue(result)
        mock_method.assert_called_once()
        self.assertEqual(slack_notifier.SlackNotifier._raw_data_url_caches, [])
        post_args = mock_method.call_args_list[0][1]
        self.assertEqual(slack_text(),
                         json.loads(post_args.get('json').get('text')))
        self.assertEqual(50, post_args.get('timeout'))
        self.assertEqual('http://test.slack:3333', post_args.get('url'))
        self.assertFalse(post_args.get('verify'))

    def test_config_insecure_false_no_ca_certs(self):
        self.conf_override(group='slack_notifier', timeout=50,
                           insecure=False,
                           ca_certs=None)

        response_list = [RequestsResponse(200, 'ok',
                                          {'Content-Type': 'application/text'})]

        mock_method, result = self._notify(response_list)
        self.assertTrue(result)
        mock_method.assert_called_once()
        self.assertEqual(slack_notifier.SlackNotifier._raw_data_url_caches, [])
        post_args = mock_method.call_args_list[0][1]
        self.assertEqual(slack_text(),
                         json.loads(post_args.get('json').get('text')))
        self.assertEqual(50, post_args.get('timeout'))
        self.assertEqual('http://test.slack:3333', post_args.get('url'))
        self.assertTrue(post_args.get('verify'))
