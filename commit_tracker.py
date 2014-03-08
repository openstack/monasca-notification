import logging

from kazoo.client import KazooClient
from kazoo.exceptions import KazooException

log = logging.getLogger(__name__)


class KafkaCommitTracker(object):
    """ Tracks message offsets for a kafka topic and partitions.
        Uses zookeeper to keep track of the last committed offset.
        As messages are finished with processing the committed offset is updated
    """


    # todo how do I have one object shared across processes? Maybe I don't maybe I use another internal
    # queue for finished notifications. This then runs in a thread that reads that queue and acts
    # appropriately.

    def __init__(self, url, topic):
        """ Setup the tracker
            url is the zookeeper hostname:port
            topic is the kafka topic to track
        """
        self.zookeeper = KazooClient(url)
        self.zookeeper.start()
        self.topic_path = '/consumers/mon-notifications/%s' % topic

        self.offsets = self._get_offsets()

    def _get_offsets(self):
        """ Read the initial offsets from zookeeper or set defaults
            The return is a dictionary with key name being partition # and value the offset
        """
        try:
            if self.zookeeper.exists(self.topic_path):
                offsets = {}
                for child in self.zookeeper.get_children(self.topic_path):
                    offsets[child] = self.zookeeper.get('/'.join(self.topic_path, child)[0])
                return offsets
            else:
                self.zookeeper.ensure_path(self.topic_path)
                return {}
        except KazooException, e:
            log.exception('Error retrieving the committed offset in zookeeper')

    def _update_offsets(self):
        """ Update zookeepers stored offset numbers
        """
        try:
            for partition, value in self.offsets.iteritems():
                self.zookeeper.set('/'.join(self.topic_path, partition), value)
        except KazooException, e:
            log.exception('Error updating the committed offset in zookeeper')

    def finish(self, partition, offset):
        """ Mark a message as finished.
        """
        log.debug('Received finish for partition %s, offset %s' % (partition, offset))
        # todo what to do if a single alarm is holding up committing others for a long time?

    def get_offsets(self, partitions=None):
        """ Return the offsets for specified partitions or all if partitions is None
            The return is a dictionary with key name being partition # and value the offset
        """
        if partitions is None:
            return self.offsets
        else:
            return {k: self.offsets[k] for k in partitions}

