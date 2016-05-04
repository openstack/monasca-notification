# (C) Copyright 2014-2016 Hewlett Packard Enterprise Development Company LP
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
import sys
import time
import yaml

from notification_engine import NotificationEngine
from periodic_engine import PeriodicEngine
from retry_engine import RetryEngine

log = logging.getLogger(__name__)
processors = []  # global list to facilitate clean signal handling
exiting = False


def clean_exit(signum, frame=None):
    """Exit all processes attempting to finish uncommited active work before exit.
         Can be called on an os signal or no zookeeper losing connection.
    """
    global exiting
    if exiting:
        # Since this is set up as a handler for SIGCHLD when this kills one
        # child it gets another signal, the global exiting avoids this running
        # multiple times.
        log.debug('Exit in progress clean_exit received additional signal %s' % signum)
        return

    log.info('Received signal %s, beginning graceful shutdown.' % signum)
    exiting = True
    wait_for_exit = False

    for process in processors:
        try:
            if process.is_alive():
                process.terminate()  # Sends sigterm which any processes after a notification is sent attempt to handle
                wait_for_exit = True
        except Exception:
            pass

    # wait for a couple seconds to give the subprocesses a chance to shut down correctly.
    if wait_for_exit:
        time.sleep(2)

    # Kill everything, that didn't already die
    for child in multiprocessing.active_children():
        log.debug('Killing pid %s' % child.pid)
        try:
            os.kill(child.pid, signal.SIGKILL)
        except Exception:
            pass

    if signum == signal.SIGTERM:
        sys.exit(0)

    sys.exit(signum)


def start_process(process_type, config, *args):
    log.info("start process: {}".format(process_type))
    p = process_type(config, *args)
    p.run()


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

    for proc in range(0, config['processors']['notification']['number']):
        processors.append(multiprocessing.Process(
            target=start_process, args=(NotificationEngine, config)))

    processors.append(multiprocessing.Process(
        target=start_process, args=(RetryEngine, config)))

    if 60 in config['kafka']['periodic']:
        processors.append(multiprocessing.Process(
            target=start_process, args=(PeriodicEngine, config, 60)))

    try:
        log.info('Starting processes')
        for process in processors:
            process.start()

        # The signal handlers must be added after the processes start otherwise
        # they run on all processes
        signal.signal(signal.SIGCHLD, clean_exit)
        signal.signal(signal.SIGINT, clean_exit)
        signal.signal(signal.SIGTERM, clean_exit)

        while True:
            time.sleep(10)

    except Exception:
        log.exception('Error! Exiting.')
        clean_exit(signal.SIGKILL)

if __name__ == "__main__":
    sys.exit(main())
