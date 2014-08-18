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
import kafka.common
import kafka.consumer
import logging
import statsd

from monasca_notification.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class KafkaConsumer(BaseProcessor):
    """Pull from the alarm topic and place alarm objects on the sent_queue.
         No commit is being done until processing is finished and as the processing can take some time it is done in
         another step.

         Unfortunately at this point the python-kafka client does not handle multiple consumers seamlessly.
         For more information see, https://github.com/mumrah/kafka-python/issues/112
    """
    def __init__(self, queue, kafka_url, group, topic):
        """Init
             kafka_url, group, topic - kafka connection details
             sent_queue - a sent_queue to publish log entries to
        """
        self.queue = queue

        self.kafka = kafka.client.KafkaClient(kafka_url)
        # No auto-commit so that commits only happen after the alarm is processed.
        self.consumer = kafka.consumer.SimpleConsumer(self.kafka, group, topic, auto_commit=False)
        self.consumer.provide_partition_info()  # Without this the partition is not provided in the response

        self._initialize_offsets(group, topic)
        # After my pull request is merged I can remove _initialize_offsets and use
        # self.consumer.offsets = self.consumer.get_offsets()
        # self.consumer.fetch_offsets = self.consumer.offsets.copy()
        offsets = self.consumer.offsets.copy()
        self.consumer.seek(0, 0)
        if offsets != self.consumer.offsets:
            log.error('Some messages not yet processed are no longer available in kafka, skipping to first available')
            log.debug('Intialized offsets %s\nStarting offsets %s' % (offsets, self.consumer.offsets))

    def _initialize_offsets(self, group, topic):
        """Fetch initial offsets from kafka
            This is largely taken from what the kafka consumer itself does when auto_commit is used
        """
        def get_or_init_offset_callback(resp):
            try:
                kafka.common.check_error(resp)
                return resp.offset
            except kafka.common.UnknownTopicOrPartitionError:
                return 0

        for partition in self.kafka.topic_partitions[topic]:
            req = kafka.common.OffsetFetchRequest(topic, partition)
            (offset,) = self.consumer.client.send_offset_fetch_request(group, [req],
                                                                       callback=get_or_init_offset_callback,
                                                                       fail_on_error=False)

            # The recorded offset is the last successfully processed, start processing at the next
            # if no processing has been done the offset is 0
            if offset == 0:
                self.consumer.offsets[partition] = offset
            else:
                self.consumer.offsets[partition] = offset + 1

        # fetch_offsets are used by the SimpleConsumer
        self.consumer.fetch_offsets = self.consumer.offsets.copy()

    def run(self):
        """Consume from kafka and place alarm objects on the sent_queue
        """
        counter = statsd.Counter('ConsumedFromKafka')
        try:
            for message in self.consumer:
                counter += 1
                log.debug("Consuming message from kafka, partition %d, offset %d" % (message[0], message[1].offset))
                self._add_to_queue(self.queue, 'alarms', message)
        except Exception:
            log.exception('Error running Kafka Consumer')
            raise
