import json
import logging
import multiprocessing
import MySQLdb
import statsd
import time

from mon_notification.notification import Notification
from mon_notification.notification_exceptions import AlarmFormatError
from mon_notification.processors import BaseProcessor


log = logging.getLogger(__name__)


class AlarmProcessor(BaseProcessor):
    def __init__(
            self, alarm_queue, notification_queue, finished_queue,
            alarm_ttl, mysql_host, mysql_user, mysql_passwd, dbname):
        self.alarm_queue = alarm_queue
        self.alarm_ttl = alarm_ttl
        self.notification_queue = notification_queue
        self.finished_queue = finished_queue

        self.mysql = MySQLdb.connect(host=mysql_host, user=mysql_user, passwd=mysql_passwd, db=dbname)

    @staticmethod
    def _parse_alarm(alarm_data):
        """Parse the alarm message making sure it matches the expected format.
        """
        expected_fields = [
            'alarmId',
            'alarmName',
            'newState',
            'oldState',
            'stateChangeReason',
            'tenantId',
            'timestamp'
        ]

        json_alarm = json.loads(alarm_data)
        alarm = json_alarm['alarm-transitioned']
        for field in expected_fields:
            if field not in alarm:
                raise AlarmFormatError('Alarm data missing field %s' % field)
        if (not 'tenantId' in alarm) or (not 'alarmId' in alarm):
            raise AlarmFormatError

        return alarm

    def run(self):
        """Check the notification setting for this project in mysql then create the appropriate notification or
             add to the finished_queue
        """
        cur = self.mysql.cursor()
        pname = multiprocessing.current_process().name
        failed_parse_count = statsd.Counter('AlarmsFailedParse-%s' % pname)
        no_notification_count = statsd.Counter('AlarmsNoNotification-%s' % pname)
        notification_count = statsd.Counter('NotificationsCreated-%s' % pname)
        db_time = statsd.Timer('ConfigDBTime-%s' % pname)

        while True:
            raw_alarm = self.alarm_queue.get()
            partition = raw_alarm[0]
            offset = raw_alarm[1].offset
            try:
                alarm = self._parse_alarm(raw_alarm[1].message.value)
            except Exception as e:  # This is general because of a lack of json exception base class
                failed_parse_count += 1
                log.error("Invalid Alarm format skipping partition %d, offset %d\nErrror%s" % (partition, offset, e))
                self._add_to_queue(self.finished_queue, 'finished', (partition, offset))
                continue

            log.debug("Read alarm from alarms sent_queue. Partition %d, Offset %d, alarm data %s"
                      % (partition, offset, alarm))

            alarm_age = time.time() - alarm['timestamp']  # Should all be in seconds since epoch
            if (self.alarm_ttl is not None) and (alarm_age > self.alarm_ttl):
                no_notification_count += 1
                self._add_to_queue(self.finished_queue, 'finished', (partition, offset))
                log.warn('Received alarm older than the ttl, skipping. Alarm from %s' % time.ctime(alarm['timestamp']))
                continue

            try:
                with db_time.time():
                    cur.execute("SELECT notification_method_id FROM alarm_action WHERE alarm_id = %s", alarm['alarmId'])
                    ids = [row[0] for row in cur]
                    if len(ids) == 1:
                        cur.execute("SELECT name, type, address FROM notification_method WHERE id = %s", ids[0])
                    elif len(ids) > 1:
                        cur.execute(
                            "SELECT name, type, address FROM notification_method WHERE id in (%s)", ','.join(ids))
            except MySQLdb.Error:
                log.exception('Error reading from mysql')

            log.debug('Response from mysql')
            notifications = [
                Notification(row[1].lower(), partition, offset, row[0], row[2], alarm) for row in cur]

            if len(notifications) == 0:
                no_notification_count += 1
                log.debug('No notifications found for this alarm, partition %d, offset %d, alarm data %s'
                          % (partition, offset, alarm))
                self._add_to_queue(self.finished_queue, 'finished', (partition, offset))
            else:
                notification_count += len(notifications)
                self._add_to_queue(self.notification_queue, 'notifications', notifications)
