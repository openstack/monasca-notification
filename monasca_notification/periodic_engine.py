# (C) Copyright 2016 Hewlett Packard Enterprise Development Company LP
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

from monasca_common.kafka.consumer import KafkaConsumer
from monasca_common.kafka.producer import KafkaProducer
from monasca_notification.common.repositories import exceptions
from monasca_notification.common.utils import get_db_repo
from notification import Notification
from processors.base import BaseProcessor
from processors.notification_processor import NotificationProcessor

log = logging.getLogger(__name__)


class PeriodicEngine(object):
    def __init__(self, config, interval):
        self._topic_name = config['kafka']['periodic'][interval]

        self._statsd = monascastatsd.Client(name='monasca',
                                            dimensions=BaseProcessor.dimensions)

        zookeeper_path = config['zookeeper']['periodic_path'][interval]
        self._consumer = KafkaConsumer(config['kafka']['url'],
                                       config['zookeeper']['url'],
                                       zookeeper_path,
                                       config['kafka']['group'],
                                       self._topic_name)

        self._producer = KafkaProducer(config['kafka']['url'])

        self._notifier = NotificationProcessor(config['notification_types'])
        self._db_repo = get_db_repo(config)

    def _keep_sending(self, alarm_id, original_state):
        # Go to DB and check alarm state
        try:
            current_state = self._db_repo.get_alarm_current_state(alarm_id)
        except exceptions.DatabaseException:
            log.debug('Database Error.  Attempting reconnect')
            current_state = self._db_repo.get_alarm_current_state(alarm_id)
        # Alarm was deleted
        if current_state is None:
            return False
        # Alarm state changed
        if current_state != original_state:
            return False
        return True

    def run(self):
        for raw_notification in self._consumer:
            partition = raw_notification[0]
            offset = raw_notification[1].offset
            message = raw_notification[1].message.value

            notification_data = json.loads(message)

            ntype = notification_data['type']
            name = notification_data['name']
            addr = notification_data['address']
            period = notification_data['period']

            notification = Notification(ntype,
                                        partition,
                                        offset,
                                        name,
                                        addr,
                                        period,
                                        notification_data['retry_count'],
                                        notification_data['raw_alarm'])

            if self._keep_sending(notification.alarm_id, notification.state):
                wait_duration = period - (
                    time.time() - notification_data['notification_timestamp'])

                if wait_duration > 0:
                    time.sleep(wait_duration)

                notification.notification_timestamp = time.time()

                self._notifier.send([notification])
                self._producer.publish(self._topic_name,
                                       [notification.to_json()])

            self._consumer.commit()
