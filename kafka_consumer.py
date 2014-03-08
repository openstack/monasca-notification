import logging

from kafka.client import KafkaClient
from kafka.consumer import SimpleConsumer

from commit_tracker import KafkaCommitTracker

log = logging.getLogger(__name__)

class KafkaConsumer(object):
    """ Pull from the alarm topic and place alarm objects on the queue.
        No commit is being done until processing is finished and as the processing can take some time it is done in
        another step.

        Unfortunately at this point the python-kafka client does not handle multiple consumers seamlessly.
        To work around this I connect to zookeeper and create a znode used for tracking which partitions are
        being consumed from.
        For more information see, https://github.com/mumrah/kafka-python/issues/112
    """
    def __init__(self, queue, kafka_url, group, topic, zookeeper_url):
        """
            kafka_url, group, topic - kafka connection details
            queue - a queue to publish log entries to
        """
        self.queue = queue

        self.kafka = KafkaClient(kafka_url)
        # No autocommit, it does not work with kafka 0.8.0 - see https://github.com/mumrah/kafka-python/issues/118
        self.consumer = SimpleConsumer(self.kafka, group, topic, auto_commit=False)
        self.tracker = KafkaCommitTracker(zookeeper_url, topic)

    def run(self):
        """ Consume from kafka and place alarm objects on the queue
        """
        # Set current offsets to the last known position
        self.consumer.offsets.update(self.tracker.get_offsets())

        for message in self.consumer:
            log.debug("Consuming message from kafka - value = %s" % message.message.value)
            if self.queue.full():
                log.debug('Alarm queue is full, consuming from kafka is blocked')
            self.queue.put(message)  # The message is decoded in the AlarmProcessor
