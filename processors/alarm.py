import json
import logging
import MySQLdb

from . import BaseProcessor
from notification_exceptions import AlarmFormatError
import Notification


log = logging.getLogger(__name__)


class AlarmProcessor(BaseProcessor):
    def __init__(self, alarm_queue, notification_queue, finished_queue, mysql_host, mysql_user, mysql_passwd, dbname):
        self.alarm_queue = alarm_queue
        self.notification_queue = notification_queue
        self.finished_queue = finished_queue

        self.mysql = MySQLdb.connect(host=mysql_host, user=mysql_user, passwd=mysql_passwd, db=dbname)

    @staticmethod
    def _parse_alarm(alarm_data):
        """ Parse the alarm message making sure it matches the expected format.
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
        """ Check the notification setting for this project in mysql then create the appropriate notification or
            add to the finished_queue
        """
        cur = self.mysql.cursor()
        while True:
            raw_alarm = self.alarm_queue.get()
            partition = raw_alarm[0]
            offset = raw_alarm[1].offset
            try:
                alarm = self._parse_alarm(raw_alarm[1].message.value)
            except Exception, e:  # This is general because of a lack of json exception base class
                log.error("Invalid Alarm format skipping partition %d, offset %d\nErrror%s" % (partition, offset, e))
                self._add_to_queue(self.finished_queue, 'finished', (partition, offset))
                continue

            log.debug("Read alarm from alarms sent_queue. Partition %d, Offset %d, alarm data %s"
                      % (partition, offset, alarm))

            try:  # alarm_action.action_id == notification_method.id
                cur.execute("SELECT action_id FROM alarm_action WHERE alarm_id = ?", alarm['alarmId'])
                ids = [row.action_id for row in cur]
                if len(ids) == 1:
                    cur.execute("SELECT name, type, address FROM notification_method WHERE id = ?", ids[0])
                elif len(ids) > 1:
                    cur.execute("SELECT name, type, address FROM notification_method WHERE id in (?)", ','.join(ids))
            except MySQLdb.Error:
                log.exception('Error reading from mysql')

            notifications = [
                Notification(row.type.lower(), partition, offset, row.name, row.address, alarm) for row in cur]

            if len(notifications) == 0:
                log.debug('No notifications found for this alarm, partition %d, offset %d, alarm data %s'
                          % (partition, offset, alarm))
                self._add_to_queue(self.finished_queue, 'finished', (partition, offset))
            else:
                self._add_to_queue(self.notification_queue, 'notifications', (partition, offset))

