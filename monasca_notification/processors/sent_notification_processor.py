# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import kafka.client
import kafka.producer
import logging
import statsd

from monasca_notification.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class SentNotificationProcessor(BaseProcessor):
    """Processes notifications which have been sent
         This involves adding them into a kafka topic for persisting by another process and adding the alarm
         to the finished queue.
    """

    def __init__(self, sent_queue, finished_queue, url, topic):
        """Init
             url, group - kafka connection details
             topic - kafka topic to publish notifications to
             finished_queue - queue written to when notifications are fully finished.
             sent_queue - the sent_notifications queue notifications are read from
        """
        self.topic = topic
        self.finished_queue = finished_queue
        self.sent_queue = sent_queue

        self.kafka = kafka.client.KafkaClient(url)
        self.producer = kafka.producer.SimpleProducer(
            self.kafka,
            async=False,
            req_acks=kafka.producer.SimpleProducer.ACK_AFTER_LOCAL_WRITE,
            ack_timeout=2000
        )

    def run(self):
        """Takes messages from the sent_queue, puts them on the kafka notification topic and then adds
             partition/offset to the finished queue
        """
        published_count = statsd.Counter('PublishedToKafka')
        while True:
            notifications = self.sent_queue.get()
            for notification in notifications:
                responses = self.producer.send_messages(self.topic, notification.to_json())
                published_count += 1
                log.debug('Published to topic %s, message %s' % (self.topic, notification.to_json()))
                for resp in responses:
                    if resp.error != 0:
                        log.error('Error publishing to %s topic, error message %s' %
                                  (self.topic, resp.error))
            self._add_to_queue(
                self.finished_queue, 'finished', (notifications[0].src_partition, notifications[0].src_offset))
