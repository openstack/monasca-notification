import logging

from kafka.client import KafkaClient
from kafka.consumer import SimpleConsumer
from kafka.producer import SimpleProducer

log = logging.getLogger(__name__)


class SentNotificationProcessor(object):
    """ Processes notifications which have been sent
        This involves adding them into a kafka topic for persisting by another process and marking that alarm as finished.
    """

    def __init__(self, url, topic, queue, tracker):
        """
            url, group - kafka connection details
            topic - kafka topic to publish notifications to
            queue - a queue to read notifications from
        """
        self.kafka = KafkaClient(url)
        self.producer = SimpleProducer(
            self.kafka,
            async=False,
            req_acks=SimpleProducer.ACK_AFTER_LOCAL_WRITE,
            ack_timeout=2000
        )

        self.topic = topic
        self.tracker = tracker
        self.queue = queue

    def run(self):
        """ Takes messages from the queue, puts them on the notification topic and updates the processed offset
        """
        while True:
            # todo I expect the message format to change, the .message.value is just for test
            message = self.queue.get().message.value
            responses = self.producer.send_messages(self.topic, message)
            for resp in responses:
                if resp.error != 0:
                    log.error('Error publishing to %s topic, error message %s, offset #%d' %
                              (self.topic, resp.error, resp.offset))
            self.tracker.finish(message.partition, message.offset)
