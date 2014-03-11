import json
import logging
import MySQLdb

from notifications.email import EmailNotification

log = logging.getLogger(__name__)


class AlarmProcessor(object):
    def __init__(self, alarm_queue, notification_queue, finished_queue, mysql_host, mysql_user, mysql_passwd, dbname):
        self.alarm_queue = alarm_queue
        self.notification_queue = notification_queue
        self.finished_queue = finished_queue

        self.mysql = MySQLdb.connect(host=mysql_host, user=mysql_user, passwd=mysql_passwd, db=dbname)

    def run(self):
        """ Check the notification setting for this project in mysql then create the appropriate notification or
            add to the finished_queue
        """
        cur = self.mysql.cursor()
        notification_types = {
            'EMAIL': EmailNotification
        }
        # todo how to handle a type not implemented? I should log an error but how to make this general
        # can I use a defaultdict and make the default be the base notification that spits out an unimplemented error?
        # Should I instead make static method of the base notification class that handles this
        while True:
            raw_alarm = self.alarm_queue.get()
            partition = raw_alarm[0]
            offset = raw_alarm[1].offset
            alarm = json.loads(raw_alarm[1].message.value)
            # todo error handling around the alarm message format
            log.debug("Read alarm from alarms sent_queue. Partition %d, Offset %d, alarm data %s"
                      % (partition, offset, alarm))

            cur.execute("SELECT name, type, address FROM notification_method WHERE tenant_id = ?", alarm.tenant_id)
            # todo error handling around mysql
            notifications = [
                notification_types[row.type](partition, offset, alarm.tenant_id, row.name, row.address) for row in cur
            ]

            if len(notifications) == 0:
                if self.alarm_queue.full():
                    log.debug('Finished queue is full, publishing is blocked')
                self.alarm_queue.put((partition, offset))
            else:
                if self.notification_queue.full():
                    log.debug('Notifications sent_queue is full, publishing is blocked')
                self.notification_queue.put(notifications)
                log.debug("Put notification on the notification sent_queue, Partition %d, Offset %d" % (partition, offset))
