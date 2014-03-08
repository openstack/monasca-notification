import logging

from kafka.client import KafkaClient
from kafka.consumer import SimpleConsumer
from kafka.producer import SimpleProducer

log = logging.getLogger(__name__)


class SentNotificationProcessor(object):
    """ Processes notifications which have been sent
        This involves adding them into a kafka topic for persisting by another process and marking that alarm as finished.
    """

    def __init__(self, queue, tracker, url, topic):
        """
            url, group - kafka connection details
            topic - kafka topic to publish notifications to
            queue - a queue to read notifications from
        """
        self.topic = topic
        self.tracker = tracker
        self.queue = queue

        self.kafka = KafkaClient(url)
        self.producer = SimpleProducer(
            self.kafka,
            async=False,
            req_acks=SimpleProducer.ACK_AFTER_LOCAL_WRITE,
            ack_timeout=2000
        )

    def run(self):
        """ Takes messages from the queue, puts them on the notification topic and updates the processed offset
        """
        while True:
            notification = self.queue.get()
            responses = self.producer.send_messages(self.topic, notification.to_json())
            log.debug('Published to topic %s, message %s' % (self.topic, notification.to_json()))
            for resp in responses:
                if resp.error != 0:
                    log.error('Error publishing to %s topic, error message %s' %
                              (self.topic, resp.error))
            self.tracker.finish(notification.src_partition, notification.src_offset)
