# (C) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
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

import logging
import time

from monasca_common.kafka import consumer
from monasca_common.kafka import producer
from monasca_notification.common.utils import get_statsd_client
from processors.alarm_processor import AlarmProcessor
from processors.notification_processor import NotificationProcessor

log = logging.getLogger(__name__)


class NotificationEngine(object):
    def __init__(self, config):
        self._topics = {}
        self._topics['notification_topic'] = config['kafka']['notification_topic']
        self._topics['retry_topic'] = config['kafka']['notification_retry_topic']

        self._statsd = get_statsd_client(config)
        self._consumer = consumer.KafkaConsumer(
            config['kafka']['url'],
            config['zookeeper']['url'],
            config['zookeeper']['notification_path'],
            config['kafka']['group'],
            config['kafka']['alarm_topic'])
        self._producer = producer.KafkaProducer(config['kafka']['url'])
        self._alarm_ttl = config['processors']['alarm']['ttl']
        self._alarms = AlarmProcessor(self._alarm_ttl, config)
        self._notifier = NotificationProcessor(config)

        self._config = config

    def _add_periodic_notifications(self, notifications):
        for notification in notifications:
            topic = notification.periodic_topic
            if topic in self._config['kafka']['periodic'] and notification.type == "webhook":
                notification.notification_timestamp = time.time()
                self._producer.publish(self._config['kafka']['periodic'][topic],
                                       [notification.to_json()])

    def run(self):
        finished_count = self._statsd.get_counter(name='alarms_finished_count')
        for alarm in self._consumer:
            log.debug('Received alarm >|%s|<', str(alarm))
            notifications, partition, offset = self._alarms.to_notification(alarm)
            if notifications:
                self._add_periodic_notifications(notifications)

                sent, failed = self._notifier.send(notifications)
                self._producer.publish(self._topics['notification_topic'],
                                       [i.to_json() for i in sent])
                self._producer.publish(self._topics['retry_topic'],
                                       [i.to_json() for i in failed])

            self._consumer.commit()
            finished_count.increment()
