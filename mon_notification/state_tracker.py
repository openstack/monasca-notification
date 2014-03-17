import collections
import kazoo.client
import kazoo.exceptions
import logging
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
    def __init__(self, url, topic, finished_queue):
        """Setup the finished_queue
             url is the zookeeper hostname:port
             topic is the kafka topic to track
        """
        self.finished_queue = finished_queue
        self.topic = topic
        self.has_lock = False

        self.zookeeper = kazoo.client.KazooClient(url)
        self.zookeeper.start()
        self.topic_path = '/consumers/mon-notification/%s' % topic

        self.lock_retry_time = 15  # number of seconds to wait for retrying for the lock
        self.lock_path = '/locks/mon-notification/%s' % topic

        self._offsets = None
        # This is a dictionary of sets used for tracking finished offsets when there is a gap and the committed offset
        # can not yet be advanced
        self._uncommitted_offsets = collections.defaultdict(set)

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

    def _update_zk_offsets(self):
        """Update zookeepers stored offset numbers to the values in self.offsets
        """
        try:
            for partition, value in self._offsets.iteritems():
                partition_path = '/'.join((self.topic_path, str(partition)))
                self.zookeeper.ensure_path(partition_path)
                self.zookeeper.set(partition_path, str(value))
            log.debug('Updated committed offsets at path %s, offsets %s' % (self.topic_path, self._offsets))
        except kazoo.exceptions.KazooException:
            log.exception('Error updating the committed offset in zookeeper')

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

        while True:
            msg = self.finished_queue.get()
            partition = int(msg[0])
            offset = int(msg[1])

            log.debug('Received commit finish for partition %d, offset %d' % (partition, offset))
            # Update immediately if the partition is not yet tracked or the offset is 1 above current offset
            if partition not in self._offsets:
                log.debug('Updating offset for partition %d, offset %d' % (partition, offset))
                self._offsets[partition] = offset
                self._update_zk_offsets()
            elif self._offsets[partition] == offset - 1:

                new_offset = offset
                for x in range(offset + 1, offset + 1 + len(self._uncommitted_offsets[partition])):
                    if x in self._uncommitted_offsets[partition]:
                        new_offset = x
                        self._uncommitted_offsets[partition].remove(x)
                    else:
                        break

                self._offsets[partition] = new_offset
                if offset == new_offset:
                    log.debug('Updating offset for partition %d, offset %d' % (partition, new_offset))
                else:
                    log.debug('Updating offset for partition %d, offset %d covering this update and older offsets'
                              % (partition, new_offset))
                self._update_zk_offsets()
            elif self._offsets[partition] > offset:
                log.error('An offset was received that was lower than the committed offset, this should not happen')
            else:  # This is skipping offsets so just add to the uncommitted set
                self._uncommitted_offsets[partition].add(offset)
                log.debug('Added partition %d, offset %d to uncommited set' % (partition, offset))
