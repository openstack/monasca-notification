import json
import logging
import MySQLdb

from notifications.email import EmailNotification
from notification_exceptions import AlarmFormatError

log = logging.getLogger(__name__)


class AlarmProcessor(object):
    def __init__(self, alarm_queue, notification_queue, finished_queue, mysql_host, mysql_user, mysql_passwd, dbname):
        self.alarm_queue = alarm_queue
        self.notification_queue = notification_queue
        self.finished_queue = finished_queue

        self.mysql = MySQLdb.connect(host=mysql_host, user=mysql_user, passwd=mysql_passwd, db=dbname)

    def _add_to_finished_queue(self, partition, offset):
        if self.finished_queue.full():
            log.warn('Finished queue is full, publishing is blocked')
        self.finished_queue.put((partition, offset))

    def run(self):
        """ Check the notification setting for this project in mysql then create the appropriate notification or
            add to the finished_queue
        """
        cur = self.mysql.cursor()
        notification_types = {
            'EMAIL': EmailNotification
        }
        while True:
            raw_alarm = self.alarm_queue.get()
            partition = raw_alarm[0]
            offset = raw_alarm[1].offset
            try:
                alarm = json.loads(raw_alarm[1].message.value)
                if not 'tenant_id' in alarm:
                    raise AlarmFormatError
            except Exception, e:  # This is general because of a lack of json exception base class
                log.error("Invalid Alarm format skipping partition %d, offset %d\nErrror%s" % (partition, offset, e))
                self._add_to_finished_queue(partition, offset)
                continue

            log.debug("Read alarm from alarms sent_queue. Partition %d, Offset %d, alarm data %s"
                      % (partition, offset, alarm))

            try:
                cur.execute("SELECT name, type, address FROM notification_method WHERE tenant_id = ?", alarm['tenant_id'])
            except MySQLdb.Error:
                log.exception('Error reading from mysql')

            notifications = []
            for row in cur:
                if row.type not in notification_types:
                    log.warn('Notification type %s is not supported. This is defined for tenant_id %s'
                             % (row.type, alarm['tenant_id']))
                    continue
                notifications.append(
                    notification_types[row.type](partition, offset, alarm['tenant_id'], row.name, row.address))

            if len(notifications) == 0:
                self._add_to_finished_queue(partition, offset)
            else:
                if self.notification_queue.full():
                    log.warn('Notifications sent_queue is full, publishing is blocked')
                self.notification_queue.put(notifications)
                log.debug("Added notifications to sent_queue for alarm Partition %d, Offset %d" % (partition, offset))
