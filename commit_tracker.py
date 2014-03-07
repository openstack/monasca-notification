
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
        self.zookeeper = url # todo
        self.topic = topic

    def finish(self, partition, offset):
        """ Mark a message as finished.
        """
        pass
        # todo what to do if a single alarm is holding up committing others for a long time?

    def get_offsets(self, partitions=None):
        """ Return the offsets for specified partitions or all if partitions is None
            The return is a dictionary with key name being partition # and value the offset
        """
        return {}
