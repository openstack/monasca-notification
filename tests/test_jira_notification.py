# Copyright 2017 FUJITSU LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing permissions and limitations under
# the License.

from unittest import mock

from monasca_notification import notification as m_notification
from monasca_notification.plugins import jira_notifier
import queue
from tests import base


def alarm():
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
            'metrics': {'dimension': {'hostname': 'foo1', 'service': 'bar1'}}}


def issue(component=True, custom_config=False):

    issue = {'fields': {'description': 'Monasca alarm',
                        'issuetype': {'name': 'Bug'},
                        'project': {'key': 'MyProject'},
                        'summary': 'Monasca alarm for alarm_defintion test Alarm status '
                                   'changed to ALARM for the alarm_id 0'}}
    if component:
        issue['fields'].update({'components': [{'name': 'MyComponent'}]})
    if custom_config:
        alarm_value = alarm()
        issue['fields'].update({'description': alarm_value.get('alarmName')})
        summary_format_string = 'Alarm created for {0} with severity {1} for {2}'
        summary = summary_format_string.format(alarm_value.get('alarmName'),
                                               alarm_value.get('newState'),
                                               alarm_value.get('alarmId'))
        issue['fields'].update({'summary': summary})
    return issue


class RequestsResponse(object):
    def __init__(self, status):
        self.status_code = status


class TestJira(base.PluginTestCase):

    default_address = 'http://test.jira:3333/?project=MyProject' \
                      '&component=MyComponent'
    default_transitions_value = [[{'id': 100, 'name': 'reopen'}]]
    issue_status_resolved = 'resolved'

    def setUp(self):
        super(TestJira, self).setUp(
            jira_notifier.register_opts
        )
        self.conf_override(
            group='jira_notifier',
            user='username',
            password='password'
        )

        self._trap = queue.Queue()

        mock_log = mock.Mock()
        mock_log.info = self._trap.put
        mock_log.debug = self._trap.put
        mock_log.warn = self._trap.put
        mock_log.error = self._trap.put
        mock_log.exception = self._trap.put

        self._jr = jira_notifier.JiraNotifier(mock_log)

    @mock.patch('monasca_notification.plugins.jira_notifier.jira')
    def _notify(self,
                transitions_value,
                issue_status,
                address,
                mock_jira):
        alarm_dict = alarm()

        mock_jira_obj = mock.Mock()
        mock_jira.JIRA.return_value = mock_jira_obj
        mock_jira_issue = mock.Mock()
        if issue_status:
            mock_jira_obj.search_issues.return_value = [mock_jira_issue]
            mock_jira_issue.fields.status.name = issue_status
        else:
            mock_jira_obj.search_issues.return_value = []
        mock_jira_obj.transitions.side_effect = transitions_value

        notification = m_notification.Notification(0, 'jira',
                                                   'jira notification',
                                                   address, 0, 0, alarm_dict)

        return mock_jira, mock_jira_obj, self._jr.send_notification(notification)

    def test_send_notification_issue_status_resolved(self):
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        TestJira.issue_status_resolved,
                                                        TestJira.default_address)
        self.assertTrue(result)
        mock_jira_obj.create_issue.assert_not_called()
        self.assertEqual(
            "project=MyProject and reporter='username' and summary ~ '0'",
            mock_jira_obj.search_issues.call_args[0][0])
        self.assertEqual(100, mock_jira_obj.transition_issue.call_args[0][1])

    def test_send_notification_issue_status_closed(self):
        issue_status = 'closed'
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        issue_status,
                                                        TestJira.default_address)
        self.assertTrue(result)
        mock_jira_obj.create_issue.assert_not_called()
        self.assertEqual(
            "project=MyProject and reporter='username' and summary ~ '0'",
            mock_jira_obj.search_issues.call_args[0][0])
        self.assertEqual(100, mock_jira_obj.transition_issue.call_args[0][1])

    def test_send_notification_issue_status_progress(self):
        issue_status = 'progress'
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        issue_status,
                                                        TestJira.default_address)
        self.assertTrue(result)
        mock_jira_obj.create_issue.assert_not_called()
        mock_jira_obj.transitions.assert_not_called()

    def test_send_notification_not_allow_transitions(self):
        transitions_value = [[{'id': 100, 'name': 'not open'}]]
        mock_jira, mock_jira_obj, result = self._notify(transitions_value,
                                                        TestJira.issue_status_resolved,
                                                        TestJira.default_address)
        self.assertTrue(result)
        mock_jira_obj.create_issue.assert_not_called()
        mock_jira_obj.transition_issue.assert_not_called()

    def test_send_notification_without_issue_list(self):
        issue_status = None
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        issue_status,
                                                        TestJira.default_address)
        self.assertTrue(result)
        mock_jira_obj.transitions.assert_not_called()
        self.assertEqual(issue(), mock_jira_obj.create_issue.call_args[1])

    def test_send_notification_without_componet(self):
        issue_status = None
        address = 'http://test.jira:3333/?project=MyProject'
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        issue_status,
                                                        address)
        self.assertTrue(result)
        self.assertEqual(issue(component=False), mock_jira_obj.create_issue.call_args[1])
        mock_jira_obj.transitions.assert_not_called()

    def test_send_notification_create_jira_object_args(self):
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        TestJira.issue_status_resolved,
                                                        TestJira.default_address)
        self.assertEqual('http://test.jira:3333/', mock_jira.JIRA.call_args[0][0])
        self.assertEqual(('username', 'password'), mock_jira.JIRA.call_args[1].get('basic_auth'))
        self.assertEqual(None, mock_jira.JIRA.call_args[1].get('proxies'))

    def test_send_notification_with_proxy(self):
        self.conf_override(
            proxy='http://yourid:password@proxyserver:8080',
            group='jira_notifier'
        )
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        TestJira.issue_status_resolved,
                                                        TestJira.default_address)
        self.assertTrue(result)
        self.assertEqual({'https': 'http://yourid:password@proxyserver:8080'},
                         mock_jira.JIRA.call_args[1].get('proxies'))

    def test_send_notification_custom_config_success(self):
        issue_status = None
        self.conf_override(
            custom_formatter='tests/resources/test_jiraformat.yml',
            group='jira_notifier'
        )
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        issue_status,
                                                        TestJira.default_address)
        self.assertTrue(result)
        mock_jira_obj.transitions.assert_not_called()
        self.assertEqual(issue(custom_config=True), mock_jira_obj.create_issue.call_args[1])

    def test_send_notification_custom_config_failed(self):
        self.conf_override(
            custom_formatter='tests/resources/test_jiraformat_without_summary.yml',
            group='jira_notifier'
        )
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        TestJira.issue_status_resolved,
                                                        TestJira.default_address)
        self.assertFalse(result)

    def test_send_notification_custom_config_without_comments(self):
        self.conf_override(
            custom_formatter='tests/resources/test_jiraformat_without_comments.yml',
            group='jira_notifier'
        )
        mock_jira, mock_jira_obj, result = self._notify(TestJira.default_transitions_value,
                                                        TestJira.issue_status_resolved,
                                                        TestJira.default_address)
        self.assertTrue(result)
        mock_jira_obj.add_comment.assert_not_called()

    def test_send_notification_custom_config_exception(self):
        self.conf_override(
            custom_formatter='tests/resources/not_exist_file.yml',
            group='jira_notifier'
        )
        self.assertRaises(Exception, self._notify,
                          TestJira.default_transitions_value,
                          TestJira.issue_status_resolved,
                          TestJira.default_address)

    def test_type(self):
        self.assertEqual('jira', self._jr.type)

    def test_statsd_name(self):
        self.assertEqual('jira_notifier', self._jr.statsd_name)
