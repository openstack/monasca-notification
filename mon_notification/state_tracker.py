import collections
import kazoo.client
import kazoo.exceptions
import logging
import Queue
import statsd
import time

from mon_notification import notification_exceptions

log = logging.getLogger(__name__)


class ZookeeperStateTracker(object):
    """Tracks message offsets for a kafka topic and partitions.
         Uses zookeeper to keep track of the last committed offset.
         As messages are finished with processing the committed offset is updated periodically.
         The messages are not necessarily finished in order, but the committed offset includes
         all previous messages so this object tracks any gaps updating as needed.
    """
    def __init__(self, url, topic, finished_queue, max_lag):
        """Setup the finished_queue
             url is the zookeeper hostname:port
             topic is the kafka topic to track
        """
        self.finished_queue = finished_queue
        self.max_lag = max_lag
        self.topic = topic
        self.has_lock = False
        self.stop = False

        self.zookeeper = kazoo.client.KazooClient(url)
        self.zookeeper.start()
        self.topic_path = '/consumers/mon-notification/%s' % topic

        self.lock_retry_time = 15  # number of seconds to wait for retrying for the lock
        self.lock_path = '/locks/mon-notification/%s' % topic

        self._offsets = None
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

    def _get_offsets(self):
        """Read the initial offsets from zookeeper or set defaults
             The return is a dictionary with key name being partition # and value the offset
        """
        if not self.has_lock:
            log.warn('Reading offsets before the tracker has the lock, they could change')
        try:
            if self.zookeeper.exists(self.topic_path):
                offsets = {}
                for child in self.zookeeper.get_children(self.topic_path):
                    offsets[int(child)] = int(self.zookeeper.get('/'.join((self.topic_path, child)))[0])
                log.info('Setting initial offsets to %s' % str(offsets))
                return offsets
            else:
                self.zookeeper.ensure_path(self.topic_path)
                return {}
        except kazoo.exceptions.KazooException:
            log.exception('Error retrieving the committed offset in zookeeper')

    def _update_offset(self, partition, value):
        """Update the object and zookeepers stored offset number for a partition to value
        """
        self.offset_update_count += value - self._offsets[partition]
        self._offsets[partition] = value
        partition_path = '/'.join((self.topic_path, str(partition)))
        try:
            with self.zk_timer.time():
                self.zookeeper.ensure_path(partition_path)
                self.zookeeper.set(partition_path, str(value))
            log.debug('Updated committed offset at path %s, offsets %s' % (partition_path, value))
        except kazoo.exceptions.KazooException:
            log.exception('Error updating the committed offset in zookeeper, path %s, value %s'
                          % (partition_path, value))

        self._last_commit_time[partition] = time.time()

    @property
    def offsets(self):
        """Generally only initialize the offsets after the lock has been pulled
        """
        if self._offsets is None:
            self._offsets = self._get_offsets()

        return self._offsets

    def get_offsets(self, partitions=None):
        """Return the offsets for specified partitions or all if partitions is None
             The return is a dictionary with key name being partition # and value the offset
        """
        if partitions is None:
            return self.offsets
        else:
            return {k: self.offsets[k] for k in partitions}

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

    def run(self):
        """Mark a message as finished and where possible commit the new offset to zookeeper.
             There is no mechanism here to deal with the situation where a single alarm is extremely slow to finish
             holding up all others behind it. It is assumed the notification will time out allowing things to finish.
        """
        if not self.has_lock:
            raise notification_exceptions.NotificationException('Attempt to begin run without Zookeeper Lock')

        if self._offsets is None:  # Verify the offsets have been initialized
            self._offsets = self._get_offsets()

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
                                self._update_offset(partition, max(self._uncommitted_offsets[partition]))
                    break

            try:
                msg = self.finished_queue.get(timeout=10)
            except Queue.Empty:
                continue  # This is non-blocking so the self.stop signal has a chance to take affect

            finished_count += 1
            partition = int(msg[0])
            offset = int(msg[1])

            log.debug('Received commit finish for partition %d, offset %d' % (partition, offset))
            # Update immediately if the partition is not yet tracked or the offset is 1 above current offset
            if partition not in self._offsets:
                log.debug('Updating offset for partition %d, offset %d' % (partition, offset))
                self._update_offset(partition, offset)
            elif self._offsets[partition] == offset - 1:

                new_offset = offset
                for x in range(offset + 1, offset + 1 + len(self._uncommitted_offsets[partition])):
                    if x in self._uncommitted_offsets[partition]:
                        new_offset = x
                        self._uncommitted_offsets[partition].remove(x)
                    else:
                        break

                self._update_offset(partition, new_offset)
                if offset == new_offset:
                    log.debug('Updating offset for partition %d, offset %d' % (partition, new_offset))
                else:
                    log.debug('Updating offset for partition %d, offset %d covering this update and older offsets'
                              % (partition, new_offset))
            elif self._offsets[partition] > offset:
                log.warn('An offset was received that was lower than the committed offset.' +
                         'Possibly a result of skipping lagging notifications')
            else:  # This is skipping offsets so add to the uncommitted set unless max_lag has been hit
                self._uncommitted_offsets[partition].add(offset)
                log.debug('Added partition %d, offset %d to uncommited set' % (partition, offset))
                if (self.max_lag is not None) and ((time.time() - self._last_commit_time[partition]) > self.max_lag):
                    log.error('Max Lag has been reached! Skipping offsets for partition %s' % partition)
                    self._update_offset(partition, max(self._uncommitted_offsets[partition]))
                    self._uncommitted_offsets[partition].clear()

        self._drop_lock()