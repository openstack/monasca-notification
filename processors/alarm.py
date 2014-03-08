import logging
import MySQLdb

from notifications.email import EmailNotification

log = logging.getLogger(__name__)


class AlarmProcessor(object):
    def __init__(self, alarm_queue, notification_queue, tracker, mysql_host, mysql_user, mysql_passwd, dbname):
        self.alarm_queue = alarm_queue
        self.notification_queue = notification_queue
        self.tracker = tracker

        self.mysql = MySQLdb.connect(host=mysql_host, user=mysql_user, passwd=mysql_passwd, db=dbname)

    def run(self):
        """ Check the notification setting for this project in mysql then create the appropriate notification or
            mark as finished in the tracker
        """
        while True:
            alarm = self.alarm_queue.get()
            #todo parse the json alarm to a python object, likely a named tuple, also make debug statement more useful
            log.debug("Read alarm from alarms queue")

        #todo figure out mysqldb library
        # if notifications configured in mysql
            # todo this object should be made based on the type
            notification = EmailNotification(alarm)
            if self.notification_queue.full():
                log.debug('Notifications queue is full, publishing is blocked')
            self.notification_queue.put(notification)
            log.debug("Put notification on the notification queue") # todo make this debug info better

        # else
        #self.tracker(finished, alarm.partition, alarm.offset)

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

