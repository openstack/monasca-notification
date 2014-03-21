"""Tests the AlarmProcessor"""

import collections
import json
import mock
import multiprocessing
import unittest

from mon_notification.processors import alarm_processor

alarm_tuple = collections.namedtuple('alarm_tuple', ['offset', 'message'])

class TestAlarmProcessor(unittest.TestCase):
    def setUp(self):
        self.alarm_queue = multiprocessing.Queue(10)
        self.notification_queue = multiprocessing.Queue(10)
        self.finished_queue = multiprocessing.Queue(10)
        self.log_queue = multiprocessing.Queue(10)

    @mock.patch('MySQLdb.connect')
    @mock.patch('mon_notification.processors.alarm_processor.log')
    def test_invalid_alarm(self, mock_log, mock_mysql):
        """Invalid Alarms, should log and error and push to the finished queue"""
        mock_log.error = self.log_queue.put  # Since the log runs in another thread I can mock it directly
        processor = alarm_processor.AlarmProcessor(self.alarm_queue, self.notification_queue,
                                                   self.finished_queue, 10, 'mysql_host', 'mysql_user',
                                                   'mysql_passwd', 'dbname')

        message = json.dumps({'alarm-transitioned': {'invalid': 'bad threshold'}})
        invalid_alarm = [0, alarm_tuple(1, message)]
        self.alarm_queue.put(invalid_alarm)

        p_thread = multiprocessing.Process(target=processor.run)
        p_thread.start()
        finished = self.finished_queue.get(timeout=1)
        p_thread.terminate()

        self.assertTrue(finished == (0, 1))

        log_msg = self.log_queue.get(timeout=1)
        self.assertTrue(log_msg.startswith('Invalid Alarm format'))

