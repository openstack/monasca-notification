# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
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
from oslo_serialization import jsonutils

from monasca_common.kafka import client_factory
from monasca_notification.common.repositories import exceptions
from monasca_notification.common.utils import construct_notification_object
from monasca_notification.common.utils import get_db_repo
from monasca_notification.common.utils import get_statsd_client
from monasca_notification.processors import notification_processor

log = logging.getLogger(__name__)
CONF = cfg.CONF


class PeriodicEngine(object):
    def __init__(self, period):
        self._topic_name = CONF.kafka.periodic[str(period)]

        self._statsd = get_statsd_client()

        self._consumer = client_factory.get_kafka_consumer(
            CONF.kafka.url,
            CONF.kafka.group,
            self._topic_name,
            CONF.zookeeper.url,
            CONF.zookeeper.periodic_path[str(period)],
            CONF.kafka.legacy_kafka_client_enabled)
        self._producer = client_factory.get_kafka_producer(
            CONF.kafka.url,
            CONF.kafka.legacy_kafka_client_enabled)

        self._notifier = notification_processor.NotificationProcessor()
        self._db_repo = get_db_repo()
        self._period = period

    def _keep_sending(self, alarm_id, original_state, period):
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
        # Period changed
        if period != self._period:
            return False

        return True

    def run(self):
        for raw_notification in self._consumer:
            message = raw_notification.value()
            notification_data = jsonutils.loads(message)

            notification = construct_notification_object(self._db_repo, notification_data)

            if notification is None:
                self._consumer.commit()
                continue

            if self._keep_sending(notification.alarm_id,
                                  notification.state,
                                  notification.period):

                wait_duration = notification.period - (
                    time.time() - notification_data['notification_timestamp'])

                if wait_duration > 0:
                    time.sleep(wait_duration)

                notification.notification_timestamp = time.time()

                self._notifier.send([notification])
                self._producer.publish(self._topic_name,
                                       [notification.to_json()])

            self._consumer.commit()
