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
        while True:
            raw_alarm = self.alarm_queue.get()
            partition = raw_alarm[0]
            offset = raw_alarm[1].offset
            alarm = raw_alarm[1].message.value
            log.debug("Read alarm from alarms sent_queue. Partition %d, Offset %d, alarm data %s"
                      % (partition, offset, alarm))

        #todo figure out mysqldb library
        # if notifications configured in mysql
            # todo this object should be made based on the type
            notification = EmailNotification(partition, offset)
            if self.notification_queue.full():
                log.debug('Notifications sent_queue is full, publishing is blocked')
            self.notification_queue.put(notification)
            log.debug("Put notification on the notification sent_queue, Partition %d, Offset %d" % (partition, offset))

        # else
        #self.finished_queue.put((alarm.partition, alarm.offset))

# This seems to be the key table
#mysql> describe notification_method;
#+------------+---------------------+------+-----+---------+-------+
#| Field      | Type                | Null | Key | Default | Extra |
#+------------+---------------------+------+-----+---------+-------+
#| id         | varchar(36)         | NO   | PRI | NULL    |       |
#| tenant_id  | varchar(36)         | NO   |     | NULL    |       |
#| name       | varchar(250)        | YES  |     | NULL    |       |
#| type       | enum('EMAIL','SMS') | NO   |     | NULL    |       |
#| address    | varchar(100)        | YES  |     | NULL    |       |
#| created_at | datetime            | NO   |     | NULL    |       |
#| updated_at | datetime            | NO   |     | NULL    |       |
#+------------+---------------------+------+-----+---------+-------+

