# (C) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
# Copyright 2017 Fujitsu LIMITED
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

import time

from oslo_config import cfg
from oslo_log import log as logging

from monasca_common.kafka import client_factory
from monasca_notification.common.utils import get_statsd_client
from monasca_notification.processors import alarm_processor as ap
from monasca_notification.processors import notification_processor as np

log = logging.getLogger(__name__)
CONF = cfg.CONF


class NotificationEngine(object):
    def __init__(self):
        self._statsd = get_statsd_client()
        self._consumer = client_factory.get_kafka_consumer(
            CONF.kafka.url,
            CONF.kafka.group,
            CONF.kafka.alarm_topic,
            CONF.zookeeper.url,
            CONF.zookeeper.notification_path,
            CONF.kafka.legacy_kafka_client_enabled)
        self._producer = client_factory.get_kafka_producer(
            CONF.kafka.url,
            CONF.kafka.legacy_kafka_client_enabled)
        self._alarms = ap.AlarmProcessor()
        self._notifier = np.NotificationProcessor()

    def _add_periodic_notifications(self, notifications):
        for notification in notifications:
            period = str(notification.period)
            if period in CONF.kafka.periodic.keys():
                notification.notification_timestamp = time.time()
                self._producer.publish(CONF.kafka.periodic[period],
                                       [notification.to_json()])

    def run(self):
        finished_count = self._statsd.get_counter(name='alarms_finished_count')
        for alarm in self._consumer:
            log.debug('Received alarm >|%s|<', str(alarm))
            notifications, partition, offset = self._alarms.to_notification(alarm)
            if notifications:
                self._add_periodic_notifications(notifications)

                sent, failed = self._notifier.send(notifications)
                self._producer.publish(CONF.kafka.notification_topic,
                                       [i.to_json() for i in sent])
                self._producer.publish(CONF.kafka.notification_retry_topic,
                                       [i.to_json() for i in failed])

            self._consumer.commit()
            finished_count.increment()
