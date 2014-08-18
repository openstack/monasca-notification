# Notification Engine

This engine reads alarms from Kafka and then notifies the customer using their configured notification method.

# Architecture
There are four processing steps separated by queues implemented with python multiprocessing. The steps are:

1. Reads Alarms from Kafka, with no auto commit. - KafkaConsumer class
2. Determine notification type for an alarm. Done by reading from mysql. - AlarmProcessor class
3. Send Notification. - NotificationProcessor class
4. Add sent notifications to Kafka on the notification topic. - SentNotificationProcessor class

There is also a special processing step, the KafkaStateTracker, that runs in the main thread and keeps track of the
last committed message and ones available for commit, it then periodically commits all progress. This handles the
situation where alarms that are not acted on are quickly ready for commit but others which are prior to them in the
kafka order are still in progress. Locking is also handled by this class using zookeeper.

There are 4 internal queues:

1. alarms - kafka alarms are added to this queue.
2. notifications - notifications to be sent, grouped by source alarm are added to this queue.
   Consists of a list of Notification objects.
3. sent_notifications - notifications that have been sent are added here. Consists of Notification objects.
4. finished - alarms that are done with processing, either the notification is sent or there was none.

## High Availability
HA is handled by running multiple notification engines. Only one at a time is active if it dies another can take
over and continue from where it left. A zookeeper lock file is used to ensure only one running daemon. If needed
the code can be modified to use kafka partitions to have multiple active engines working on different alarms.

## Fault Tolerance
When reading from the alarm topic no committing is done. The committing is done only after processing. This allows
the processing to continue even though some notifications can be slow. In the event of a catastrophic failure some
notifications could be sent but the alarms not yet acknowledged. This is an acceptable failure mode, better to send a
notification twice than not at all.

The general process when a major error is encountered is to exit the daemon which should allow another daemon to take
over according to the HA strategy. It is also assumed the notification engine will be run by a process supervisor which
will restart it in case of a failure. This way any errors which are not easy to recover from are automatically handled
by the service restarting and the active daemon switching to another instance.

Though this should cover all errors there is risk that an alarm or set of alarms can be processed and notifications
sent out multiple times. To minimize this risk a number of techniques are used:

- Timeouts are implemented with all notification types.
- On shutdown uncommitted work is finished up.
- An alarm TTL is utilized. Any alarm older than the TTL is not processed.
- A maximum offset lag time is set. The offset is normally only updated if there is a continuous chain of finished
  alarms. If there is a new offset that arrives yet still a gap it is normally held in reserve. If the maximum lag
  time has been set and exceeded when a new finished alarm comes in the offset is updated regardless of gaps.

# Operation
Yaml config file by default is in '/etc/monasca/notification.yaml', a sample is in this project.

## Monitoring
statsd is incorporated into the daemon and will send all stats to localhost on udp port 8125. In many cases the stats
are gathered per thread, the thread number is indicated by a -# at the end of the name.

- Counters
    - ConsumedFromKafka
    - AlarmsFailedParse
    - AlarmsFinished
    - AlarmsNoNotification
    - AlarmsOffsetUpdated
    - NotificationsCreated
    - NotificationsSentSMTP
    - NotificationsSentFailed
    - NotificationsInvalidType
    - PublishedToKafka
- Timers
    - ConfigDBTime
    - SMTPTime
    - OffsetCommitTime

# Future Considerations
- Currently I lock the topic rather than the partitions. This effectively means there is only one active notification
  engine at any given time. In the future to share the load among multiple daemons we could lock by partition.
- More extensive load testing is needed
  - How fast is the mysql db? How much load do we put on it. Initially I think it makes most sense to read notification
    details for each alarm but eventually I may want to cache that info.
  - I am starting with a single KafkaConsumer and a single SentNotificationProcessor depending on load this may need
    to scale.
  - How fast is the state tracker? Do I need to scale or speed that up at all?

# License

Copyright (c) 2014 Hewlett-Packard Development Company, L.P.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
    
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied.
See the License for the specific language governing permissions and
limitations under the License.
