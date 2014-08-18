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

import collections
import kafka.client
import kafka.common
import kazoo.client
import kazoo.exceptions
import logging
import Queue
import statsd
import time

from monasca_notification import notification_exceptions

log = logging.getLogger(__name__)


class KafkaStateTracker(object):
    """Tracks message offsets for a kafka topic and partitions.
         As messages are finished with processing the committed offset is updated periodically.
         The messages are not necessarily finished in order, but the committed offset includes
         all previous messages so this object tracks any gaps updating as needed.
         Uses zookeeper to keep track of the last committed offset.
    """
    def __init__(self, finished_queue, kafka_url, group, topic, max_lag, zookeeper_url):
        """Setup the finished_queue
             finished_queue - queue containing all processed alarms
             kafka_url, group, topic - kafka connection details
             zookeeper_url is the zookeeper hostname:port
        """
        self.finished_queue = finished_queue
        self.max_lag = max_lag
        self.topic = topic
        self.has_lock = False
        self.stop = False

        # The kafka client is used solely for committing offsets, the consuming is done in the kafka_consumer
        self.kafka_group = group
        self.kafka = kafka.client.KafkaClient(kafka_url)
        # The consumer is not needed but after my pull request is merged using it for get_offsets simplifies this code
        # import kafka.consumer
        # self.consumer = kafka.consumer.SimpleConsumer(self.kafka, group, topic, auto_commit=False)

        self.zookeeper = kazoo.client.KazooClient(zookeeper_url)
        self.zookeeper.start()

        self.lock_retry_time = 15  # number of seconds to wait for retrying for the lock
        self.lock_path = '/locks/monasca-notification/%s' % topic

        self._offsets = None  # Initialized in the beginning of the run
        # This is a dictionary of sets used for tracking finished offsets when there is a gap and the committed offset
        # can not yet be advanced
        self._uncommitted_offsets = collections.defaultdict(set)
        self._last_commit_time = collections.defaultdict(time.time)

        self.zk_timer = statsd.Timer('OffsetCommitTime')
        self.offset_update_count = statsd.Counter('AlarmsOffsetUpdated')

    def _drop_lock(self):
        """Drop the lock file kept in zookeeper
             This should only ever be run when all processing of the finished queue has completed.
        """
        if self.zookeeper.exists(self.lock_path):
            self.zookeeper.delete(self.lock_path)
        self.has_lock = False

    def lock(self, exit_method):
        """Grab a lock within zookeeper, if not available retry.
        """
        while True:
            # The path is ephemeral so if it exists wait then cycle again
            if self.zookeeper.exists(self.lock_path):
                log.info('Another process has the lock for topic %s, waiting then retrying.' % self.topic)
                time.sleep(self.lock_retry_time)
                continue

            try:
                self.zookeeper.create(self.lock_path, ephemeral=True, makepath=True)
            except kazoo.exceptions.KazooException as e:
                # If creating the path fails something beat us to it most likely, try again
                log.warn('Error creating lock path %s\n%s' % (self.lock_path, e))
                continue
            else:
                # Succeeded in grabbing the lock continue
                log.info('Grabbed lock for topic %s' % self.topic)
                self.has_lock = True
                break

        # Set up a listener to exit if we lose connection, this always exits even if the zookeeper connection is only
        # suspended, the process should be supervised so it starts right back up again.
        self.zookeeper.add_listener(exit_method)

    @property
    def offsets(self):
        """Return self._offsets, this is a property because generally only initialize the offsets after the lock has
            been pulled
        """
        if not self.has_lock:
            log.warn('Reading offsets before the tracker has the lock, they could change')

        if self._offsets is None:
            # After my pull request is merged I can setup self.consumer as is done in kafka_consumer
            # then simply use the get_offsets command as below
            # self._offsets = self.consumer.get_offsets()
            self._offsets = {}

            def get_or_init_offset_callback(resp):
                try:
                    kafka.common.check_error(resp)
                    return resp.offset
                except kafka.common.UnknownTopicOrPartitionError:
                    return 0
            for partition in self.kafka.topic_partitions[self.topic]:
                req = kafka.common.OffsetFetchRequest(self.topic, partition)
                (offset,) = self.kafka.send_offset_fetch_request(self.kafka_group, [req],
                                                                 callback=get_or_init_offset_callback,
                                                                 fail_on_error=False)
                self._offsets[partition] = offset

        return self._offsets

    def run(self):
        """Mark a message as finished and where possible commit the new offset to zookeeper.
             There is no mechanism here to deal with the situation where a single alarm is extremely slow to finish
             holding up all others behind it. It is assumed the notification will time out allowing things to finish.
        """
        if not self.has_lock:
            raise notification_exceptions.NotificationException('Attempt to begin run without Zookeeper Lock')

        finished_count = statsd.Counter('AlarmsFinished')
        while True:
            # If self.stop is True run the queue until it is empty, do final commits then exit
            if self.stop and self.finished_queue.empty():
                log.debug('self.stop set and the finished_queue is empty, doing final wait')
                time.sleep(10)  # Before final exit wait a bit to verify the queue is still empty
                if self.finished_queue.empty():
                    if self.max_lag is not None:
                        # if the max_lag has been hit at this point commit the last received offset
                        for partition in self._last_commit_time.iterkeys():
                            if ((time.time() - self._last_commit_time[partition]) > self.max_lag) and\
                                    (len(self._uncommitted_offsets[partition]) > 0):
                                log.error('Max Lag has been reached! Skipping offsets for partition %s' % partition)
                                self.update_offset(partition, max(self._uncommitted_offsets[partition]))
                    break

            try:
                msg = self.finished_queue.get(timeout=10)
            except Queue.Empty:
                continue  # This is non-blocking so the self.stop signal has a chance to take affect

            finished_count += 1
            partition = int(msg[0])
            offset = int(msg[1])

            log.debug('Received commit finish for partition %d, offset %d' % (partition, offset))
            # Update immediately if the offset is 1 above current offset
            if self.offsets[partition] == offset - 1:

                new_offset = offset
                for x in range(offset + 1, offset + 1 + len(self._uncommitted_offsets[partition])):
                    if x in self._uncommitted_offsets[partition]:
                        new_offset = x
                        self._uncommitted_offsets[partition].remove(x)
                    else:
                        break

                self.update_offset(partition, new_offset)
                if offset == new_offset:
                    log.debug('Updating offset for partition %d, offset %d' % (partition, new_offset))
                else:
                    log.debug('Updating offset for partition %d, offset %d covering this update and older offsets'
                              % (partition, new_offset))
            elif self.offsets[partition] > offset:
                log.warn('An offset was received that was lower than the committed offset.' +
                         'Possibly a result of skipping lagging notifications')
            else:  # This is skipping offsets so add to the uncommitted set unless max_lag has been hit
                self._uncommitted_offsets[partition].add(offset)
                log.debug('Added partition %d, offset %d to uncommited set' % (partition, offset))
                if (self.max_lag is not None) and ((time.time() - self._last_commit_time[partition]) > self.max_lag):
                    log.error('Max Lag has been reached! Skipping offsets for partition %s' % partition)
                    self.update_offset(partition, max(self._uncommitted_offsets[partition]))
                    self._uncommitted_offsets[partition].clear()

        self._drop_lock()

    def update_offset(self, partition, value):
        """Update the object and kafka offset number for a partition to value
        """
        if self._offsets is None:  # Initialize offsets if needed
            self.offsets

        self.offset_update_count += value - self._offsets[partition]
        self._offsets[partition] = value

        req = kafka.common.OffsetCommitRequest(self.topic, partition, value, None)
        try:
            responses = self.kafka.send_offset_commit_request(self.kafka_group, [req])
            kafka.common.check_error(responses[0])
            log.debug('Updated committed offset for partition %s, offset %s' % (partition, value))
        except kafka.common.KafkaError:
            log.exception('Error updating the committed offset in kafka, partition %s, value %s' % (partition, value))
            raise

        self._last_commit_time[partition] = time.time()
