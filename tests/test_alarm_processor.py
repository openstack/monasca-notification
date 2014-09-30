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

"""Tests the AlarmProcessor"""

import collections
import json
import mock
import multiprocessing
import Queue
import time
import unittest

from monasca_notification.notification import Notification
from monasca_notification.processors import alarm_processor

alarm_tuple = collections.namedtuple('alarm_tuple', ['offset', 'message'])
message_tuple = collections.namedtuple('message_tuple', ['value'])


class TestAlarmProcessor(unittest.TestCase):
    def setUp(self):
        self.alarm_queue = multiprocessing.Queue(10)
        self.notification_queue = multiprocessing.Queue(10)
        self.finished_queue = multiprocessing.Queue(10)
        self.log_queue = multiprocessing.Queue(10)

    def _create_raw_alarm(self, partition, offset, message):
        """Create a raw alarm, with the given message dictionary.
        """
        json_msg = json.dumps({'alarm-transitioned': message})
        msg_tuple = message_tuple(json_msg)
        return [partition, alarm_tuple(offset, msg_tuple)]

    @mock.patch('MySQLdb.connect')
    @mock.patch('monasca_notification.processors.alarm_processor.log')
    def _run_alarm_processor(self, queue, sql_response, mock_log, mock_mysql):
        """Runs a mocked alarm processor reading from queue while running, returns (queue_message, log_message)
        """
        # Since the log runs in another thread I can mock it directly, instead change the methods to put to a queue
        mock_log.warn = self.log_queue.put
        mock_log.error = self.log_queue.put

        # Setup the sql response
        if sql_response is not None:
            mock_mysql.return_value = mock_mysql
            mock_mysql.cursor.return_value = mock_mysql
            mock_mysql.__iter__.return_value = sql_response

        processor = alarm_processor.AlarmProcessor(self.alarm_queue, self.notification_queue,
                                                   self.finished_queue, 600, 'mysql_host', 'mysql_user',
                                                   'mysql_passwd', 'dbname')

        p_thread = multiprocessing.Process(target=processor.run)
        p_thread.start()
        try:
            queue_msg = queue.get(timeout=2)
        except Queue.Empty:
            queue_msg = None
        p_thread.terminate()

        try:
            log_msg = self.log_queue.get(timeout=1)
        except Queue.Empty:
            log_msg = None
        return queue_msg, log_msg

    def test_invalid_alarm(self):
        """Invalid Alarms, should log and error and push to the finished queue."""
        self.alarm_queue.put(self._create_raw_alarm(0, 1, {'invalid': 'invalid_alarm'}))
        finished, log_msg = self._run_alarm_processor(self.finished_queue, None)

        self.assertTrue(finished == (0, 1))
        self.assertTrue(log_msg.startswith('Invalid Alarm format'))

    def test_old_timestamp(self):
        """Should cause the alarm_ttl to fire log a warning and push to finished queue."""
        alarm_dict = {"tenantId": "0", "alarmDefinitionId": "0", "alarmId": "1", "alarmName": "test Alarm",
                      "oldState": "OK", "newState": "ALARM", "stateChangeReason": "I am alarming!",
                      "timestamp": 1375346830, "actionsEnabled": 1}
        self.alarm_queue.put(self._create_raw_alarm(0, 2, alarm_dict))
        finished, log_msg = self._run_alarm_processor(self.finished_queue, None)

        self.assertTrue(finished == (0, 2))
        self.assertTrue(log_msg.startswith('Received alarm older than the ttl'))

    def test_no_notifications(self):
        """Test an alarm with no defined notifications
        """
        alarm_dict = {"tenantId": "0", "alarmDefinitionId": "0", "alarmId": "1", "alarmName": "test Alarm",
                      "oldState": "OK", "newState": "ALARM", "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(), "actionsEnabled": 1}
        self.alarm_queue.put(self._create_raw_alarm(0, 3, alarm_dict))
        finished, log_msg = self._run_alarm_processor(self.finished_queue, None)

        self.assertTrue(finished == (0, 3))

    def test_valid_notification(self):
        """Test a valid notification, being put onto the notification_queue
        """
        alarm_dict = {"tenantId": "0", "alarmDefinitionId": "0", "alarmId": "1", "alarmName": "test Alarm",
                      "oldState": "OK", "newState": "ALARM", "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(), "actionsEnabled": 1}
        self.alarm_queue.put(self._create_raw_alarm(0, 4, alarm_dict))
        sql_response = [['test notification', 'EMAIL', 'me@here.com']]
        finished, log_msg = self._run_alarm_processor(self.notification_queue, sql_response)

        test_notification = Notification('email', 0, 4, 'test notification', 'me@here.com', alarm_dict)

        self.assertTrue(finished == [test_notification])

    def test_two_valid_notifications(self):
        alarm_dict = {"tenantId": "0", "alarmDefinitionId": "0", "alarmId": "1", "alarmName": "test Alarm",
                      "oldState": "OK", "newState": "ALARM", "stateChangeReason": "I am alarming!",
                      "timestamp": time.time(), "actionsEnabled": 1}
        self.alarm_queue.put(self._create_raw_alarm(0, 5, alarm_dict))
        sql_response = [['test notification', 'EMAIL', 'me@here.com'], ['test notification2', 'EMAIL', 'me@here.com']]
        finished, log_msg = self._run_alarm_processor(self.notification_queue, sql_response)

        test_notification = Notification('email', 0, 5, 'test notification', 'me@here.com', alarm_dict)
        test_notification2 = Notification('email', 0, 5, 'test notification2', 'me@here.com', alarm_dict)

        self.assertTrue(finished == [test_notification, test_notification2])
