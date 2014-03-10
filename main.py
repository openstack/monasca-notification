#!/usr/bin/env python
#
""" Notification Engine
    This engine reads alarms from Kafka and then notifies the customer using their configured notification method.
"""

import logging
import yaml
from multiprocessing import Process, Queue
import os
import signal
import sys

from state_tracker import ZookeeperStateTracker
from kafka_consumer import KafkaConsumer
from processors.alarm import AlarmProcessor
from processors.notification import NotificationProcessor
from processors.sent_notification import SentNotificationProcessor

log = logging.getLogger(__name__)
processors = []  # global list to facilitate clean signal handling


def clean_exit(signum, frame=None):
    """ Exit all processes cleanly
        Can be called on an os signal or no zookeeper loosing connection.
    """
    for process in processors:
        process.terminate()

    sys.exit(0)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    if len(argv) == 2:
        config_file = argv[1]
    elif len(argv) > 2:
        print "Usage: " + argv[0] + " <config_file>"
        print "Config file defaults to /etc/mon/notification.yaml"
        return 1
    else:
        config_file = '/etc/mon/notification.yaml'

    config = yaml.load(open(config_file, 'r'))

    # Setup logging
    log_path = os.path.join(config['log_dir'], 'notification.log')
    #todo restore normal logging
    logging.basicConfig(level=logging.DEBUG)
#    logging.basicConfig(format='%(asctime)s %(message)s', filename=log_path, level=logging.INFO)
    kazoo_logger = logging.getLogger('kazoo')
    kazoo_logger.setLevel(logging.WARN)
    kafka_logger = logging.getLogger('kafka')
    kafka_logger.setLevel(logging.WARN)

    #Create the queues
    alarms = Queue(config['queues']['alarms_size'])
    notifications = Queue(config['queues']['notifications_size'])
    sent_notifications = Queue(config['queues']['sent_notifications_size'])
    finished = Queue(config['queues']['finished_size'])  # Data added here should be of the form (partition, offset)

    #State Tracker - Used for tracking the progress of fully processed alarms and the zookeeper lock
    tracker = ZookeeperStateTracker(config['zookeeper']['url'], config['kafka']['alarm_topic'], finished)
    tracker.lock(clean_exit)  # Only begin if we have the processing lock

    ## Define processors
    #KafkaConsumer
    kafka = Process(
        target=KafkaConsumer(
            alarms,
            config['kafka']['url'],
            config['kafka']['group'],
            config['kafka']['alarm_topic'],
            tracker.get_offsets()
        ).run
    )
    processors.append(kafka)

    #AlarmProcessors
    alarm_processors = []
    for i in xrange(config['processors']['alarm']['number']):
        alarm_processors.append(Process(
            target=AlarmProcessor(
                alarms,
                notifications,
                finished,
                config['mysql']['host'],
                config['mysql']['user'],
                config['mysql']['passwd'],
                config['mysql']['db']
            ).run)
        )
    processors.extend(alarm_processors)

    #NotificationProcessors
    notification_processors = []
    for i in xrange(config['processors']['notification']['number']):
        notification_processors.append(Process(target=NotificationProcessor(notifications, sent_notifications).run))
    processors.extend(notification_processors)

    #SentNotificationProcessor
    sent_notification_processor = Process(
        target=SentNotificationProcessor(
            sent_notifications,
            finished,
            config['kafka']['url'],
            config['kafka']['notification_topic']
        ).run
    )
    processors.append(sent_notification_processor)

    ## Start
    signal.signal(signal.SIGTERM, clean_exit)
    try:
        log.info('Starting processes')
        for process in processors:
            process.start()
        tracker.run()  # Runs in the main class
    except:
        log.exception('Error exiting!')
        for process in processors:
            process.terminate()

if __name__ == "__main__":
    sys.exit(main())


