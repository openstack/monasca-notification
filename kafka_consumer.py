import logging

from kafka.client import KafkaClient
from kafka.consumer import SimpleConsumer

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
    def __init__(self, url, group, topic, queue):
        """
            url, group, topic - kafka connection details
            queue - a queue to publish log entries to
        """
        self.kafka = KafkaClient(url)

        # Todo connect to zookeeper and make a znode where I can track which consumers to consume from.
            # Initially just grab them all, in the future probably should be spread out more, add this to future considerations

        # No autocommit, that is done after sending, see the README.md for more details
        self.consumer = SimpleConsumer(self.kafka, group, topic, auto_commit=False)
        self.queue = queue

    def run(self):
        """ Consume from kafka and place alarm objects on the queue
            This quite intentionally does not ack
        """
        for message in self.consumer:
            log.debug("Consuming message from kafka - value = %s" % message.message.value)
            if self.queue.full():
                log.debug('Alarm queue is full, consuming from kafka is blocked')
            self.queue.put(message)  # The message is decoded in the AlarmProcessor
