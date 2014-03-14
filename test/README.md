Basic testing.
Note that mini-mon is set to use smtp3.hp.com which must be used from within the HP corporate network.

# Load some notifications into the db.
- First edit the last line of test_notifications.sql to add in your email
- From the mysql vm run `mysql -uroot -ppassword mon < sample_notifications.sql`
- It is helpful to watch the log file, `tail -f /var/log/mon-notification/notification.log`
  - If desired edit /usr/share/pyshared/mon_notification/main.py to change logging.INFO to logging.DEBUG
- Then for all of the json files or just some run
  `/opt/kafka/bin/kafka-console-producer.sh --broker 192.168.10.10:9092 --topic alarm-state-transitions < *.json`
