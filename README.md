Team and repository tags
========================

[![Team and repository tags](https://governance.openstack.org/badges/monasca-notification.svg)](https://governance.openstack.org/reference/tags/index.html)

<!-- Change things from this point on -->

# Notification Engine

This engine reads alarms from Kafka and then notifies the customer using their configured notification method.
Multiple notification and retry engines can run in parallel up to one per available Kafka partition.  Zookeeper
is used to negotiate access to the Kafka partitions whenever a new process joins or leaves the working set.

# Architecture
The notification engine generates notifications using the following steps:
1. Reads Alarms from Kafka, with no auto commit. - KafkaConsumer class
2. Determine notification type for an alarm. Done by reading from mysql. - AlarmProcessor class
3. Send Notification. - NotificationProcessor class
4. Successful notifications are added to a sent notification topic. - NotificationEngine class
5. Failed notifications are added to a retry topic. - NotificationEngine class
6. Commit offset to Kafka - KafkaConsumer class

The notification engine uses three Kafka topics:
1. alarm_topic: Alarms inbound to the notification engine.
2. notification_topic: Successfully sent notifications.
3. notification_retry_topic: Unsuccessful notifications.

A retry engine runs in parallel with the notification engine and gives any
failed notification a configurable number of extra chances at succeess.

The retry engine generates notifications using the following steps:
1. Reads Notification json data from Kafka, with no auto commit. - KafkaConsumer class
2. Rebuild the notification that failed. - RetryEngine class
3. Send Notification. - NotificationProcessor class
4. Successful notifictions are added to a sent notification topic. - RetryEngine class
5. Failed notifications that have not hit the retry limit are added back to the retry topic. - RetryEngine class
6. Failed notifications that have hit the retry limit are discarded. - RetryEngine class
6. Commit offset to Kafka - KafkaConsumer class

The retry engine uses two Kafka topics:
1. notification_retry_topic: Notifications that need to be retried.
2. notification_topic: Successfully sent notifications.

## Fault Tolerance
When reading from the alarm topic no committing is done. The committing is done only after processing. This allows
the processing to continue even though some notifications can be slow. In the event of a catastrophic failure some
notifications could be sent but the alarms not yet acknowledged. This is an acceptable failure mode, better to send a
notification twice than not at all.

The general process when a major error is encountered is to exit the daemon which should allow the other processes to
renegotiate access to the Kafka partitions.  It is also assumed the notification engine will be run by a process
supervisor which will restart it in case of a failure. This way any errors which are not easy to recover from are
automatically handled by the service restarting and the active daemon switching to another instance.

Though this should cover all errors there is risk that an alarm or set of alarms can be processed and notifications
sent out multiple times. To minimize this risk a number of techniques are used:

- Timeouts are implemented with all notification types.
- An alarm TTL is utilized. Any alarm older than the TTL is not processed.

# Operation
Yaml config file by default is in '/etc/monasca/notification.yaml', a sample is in this project.

## Monitoring
statsd is incorporated into the daemon and will send all stats to statsd server launched by monasca-agent.
Default host and port points at **localhost:8125**.

- Counters
    - ConsumedFromKafka
    - AlarmsFailedParse
    - AlarmsNoNotification
    - NotificationsCreated
    - NotificationsSentSMTP
    - NotificationsSentWebhook
    - NotificationsSentPagerduty
    - NotificationsSentFailed
    - NotificationsInvalidType
    - AlarmsFinished
    - PublishedToKafka
- Timers
    - ConfigDBTime
    - SendNotificationTime

# Future Considerations
- More extensive load testing is needed
  - How fast is the mysql db? How much load do we put on it. Initially I think it makes most sense to read notification
    details for each alarm but eventually I may want to cache that info.
  - How expensive are commits to Kafka for every message we read?  Should we commit every N messages?
  - How efficient is the default Kafka consumer batch size?
  - Currently we can get ~200 notifications per second per NotificationEngine instance using webhooks to a local 
    http server.  Is that fast enough?
  - Are we putting too much load on Kafka at ~200 commits per second?

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
