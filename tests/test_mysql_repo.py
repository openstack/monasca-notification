# (C) Copyright 2015 Hewlett Packard Enterprise Development LP
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
import unittest

import pymysql

from monasca_notification.common.repositories import exceptions as exc
from monasca_notification.common.repositories.mysql import mysql_repo


class TestMySqlRepo(unittest.TestCase):
    @mock.patch('monasca_notification.common.repositories.mysql.mysql_repo.pymysql')
    def testReconnect(self, mock_mysql):
        m = mock.MagicMock()

        m.cursor.side_effect = pymysql.Error

        mock_mysql.connect.return_value = m
        mock_mysql.Error = pymysql.Error

        config = {'mysql': {'host': 'foo',
                            'port': '3306',
                            'user': 'bar',
                            'passwd': '1',
                            'db': '2'}}

        repo = mysql_repo.MysqlRepo(config)

        alarm = {'alarmDefinitionId': 'foo',
                 'newState': 'bar'}

        def get_notification(repo, alarm):
            g = repo.fetch_notifications(alarm)
            for x in g:
                pass

        try:
            get_notification(repo, alarm)
        except exc.DatabaseException:
            try:
                get_notification(repo, alarm)
            except Exception:
                pass

        self.assertEqual(mock_mysql.connect.call_count, 2)
