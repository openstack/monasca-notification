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

from kafka_consumer import KafkaConsumer
from processors.alarm import AlarmProcessor
from processors.notification import NotificationProcessor
from processors.sent_notification import SentNotificationProcessor

log = logging.getLogger(__name__)
processors = []  # global list to facilitate clean signal handling


def clean_exit(signum, frame):
    """ Exit cleanly on defined signals
    """
    # todo - Figure out good exiting. For most situations, make sure it all shuts down nicely, finishing up anything in the queue
    for process in processors:
        process.terminate()


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
    logging.basicConfig(format='%(asctime)s %(message)s', filename=log_path, level=logging.INFO)

    #Create the queues
    alarms = Queue(config['queues']['alarms_size'])
    notifications = Queue(config['queues']['notifications_size'])
    sent_notifications = Queue(config['queues']['sent_notifications_size'])

    ## Define processes
    #start KafkaConsumer
    kafka = Process(target=KafkaConsumer(config, alarms).run)  # todo don't pass the config object just the bits needed
    processors.append(kafka)

    #Define AlarmProcessors
    alarm_processors = []
    for i in xrange(config['processors']['alarm']['number']):
        alarm_processors.append(Process(target=AlarmProcessor(config, alarms, notifications).run))  # todo don't pass the config object just the bits needed
    processors.extend(alarm_processors)

    #Define NotificationProcessors
    notification_processors = []
    for i in xrange(config['processors']['notification']['number']):
        notification_processors.append(Process(target=NotificationProcessor(config, notifications, sent_notifications).run))  # todo don't pass the config object just the bits needed
    processors.extend(notification_processors)

    #Define SentNotificationProcessor
    sent_notification_processor = Process(target=SentNotificationProcessor(config, sent_notifications).run)  # todo don't pass the config object just the bits needed
    processors.append(sent_notification_processor)

    ## Start
    signal.signal(signal.SIGTERM, clean_exit)
    try:
        log.info('Starting processes')
        for process in processors:
            process.start()
    except:
        log.exception('Error exiting!')
        for process in processors:
            process.terminate()


# todo - I need to make a deb for kafka-python, code currently in ~/working/kafka-python

if __name__ == "__main__":
    sys.exit(main())

