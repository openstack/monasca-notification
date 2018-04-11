# (C) Copyright 2014-2016 Hewlett Packard Enterprise Development LP
# Copyright 2017 FUJITSU LIMITED
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
import six
import ujson as json

from monasca_notification.common.repositories import exceptions as exc
from monasca_notification.common.utils import get_db_repo
from monasca_notification.common.utils import get_statsd_client
from monasca_notification import notification
from monasca_notification import notification_exceptions


log = logging.getLogger(__name__)
CONF = cfg.CONF


class AlarmProcessor(object):
    def __init__(self):
        self._alarm_ttl = CONF.alarm_processor.ttl
        self._statsd = get_statsd_client()
        self._db_repo = get_db_repo()

    @staticmethod
    def _parse_alarm(alarm_data):
        """Parse the alarm message making sure it matches the expected format.
        """
        expected_fields = [
            'actionsEnabled',
            'alarmId',
            'alarmDefinitionId',
            'alarmName',
            'newState',
            'oldState',
            'stateChangeReason',
            'severity',
            'link',
            'lifecycleState',
            'tenantId',
            'timestamp'
        ]
        # check if alarm_data is <class 'bytes'>
        # if yes convert it to standard string
        if isinstance(alarm_data, six.binary_type):
            alarm_data = alarm_data.decode("utf-8")
        json_alarm = json.loads(alarm_data)
        alarm = json_alarm['alarm-transitioned']
        for field in expected_fields:
            if field not in alarm:
                raise notification_exceptions.AlarmFormatError(
                    'Alarm data missing field %s' % field)
        if ('tenantId' not in alarm) or ('alarmId' not in alarm):
            raise notification_exceptions.AlarmFormatError

        return alarm

    def _alarm_is_valid(self, alarm):
        """Check if the alarm is enabled and is within the ttl, return True in that case
        """
        if not alarm['actionsEnabled']:
            log.debug('Actions are disabled for this alarm.')
            return False

        alarm_age = time.time() - alarm['timestamp'] / 1000
        if (self._alarm_ttl is not None) and (alarm_age > self._alarm_ttl):
            log.warn('Received alarm older than the ttl, skipping. Alarm from %s' %
                     time.ctime(alarm['timestamp'] / 1000))
            return False

        return True

    def _build_notification(self, alarm):
        db_time = self._statsd.get_timer()

        with db_time.time('config_db_time'):
            alarms_actions = self._db_repo.fetch_notifications(alarm)

        return [notification.Notification(
                alarms_action[0],
                alarms_action[1],
                alarms_action[2],
                alarms_action[3],
                alarms_action[4],
                0,
                alarm) for alarms_action in alarms_actions]

    def to_notification(self, raw_alarm):
        """Check the notification setting for this project then create the appropriate notification
        """
        failed_parse_count = self._statsd.get_counter(name='alarms_failed_parse_count')
        no_notification_count = self._statsd.get_counter(name='alarms_no_notification_count')
        notification_count = self._statsd.get_counter(name='created_count')

        partition = raw_alarm[0]
        offset = raw_alarm[1].offset
        try:
            alarm = self._parse_alarm(raw_alarm[1].message.value)
        except Exception as e:  # This is general because of a lack of json exception base class
            failed_parse_count += 1
            log.exception(
                "Invalid Alarm format skipping partition %d, offset %d\nError%s" %
                (partition, offset, e))
            return [], partition, offset

        log.debug("Read alarm from alarms sent_queue. Partition %d, Offset %d, alarm data %s"
                  % (partition, offset, alarm))

        if not self._alarm_is_valid(alarm):
            no_notification_count += 1
            return [], partition, offset

        try:
            notifications = self._build_notification(alarm)
        except exc.DatabaseException:
            log.debug('Database Error.  Attempting reconnect')
            notifications = self._build_notification(alarm)

        if len(notifications) == 0:
            no_notification_count += 1
            log.debug(
                'No notifications found for this alarm, partition %d, offset %d, alarm data %s' %
                (partition, offset, alarm))
            return [], partition, offset
        else:
            log.debug('Found %d notifications: [%s]', len(notifications), notifications)
            notification_count += len(notifications)
            return notifications, partition, offset
