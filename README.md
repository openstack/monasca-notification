# Notification Engine

This engine reads alarms from Kafka and then notifies the customer using their configured notification method.

# Architecture
There are four processing steps separated by queues implemented with python multiprocessing. The steps are:

1. Reads Alarms from Kafka, with no auto commit. - KafkaConsumer class
2. Determine notification type for an alarm. Done by reading from mysql. - AlarmProcessor class
3. Send Notification. - NotificationProcessor class
4. Add sent notifications to Kafka on the notification topic. - SentNotificationProcessor class

There is also a special processing step, the ZookeeperStateTracker, that runs in the main thread and keeps track of the
last committed message and ones available for commit, it then periodically commits all progress. This handles the
situation where alarms that are not acted on are quickly ready for commit but others which are prior to them in the
kafka order are still in progress. Locking is also handled by this class, so all zookeeper functionality is tracked in
this class.

There are 4 internal queues:

1. alarms - kafka alarms are added to this queue.
2. notifications - notifications to be sent, grouped by source alarm are added to this queue.
   Consists of a list of Notification objects.
3. sent_notifications - notifications that have been sent are added here. Consists of Notification objects.
4. finished - alarms that are done with processing, either the notification is sent or there was none.

## High Availability
HA is handled by utilizing multiple partitions withing kafka. When multiple notification engines are running the partitions
are spread out among them, as engines die/restart things reshuffle.

When reading from the alarm topic no committing is done. The committing is done in sent_notification processor. This allows
the processing to continue even though some notifications can be slow. In the event of a catastrophic failure some
notifications could be sent but the alarms not yet acknowledged. This is an acceptable failure mode, better to send a
notification twice than not at all.

It is assumed the notification engine will be run by a process supervisor which will restart it in case of a failure.

# Operation
Yaml config file by default is in '/etc/mon/notification.yaml'. The daemon runs via an upstart script.

# Future Considerations
- Currently I lock the topic rather than the partitions. This effectively means there is only one active notification
  engine at any given time. In the future to share the load among multiple daemons we could lock by partition.
- The ZookeeperStateTracker is a likely place to end up as a bottleneck on high throughput. Detailed investigation of
  its speed should be done.
- How fast is the mysql db? How much load do we put on it. Initially I think it makes most sense to read notification
  details for each alarm but eventually I may want to cache that info.
- I am starting with a single KafkaConsumer and a single SentNotificationProcessor depending on load this may need
  to scale.
