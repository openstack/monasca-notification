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
import time

from kazoo.client import KazooClient
from kazoo.exceptions import KazooException

from commit_tracker import KafkaCommitTracker
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
    # todo - Figure out good exiting. For most situations, make sure it all shuts down nicely, finishing up anything in the queue
    for process in processors:
        process.terminate()
    sys.exit(0)


def get_zookeeper_lock(url, topic):
    """ Grab a lock in zookeeper or if not available retry in 30x
        Add a listener to stop processes on
    """
    topic_path = '/consumers/mon-notification/%s' % topic
    zookeeper = KazooClient(url)
    zookeeper.start()

    while True:
        # The path is ephemeral so if it exists wait then cycle again
        if zookeeper.exists(topic_path):
            log.info('Another process has the lock for topic %s, waiting then retrying.' % topic)
            time.sleep(30)
            continue

        try:
            zookeeper.create(topic_path, ephemeral=True, makepath=True)
        except KazooException, e:
            # If creating the path fails something beat us to it most likely, try again
            log.debug('Error creating lock path %s\n%s' % (topic_path, e))
            continue
        else:
            # Succeeded in grabbing the lock continue
            log.info('Grabbed lock for topic %s' % topic)
            break

    # Set up a listener to exit if we loose connection, this always exits even if the zookeeper connection is only
    # suspended, the process should be supervised so it starts right back up again.
    zookeeper.add_listener(clean_exit)


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

    # Todo review the code structure, is there a better design I could use?

    #Create the queues
    alarms = Queue(config['queues']['alarms_size'])
    notifications = Queue(config['queues']['notifications_size'])
    sent_notifications = Queue(config['queues']['sent_notifications_size'])

    ## Define processes
    #start KafkaConsumer
    kafka = Process(target=KafkaConsumer(config['kafka']['url'], config['kafka']['group'], config['kafka']['alarm_topic'], alarms, config['zookeeper']['url']).run)
    processors.append(kafka)

#    #Define AlarmProcessors
#    alarm_processors = []
#    for i in xrange(config['processors']['alarm']['number']):
#        alarm_processors.append(Process(target=AlarmProcessor(config, alarms, notifications).run))  # todo don't pass the config object just the bits needed
#    processors.extend(alarm_processors)
#
#    #Define NotificationProcessors
#    notification_processors = []
#    for i in xrange(config['processors']['notification']['number']):
#        notification_processors.append(Process(target=NotificationProcessor(config, notifications, sent_notifications).run))  # todo don't pass the config object just the bits needed
#    processors.extend(notification_processors)
#
    #Define SentNotificationProcessor
    tracker = KafkaCommitTracker(config['zookeeper']['url'], config['kafka']['alarm_topic'])
    # todo temp setup with the wrong queue to just test kafka basics
    sent_notification_processor = Process(target=SentNotificationProcessor(config['kafka']['url'], config['kafka']['notification_topic'], alarms, tracker).run)
#    sent_notification_processor = Process(
#        target=SentNotificationProcessor(
#            config['kafka']['url'],
#            config['kafka']['notification_topic'],
#            sent_notifications,
#            tracker
#        ).run
#    )
    processors.append(sent_notification_processor)

    ## Start
    signal.signal(signal.SIGTERM, clean_exit)
    get_zookeeper_lock(config['zookeeper']['url'], config['kafka']['alarm_topic'])
    try:
        log.info('Starting processes')
        for process in processors:
            process.start()
    except:
        log.exception('Error exiting!')
        for process in processors:
            process.terminate()

if __name__ == "__main__":
    sys.exit(main())


