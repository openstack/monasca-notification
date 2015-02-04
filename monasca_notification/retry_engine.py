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

import json
import logging
import monascastatsd
import time

from notification import Notification
from processors.base import BaseProcessor
from processors.kafka_consumer import KafkaConsumer
from processors.kafka_producer import KafkaProducer
from processors.notification_processor import NotificationProcessor

log = logging.getLogger(__name__)


class RetryEngine(object):
    def __init__(self, config):
        self._retry_interval = config['retry']['interval']
        self._retry_max = config['retry']['max_attempts']

        self._topics = {}
        self._topics['notification_topic'] = config['kafka']['notification_topic']
        self._topics['retry_topic'] = config['kafka']['notification_retry_topic']

        self._statsd = monascastatsd.Client(name='monasca',
                                            dimensions=BaseProcessor.dimensions)

        self._consumer = KafkaConsumer(config['kafka']['url'],
                                       config['zookeeper']['url'],
                                       config['zookeeper']['notification_retry_path'],
                                       config['kafka']['group'],
                                       config['kafka']['notification_retry_topic'])

        self._producer = KafkaProducer(config['kafka']['url'])

        self._notifier = NotificationProcessor(config['notification_types'])

    def run(self):
        for raw_notification in self._consumer:
            partition = raw_notification[0]
            offset = raw_notification[1].offset
            message = raw_notification[1].message.value

            notification_data = json.loads(message)

            ntype = notification_data['type']
            name = notification_data['name']
            addr = notification_data['address']

            notification = Notification(ntype,
                                        partition,
                                        offset,
                                        name,
                                        addr,
                                        notification_data['retry_count'],
                                        notification_data['raw_alarm'])

            wait_duration = self._retry_interval - (
                time.time() - notification_data['notification_timestamp'])

            if wait_duration > 0:
                time.sleep(wait_duration)

            sent, failed = self._notifier.send([notification])

            if sent:
                self._producer.publish(self._topics['notification_topic'], sent)

            if failed:
                notification.retry_count += 1
                notification.notification_timestamp = time.time()
                if notification.retry_count < self._retry_max:
                    log.error("retry failed for {} with name {} "
                              "at {}.  "
                              "Saving for later retry.".format(ntype, name, addr))
                    self._producer.publish(self._topics['retry_topic'],
                                           [notification])
                else:
                    log.error("retry failed for {} with name {} "
                              "at {} after {} retries.  "
                              "Giving up on retry."
                              .format(ntype, name, addr, self._retry_max))

            self._consumer.commit([partition])
