import kafka.client
import kafka.consumer
import logging

from mon_notification.processors import BaseProcessor

log = logging.getLogger(__name__)


class KafkaConsumer(BaseProcessor):
    """Pull from the alarm topic and place alarm objects on the sent_queue.
         No commit is being done until processing is finished and as the processing can take some time it is done in
         another step.

         Unfortunately at this point the python-kafka client does not handle multiple consumers seamlessly.
         For more information see, https://github.com/mumrah/kafka-python/issues/112
    """
    def __init__(self, queue, kafka_url, group, topic, initial_offsets=None):
        """Init
             kafka_url, group, topic - kafka connection details
             sent_queue - a sent_queue to publish log entries to
        """
        self.queue = queue

        self.kafka = kafka.client.KafkaClient(kafka_url)
        # No autocommit, it does not work with kafka 0.8.0 - see https://github.com/mumrah/kafka-python/issues/118
        self.consumer = kafka.consumer.SimpleConsumer(self.kafka, group, topic, auto_commit=False)
        self.consumer.provide_partition_info()  # Without this the partition is not provided in the response
        if initial_offsets is not None:
            # Set initial offsets directly in the consumer, there is no method for this so I have to do it here
            self.consumer.offsets.update(initial_offsets)
            # fetch offsets are +1 of standard offsets
            for partition in initial_offsets:
                self.consumer.fetch_offsets[partition] = initial_offsets[partition] + 1

    def run(self):
        """Consume from kafka and place alarm objects on the sent_queue
        """
        for message in self.consumer:
            log.debug("Consuming message from kafka, partition %d, offset %d" % (message[0], message[1].offset))
            self._add_to_queue(self.queue, 'alarms', message)
