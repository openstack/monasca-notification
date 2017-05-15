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

import mock

from monasca_notification.common.repositories.orm import orm_repo
from tests import base


class TestOrmRepo(base.BaseTestCase):

    @mock.patch('monasca_notification.common.repositories.orm.orm_repo.engine_from_config')
    def setUp(self, mock_sql_engine_from_config):
        super(TestOrmRepo, self).setUp()
        self.conf_default(
            group='orm', url='mysql+pymysql://user:password@hostname:3306/mon'
        )
        self._rep = orm_repo.OrmRepo()
        self.mock_conn = \
            self._rep._orm_engine.connect.return_value.__enter__.return_value

    def test_fetch_notifications_success(self):
        alarmdef_id = 'alarmdef-123'
        new_state = 'alarm'

        alarm = {'alarmDefinitionId': alarmdef_id,
                 'newState': new_state}
        self.mock_conn.execute.return_value = [('notification-123',
                                                'EMAIL',
                                                'notification-name',
                                                'testaddress',
                                                0)]

        self.assertEqual([('notification-123',
                           'email',
                           'notification-name',
                           'testaddress',
                           0)],
                         self._rep.fetch_notifications(alarm))

        self.mock_conn.execute.assert_called_once()
        self.assertEqual(self._rep._orm_query,
                         self.mock_conn.execute.call_args_list[0][0][0])
        self.assertEqual({'alarm_definition_id': alarmdef_id,
                          'alarm_state': new_state},
                         self.mock_conn.execute.call_args_list[0][1])

    def test_get_alarm_current_state_success(self):
        alarm_id = 'alarm-123'
        alarm_state = 'alarm'
        self.mock_conn.execute.return_value.fetchone.return_value = [alarm_state]

        self.assertEqual(self._rep.get_alarm_current_state(alarm_id), alarm_state)

        self.mock_conn.execute.assert_called_once()
        self.assertEqual(self._rep._orm_get_alarm_state,
                         self.mock_conn.execute.call_args_list[0][0][0])
        self.assertEqual({'alarm_id': alarm_id},
                         self.mock_conn.execute.call_args_list[0][1])

    def test_fetch_notification_method_types_success(self):
        notification_methods = [('EMAIL',), ('WEBHOOK',)]
        self.mock_conn.execute.return_value.fetchall.return_value = notification_methods

        self.assertEqual(self._rep.fetch_notification_method_types(), ['EMAIL', 'WEBHOOK'])

        self.mock_conn.execute.assert_called_once()
        self.assertEqual(self._rep._orm_nmt_query,
                         self.mock_conn.execute.call_args_list[0][0][0])

    def test_insert_notification_method_types_success(self):
        notification_types = ['SLACK', 'HIPCHAT', 'JIRA']
        self.mock_conn.execute.return_value = 1

        self._rep.insert_notification_method_types(notification_types)

        self.assertEqual(self._rep._orm_add_notification_type,
                         self.mock_conn.execute.call_args_list[0][0][0])
        self.assertEqual({'b_name': 'SLACK'},
                         self.mock_conn.execute.call_args_list[0][1])

    def test_get_notification_success(self):
        notification_id = 'notification-123'
        self.mock_conn.execute.return_value.fetchone.return_value = [
            'notification-123',
            'email',
            'notification-name',
            'testaddress',
            0]

        self.assertEqual(['notification-123',
                          'email',
                          'notification-name',
                          'testaddress'],
                         self._rep.get_notification(notification_id))

        self.mock_conn.execute.assert_called_once()
        self.assertEqual(self._rep._orm_get_notification,
                         self.mock_conn.execute.call_args_list[0][0][0])
        self.assertEqual({'notification_id': notification_id},
                         self.mock_conn.execute.call_args_list[0][1])
