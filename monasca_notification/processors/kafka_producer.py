# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
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
import monascastatsd
import time

from monasca_notification.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class KafkaProducer(BaseProcessor):
    """Adds messages to a kafka topic
    """

    def __init__(self, url):
        """Init
             url, group - kafka connection details
        """
        self._statsd = monascastatsd.Client(name='monasca', dimensions=BaseProcessor.dimensions)

        self._kafka = kafka.client.KafkaClient(url)
        self._producer = kafka.producer.KeyedProducer(
            self._kafka,
            async=False,
            req_acks=kafka.producer.KeyedProducer.ACK_AFTER_LOCAL_WRITE,
            ack_timeout=2000)

    def publish(self, topic, messages):
        """Takes messages and puts them on the supplied kafka topic
        """
        published_to_kafka = self._statsd.get_counter(name='published_to_kafka')

        for message in messages:
            key = time.time() * 1000
            try:
                responses = self._producer.send(topic, key, message.to_json())
            except Exception:
                log.exception("error publishing message to kafka")
                continue

            published_to_kafka += 1

            log.debug('Published to topic {}, message {}'.format(topic, message.to_json()))
            for resp in responses:
                if resp.error != 0:
                    log.error('Error publishing to {} topic, '
                              'error message {}'.format(self.topic, resp.error))
