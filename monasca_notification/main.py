#!/usr/bin/env python
# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" Notification Engine
    This engine reads alarms from Kafka and then notifies the customer using their configured notification method.
"""

import logging
import logging.config
import multiprocessing
import os
import signal
from state_tracker import KafkaStateTracker
import sys
import threading
import time
import yaml

from processors.alarm_processor import AlarmProcessor
from processors.kafka_consumer import KafkaConsumer
from processors.notification_processor import NotificationProcessor
from processors.sent_notification_processor import SentNotificationProcessor

log = logging.getLogger(__name__)
processors = []  # global list to facilitate clean signal handling
exiting = False


def clean_exit(signum, frame=None):
    """Exit all processes attempting to finish uncommited active work before exit.
         Can be called on an os signal or no zookeeper losing connection.
    """
    global exiting
    if exiting:
        # Since this is set up as a handler for SIGCHLD when this kills one child it gets another signal, the global
        # exiting avoids this running multiple times.
        log.debug('Exit in progress clean_exit received additional signal %s' % signum)
        return

    log.info('Received signal %s, beginning graceful shutdown.' % signum)
    exiting = True

    # the final processor is the sent_notification processor, skip it and the tracker both of which should
    # finish processing of any already sent notifications.
    for process in processors[:-1]:
        try:
            if process.is_alive():
                process.terminate()  # Sends sigterm which any processes after a notification is sent attempt to handle
        except Exception:
            pass

    tracker.stop = True
    max_wait_count = 6
    while tracker.has_lock:
        if max_wait_count == 0:
            log.debug('Max wait reached, proceeding to kill processes')
            break
        log.debug('Waiting for all active processing to stop.')
        max_wait_count -= 1
        time.sleep(20)

    # Kill everything, that didn't already die
    for child in multiprocessing.active_children():
        log.debug('Killing pid %s' % child.pid)
        try:
            os.kill(child.pid, signal.SIGKILL)
        except Exception:
            pass

    sys.exit(0)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    if len(argv) == 2:
        config_file = argv[1]
    elif len(argv) > 2:
        print("Usage: " + argv[0] + " <config_file>")
        print("Config file defaults to /etc/monasca/notification.yaml")
        return 1
    else:
        config_file = '/etc/monasca/notification.yaml'

    config = yaml.load(open(config_file, 'r'))

    # Setup logging
    logging.config.dictConfig(config['logging'])

    # Create the queues
    alarms = multiprocessing.Queue(config['queues']['alarms_size'])
    notifications = multiprocessing.Queue(config['queues']['notifications_size'])  # [notification_object, ]
    sent_notifications = multiprocessing.Queue(config['queues']['sent_notifications_size'])  # [notification_object, ]
    finished = multiprocessing.Queue(config['queues']['finished_size'])  # Data is of the form (partition, offset)

    # State Tracker - Used for tracking the progress of fully processed alarms and the zookeeper lock
    global tracker  # Set to global for use in the cleanup function
    tracker = KafkaStateTracker(finished, config['kafka']['url'], config['kafka']['group'],
                                config['kafka']['alarm_topic'], config['kafka']['max_offset_lag'],
                                config['zookeeper']['url'])
    tracker.lock(clean_exit)  # Only begin if we have the processing lock
    tracker_thread = threading.Thread(target=tracker.run)

    # Define processors
    # KafkaConsumer
    kafka = multiprocessing.Process(
        target=KafkaConsumer(
            alarms,
            config['kafka']['url'],
            config['kafka']['group'],
            config['kafka']['alarm_topic']
        ).run
    )
    processors.append(kafka)

    # AlarmProcessors
    alarm_processors = []
    for i in range(config['processors']['alarm']['number']):
        alarm_processors.append(multiprocessing.Process(
            target=AlarmProcessor(
                alarms,
                notifications,
                finished,
                config['processors']['alarm']['ttl'],
                config['mysql']['host'],
                config['mysql']['user'],
                config['mysql']['passwd'],
                config['mysql']['db']
            ).run),
        )
    processors.extend(alarm_processors)

    # NotificationProcessors
    notification_processors = []
    for i in range(config['processors']['notification']['number']):
        notification_processors.append(multiprocessing.Process(
            target=NotificationProcessor(
                notifications,
                sent_notifications,
                finished,
                config['email']
            ).run),
        )
    processors.extend(notification_processors)

    # SentNotificationProcessor
    sent_notification_processor = multiprocessing.Process(
        target=SentNotificationProcessor(
            sent_notifications,
            finished,
            config['kafka']['url'],
            config['kafka']['notification_topic']
        ).run
    )
    processors.append(sent_notification_processor)

    # Start
    try:
        log.info('Starting processes')
        for process in processors:
            process.start()

        # The offset tracker runs in a thread so the signal handler can run concurrently and cleanly shutdown
        tracker_thread.start()

        # The signal handlers must be added after the processes start otherwise they run on all processes
        signal.signal(signal.SIGCHLD, clean_exit)
        signal.signal(signal.SIGINT, clean_exit)
        signal.signal(signal.SIGTERM, clean_exit)

        # If the tracker fails exit
        while True:
            if tracker_thread.is_alive():
                time.sleep(5)
            else:
                tracker.has_lock = False
                clean_exit('tracker died', None)
    except Exception:
        log.exception('Error! Exiting.')
        for process in processors:
            process.terminate()

if __name__ == "__main__":
    sys.exit(main())
