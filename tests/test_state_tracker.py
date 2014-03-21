"""Tests the StateTracker"""

import mock
import multiprocessing
import threading
import time
import unittest

from mon_notification import state_tracker


class TestStateTracker(unittest.TestCase):
    def setUp(self):
        self.finished_queue = multiprocessing.Queue(10)
        with mock.patch('kazoo.client.KazooClient') as self.mock_zk:
            self.mock_zk.return_value = self.mock_zk
            self.tracker = state_tracker.ZookeeperStateTracker('url', 'topic', self.finished_queue, 1)
        self.tracker.has_lock = True
        self.tracker_thread = threading.Thread(target=self.tracker.run)
        self.tracker_thread.daemon = True  # needed for the thread to properly exit

    def _feed_queue(self, test_list):
        """Feed the queue and start the state tracker.
        """
        for item in test_list:
            self.finished_queue.put(item)

        self.tracker._offsets = {item[0]: 0 for item in test_list}
        self.tracker_thread.start()
        time.sleep(1)

    def test_ordered(self):
        """Test a series of ordered finished offsets to make sure they are updated correctly
        """
        test_list = [(0, 1), (0, 2), (1, 1), (1, 2)]
        self._feed_queue(test_list)

        expected_calls = [mock.call.set('/'.join([self.tracker.topic_path, str(partition)]), str(value))
                          for partition, value in test_list]
        set_calls = [call for call in self.mock_zk.mock_calls if call.__str__().startswith('call.set')]

        self.assertTrue(expected_calls == set_calls)

    def test_unordered(self):
        """Test a series of unordered finished offsets to make sure they are updated in order
        """
        unordered_test_list = [(0, 2), (0, 1), (1, 2), (1, 1)]
        self._feed_queue(unordered_test_list)

        commit_list = [(0, 2), (1, 2)]
        expected_calls = [mock.call.set('/'.join([self.tracker.topic_path, str(partition)]), str(value))
                          for partition, value in commit_list]
        set_calls = [call for call in self.mock_zk.mock_calls if call.__str__().startswith('call.set')]

        self.assertTrue(expected_calls == set_calls)

    def test_unordered_with_lag(self):
        """Test a series of unordered finished offsets with lag being received
        """
        unordered_quick = [(0, 2), (1, 2)]
        self._feed_queue(unordered_quick)

        time.sleep(1)  # sleep the lag period. and feed more
        unordered_slow = [(0, 3), (1, 3)]
        for item in unordered_slow:
            self.finished_queue.put(item)

        time.sleep(1)  # wait for processing

        commit_list = [(0, 3), (1, 3)]
        expected_calls = [mock.call.set('/'.join([self.tracker.topic_path, str(partition)]), str(value))
                          for partition, value in commit_list]
        set_calls = [call for call in self.mock_zk.mock_calls if call.__str__().startswith('call.set')]

        self.assertTrue(expected_calls == set_calls)
