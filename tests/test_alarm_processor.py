# (C) Copyright 2014-2016 Hewlett Packard Enterprise Development LP
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

"""Tests the AlarmProcessor"""

import collections
import json
import time
from unittest import mock

from monasca_common.kafka import legacy_kafka_message

from monasca_notification import notification as m_notification
from monasca_notification.processors import alarm_processor

from tests import base

alarm_tuple = collections.namedtuple('alarm_tuple', ['offset', 'message'])
message_tuple = collections.namedtuple('message_tuple', ['key', 'value'])


class TestAlarmProcessor(base.BaseTestCase):
    def setUp(self):
        super(TestAlarmProcessor, self).setUp()
        self.trap = []

    def _create_raw_alarm(self, partition, offset, message, key=1):
        """Create a raw alarm, with the given message dictionary.
        """
        json_msg = json.dumps({'alarm-transitioned': message})
        msg_tuple = message_tuple(key, json_msg)
        return legacy_kafka_message.LegacyKafkaMessage([partition,
                                                        alarm_tuple(offset,
                                                                    msg_tuple)])

    @mock.patch('pymysql.connect')
    @mock.patch('monasca_notification.processors.alarm_processor.log')
    def _run_alarm_processor(self, alarm, sql_response, mock_log, mock_mysql):
        """Runs a mocked alarm processor reading from queue while running,
        returns (queue_message, log_message)
        """
        # Since the log runs in another thread I can mock it directly, instead
        # change the methods to put to a queue
        mock_log.warn = self.trap.append
        mock_log.error = self.trap.append
        mock_log.exception = self.trap.append

        # Setup the sql response
        if sql_response is not None:
            mock_mysql.return_value = mock_mysql
            mock_mysql.cursor.return_value = mock_mysql
            mock_mysql.__iter__.return_value = sql_response

        self.conf_override(group='mysql', ssl=None,
                           host='localhost', port='3306',
                           user='mysql_user', db='dbname',
                           passwd='mysql_passwd')
        self.conf_override(group='statsd', host='localhost',
                           port=8125)
        processor = alarm_processor.AlarmProcessor()

        return processor.to_notification(alarm)

    def test_invalid_alarm(self):
        """Invalid Alarms, should log and error and push to the finished queue."""
        alarm = self._create_raw_alarm(0, 1, {'invalid': 'invalid_alarm'})
        notifications, partition, offset = self._run_alarm_processor(alarm, None)
        self.assertEqual(notifications, [])
        self.assertEqual(partition, 0)
        self.assertEqual(offset, 1)

        invalid_msg = ('Invalid Alarm format skipping partition 0, offset 1\n'
                       'ErrorAlarm data missing field actionsEnabled')

        self.assertIn(invalid_msg, self.trap)

    def test_old_timestamp(self):
        """Should cause the alarm_ttl to fire log a warning and push to finished queue."""
        timestamp = 1375346830042
        alarm_dict = {
            "tenantId": "0",
            "alarmDefinitionId": "0",
            "alarmId": "1",
            "alarmName": "test Alarm",
            "oldState": "OK",
            "newState": "ALARM",
            "stateChangeReason": "I am alarming!",
            "timestamp": timestamp,
            "actionsEnabled": 1,
            "metrics": "cpu_util",
            "severity": "LOW",
            "link": "http://some-place.com",
            "lifecycleState": "OPEN"}
        alarm = self._create_raw_alarm(0, 2, alarm_dict)
        expected_datetime = time.ctime(timestamp / 1000)

        notifications, partition, offset = self._run_alarm_processor(alarm, None)

        self.assertEqual(notifications, [])
        self.assertEqual(partition, 0)
        self.assertEqual(offset, 2)

        old_msg = ('Received alarm older than the ttl, skipping. '
                   'Alarm from {datetime}'.format(datetime=expected_datetime))

        self.assertIn(old_msg, self.trap)

    def test_no_notifications(self):
        """Test an alarm with no defined notifications
        """
        alarm_dict = {
            "tenantId": "0",
            "alarmDefinitionId": "0",
            "alarmId": "1",
            "alarmName": "test Alarm",
            "oldState": "OK",
            "newState": "ALARM",
            "stateChangeReason": "I am alarming!",
            "timestamp": time.time() * 1000,
            "actionsEnabled": 1,
            "metrics": "cpu_util",
            "severity": "LOW",
            "link": "http://some-place.com",
            "lifecycleState": "OPEN"}
        alarm = self._create_raw_alarm(0, 3, alarm_dict)

        notifications, partition, offset = self._run_alarm_processor(alarm, None)

        self.assertEqual(notifications, [])
        self.assertEqual(partition, 0)
        self.assertEqual(offset, 3)

    def test_valid_notification(self):
        """Test a valid notification, being put onto the notification_queue
        """
        alarm_dict = {
            "tenantId": "0",
            "alarmDefinitionId": "0",
            "alarmId": "1",
            "alarmName": "test Alarm",
            "oldState": "OK",
            "newState": "ALARM",
            "stateChangeReason": "I am alarming!",
            "timestamp": time.time() * 1000,
            "actionsEnabled": 1,
            "metrics": "cpu_util",
            "severity": "LOW",
            "link": "http://some-place.com",
            "lifecycleState": "OPEN"}
        alarm = self._create_raw_alarm(0, 4, alarm_dict)

        sql_response = [[1, 'EMAIL', 'test notification', 'me@here.com', 0]]
        notifications, partition, offset = self._run_alarm_processor(alarm, sql_response)

        test_notification = m_notification.Notification(1, 'email', 'test notification',
                                                        'me@here.com', 0, 0, alarm_dict)

        self.assertEqual(notifications, [test_notification])
        self.assertEqual(partition, 0)
        self.assertEqual(offset, 4)

    def test_two_valid_notifications(self):
        alarm_dict = {
            "tenantId": "0",
            "alarmDefinitionId": "0",
            "alarmId": "1",
            "alarmName": "test Alarm",
            "oldState": "OK",
            "newState": "ALARM",
            "stateChangeReason": "I am alarming!",
            "timestamp": time.time() * 1000,
            "actionsEnabled": 1,
            "metrics": "cpu_util",
            "severity": "LOW",
            "link": "http://some-place.com",
            "lifecycleState": "OPEN"}

        alarm = self._create_raw_alarm(0, 5, alarm_dict)

        sql_response = [[1, 'EMAIL', 'test notification', 'me@here.com', 0],
                        [2, 'EMAIL', 'test notification2', 'me@here.com', 0]]
        notifications, partition, offset = self._run_alarm_processor(alarm, sql_response)

        test_notification = m_notification.Notification(1, 'email', 'test notification',
                                                        'me@here.com', 0, 0, alarm_dict)
        test_notification2 = m_notification.Notification(2, 'email', 'test notification2',
                                                         'me@here.com', 0, 0, alarm_dict)

        self.assertEqual(notifications, [test_notification, test_notification2])
        self.assertEqual(partition, 0)
        self.assertEqual(offset, 5)
