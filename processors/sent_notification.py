import logging

from kafka.client import KafkaClient
from kafka.consumer import SimpleConsumer
from kafka.producer import SimpleProducer

log = logging.getLogger(__name__)


class SentNotificationProcessor(object):
    """ Processes notifications which have been sent
        This involves adding them into a kafka topic for persisting by another process and updating the offset of the
        last processed alarm.
    """

    def __init__(self, url, group, alarm_topic, notification_topic, queue):
        """
            url, group - kafka connection details
            alarm_topic - kafka topic to commit reads from, completes cycle started in kafka_consumer
            notification_topic - kafka topic to publish notifications to
            queue - a queue to read notifications from
        """
        self.kafka = KafkaClient(url)
        self.alarm_consumer = SimpleConsumer(self.kafka, group, alarm_topic, auto_commit=False)
        #alarm_consumer = SimpleConsumer(self.kafka, group, alarm_topic, auto_commit=False)
#        self.alarms = KafkaCommitTracker(alarm_consumer)
        self.notification_producer = SimpleProducer(
            self.kafka,
            async=False,
            req_acks=SimpleProducer.ACK_AFTER_LOCAL_WRITE,
            ack_timeout=2000
        )

        self.notification_topic = notification_topic
        self.queue = queue

    def run(self):
        """ Takes messages from the queue, puts them on the notification topic and updates the processed offset
        """
        while True:
            # todo I expect the message format to change, the .message.value is just for test
            message = self.queue.get().message.value
            responses = self.notification_producer.send_messages(self.notification_topic, message)
            for resp in responses:
                if resp.error != 0:
                    log.error('Error publishing to %s topic, error message %s, offset #%d' %
                              (self.notification_topic, resp.error, resp.offset))

#            self.alarms.finished(message.id)
