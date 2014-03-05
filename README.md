# Notification Engine

This engine reads alarms from Kafka and then notifies the customer using their configured notification method.

# Architecture
There are four processing steps separated by queues implemented with python multiprocessing. The steps are:

1. Reads Alarms from Kafka, with no auto commit. - KafkaConsumer class
2. Determine notification type for an alarm. Done by reading from mysql. - AlarmProcessor class
3. Send Notification. - NotificationProcessor class
4. Add sent notifications to Kafka, notification topic, commit the processed alarms with kafka. - SentNotificationProcessor class

There are three internal queues:

1. alarms - kafka alarms are added to this queue.
2. notifications - notifications to be sent are added to this queue. Consists of Notification objects.
3. sent_notifications - notifications that have been sent are added here. Consists of Notification objects.

Notification classes inherit from the notification abstract class and implement their specific notification method.

## High Availability
HA is handled by utilizing multiple partitions withing kafka. When multiple notification engines are running the partitions
are spread out among them, as engines die/restart things reshuffle.

When reading from the alarm topic no committing is done. The committing is done in sent_notification processor. This allows
the processing to continue even though some notifications can be slow. In the event of a catastrophic failure some
notifications could be sent but the alarms not yet acknowledged. This is an acceptable failure mode, better to send a
notification twice than not at all.

It is assumed the notification engine will be run by a process supervisor which will restart it in case of a failure.

# Operation
Yaml config file by default in '/etc/mon/notification.yaml' process runs via upstart script.

# Future Considerations
- How fast is the mysql db? How much load do we put on it. Initially I think it makes most sense to read notification
  details for each alarm but eventually I may want to cache that info.
- I am starting with a single KafkaConsumer and a single SentNotificationProcessor depending on load this may need
  to scale.
