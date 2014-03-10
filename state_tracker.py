import logging
import time

from kazoo.client import KazooClient
from kazoo.exceptions import KazooException

log = logging.getLogger(__name__)


class ZookeeperStateTracker(object):
    """ Tracks message offsets for a kafka topic and partitions.
        Uses zookeeper to keep track of the last committed offset.
        As messages are finished with processing the committed offset is updated periodically.
        The messages are not necessarily finished in order, but the committed offset includes
        all previous messages so this object tracks any gaps updating as needed.
    """
    def __init__(self, url, topic, finished_queue):
        """ Setup the finished_queue
            url is the zookeeper hostname:port
            topic is the kafka topic to track
        """
        self.finished_queue = finished_queue
        self.topic = topic
        self.has_lock = False

        self.zookeeper = KazooClient(url)
        self.zookeeper.start()
        self.topic_path = '/consumers/mon-notification/%s' % topic

        self._offsets = None

        self.lock_retry_time = 15  # number of seconds to wait for retrying for the lock
        self.lock_path = '/locks/mon-notification/%s' % topic

    def _get_offsets(self):
        """ Read the initial offsets from zookeeper or set defaults
            The return is a dictionary with key name being partition # and value the offset
        """
        if not self.has_lock:
            log.warn('Reading offsets before the tracker has the lock, they could change')
        try:
            if self.zookeeper.exists(self.topic_path):
                offsets = {}
                for child in self.zookeeper.get_children(self.topic_path):
                    offsets[int(child)] = int(self.zookeeper.get('/'.join((self.topic_path, child)))[0])
                log.info('Setting initial offsets to %s' % offsets)
                return offsets
            else:
                self.zookeeper.ensure_path(self.topic_path)
                return {}
        except KazooException, e:
            log.exception('Error retrieving the committed offset in zookeeper')

    def _update_offsets(self):
        """ Update zookeepers stored offset numbers to the values in self.offsets
        """
        try:
            for partition, value in self._offsets.iteritems():
                partition_path = '/'.join((self.topic_path, str(partition)))
                self.zookeeper.ensure_path(partition_path)
                self.zookeeper.set(partition_path, str(value))
            log.debug('Updated committed offsets at path %s, offsets %s' % (self.topic_path, self._offsets))
        except KazooException, e:
            log.exception('Error updating the committed offset in zookeeper')

    @property
    def offsets(self):
        """ Generally only initialize the offsets after the lock has been pulled
        """
        if self._offsets is None:
            self._offsets = self._get_offsets()

        return self._offsets

    def get_offsets(self, partitions=None):
        """ Return the offsets for specified partitions or all if partitions is None
            The return is a dictionary with key name being partition # and value the offset
        """
        if partitions is None:
            return self.offsets
        else:
            return {k: self.offsets[k] for k in partitions}

    def lock(self, exit_method):
        """ Grab a lock within zookeeper, if not available retry.
        """
        while True:
            # The path is ephemeral so if it exists wait then cycle again
            if self.zookeeper.exists(self.lock_path):
                log.info('Another process has the lock for topic %s, waiting then retrying.' % self.topic)
                time.sleep(self.lock_retry_time)
                continue

            try:
                self.zookeeper.create(self.lock_path, ephemeral=True, makepath=True)
            except KazooException, e:
                # If creating the path fails something beat us to it most likely, try again
                log.warn('Error creating lock path %s\n%s' % (self.lock_path, e))
                continue
            else:
                # Succeeded in grabbing the lock continue
                log.info('Grabbed lock for topic %s' % self.topic)
                self.has_lock = True
                break

        # Set up a listener to exit if we loose connection, this always exits even if the zookeeper connection is only
        # suspended, the process should be supervised so it starts right back up again.
        self.zookeeper.add_listener(exit_method)

    def run(self):
        """ Mark a message as finished.
        """
        if not self.has_lock:
            raise NotificationException('Attempt to begin run without Zookeeper Lock')

        if self._offsets is None:  # Verify the offsets have been initialized
            self.offsets

        while True:
            msg = self.finished_queue.get()
            partition = int(msg[0])
            offset = int(msg[1])

            log.debug('Received commit finish for partition %d, offset %d' % (partition, offset))
            # todo these don't come in order but I should only update when there is an unbroken chain
            # from the last offset to the current. I have yet to implement this logic
            if (not self._offsets.has_key(partition)) or (self._offsets[partition] < offset):
                self._offsets[partition] = offset
                self._update_offsets()
            # todo what to do if a single alarm is holding up committing others for a long time?
