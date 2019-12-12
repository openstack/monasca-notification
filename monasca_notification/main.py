# (C) Copyright 2014-2017 Hewlett Packard Enterprise Development LP
# Copyright 2017 FUJITSU LIMITED
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
    This engine reads alarms from Kafka and then notifies the customer using their configured
    notification method.
"""

import multiprocessing
import os
import signal
import sys
import time
import warnings

from oslo_log import log

from monasca_notification import config
from monasca_notification import notification_engine
from monasca_notification import periodic_engine
from monasca_notification import retry_engine

LOG = log.getLogger(__name__)
CONF = config.CONF

processors = []  # global list to facilitate clean signal handling
exiting = False


def clean_exit(signum, frame=None):
    """Exit all processes attempting to finish uncommitted active work before exit.
         Can be called on an os signal or no zookeeper losing connection.
    """
    global exiting
    if exiting:
        # Since this is set up as a handler for SIGCHLD when this kills one
        # child it gets another signal, the global exiting avoids this running
        # multiple times.
        LOG.debug('Exit in progress clean_exit received additional signal %s' % signum)
        return

    LOG.info('Received signal %s, beginning graceful shutdown.' % signum)
    exiting = True
    wait_for_exit = False

    for process in processors:
        try:
            if process.is_alive():
                # Sends sigterm which any processes after a notification is sent attempt to handle
                process.terminate()
                wait_for_exit = True
        except Exception:  # nosec
            # There is really nothing to do if the kill fails, so just go on.
            # The # nosec keeps bandit from reporting this as a security issue
            pass

    # wait for a couple seconds to give the subprocesses a chance to shut down correctly.
    if wait_for_exit:
        time.sleep(2)

    # Kill everything, that didn't already die
    for child in multiprocessing.active_children():
        LOG.debug('Killing pid %s' % child.pid)
        try:
            os.kill(child.pid, signal.SIGKILL)
        except Exception:  # nosec
            # There is really nothing to do if the kill fails, so just go on.
            # The # nosec keeps bandit from reporting this as a security issue
            pass

    if signum == signal.SIGTERM:
        sys.exit(0)

    sys.exit(signum)


def start_process(process_type, *args):
    LOG.info("start process: {}".format(process_type))
    p = process_type(*args)
    p.run()


def main(argv=None):
    warnings.simplefilter('always')
    config.parse_args(argv=argv)

    for proc in range(0, CONF.notification_processor.number):
        processors.append(multiprocessing.Process(
            target=start_process,
            args=(notification_engine.NotificationEngine,))
        )

    processors.append(multiprocessing.Process(
        target=start_process,
        args=(retry_engine.RetryEngine,))
    )

    for notification_period in CONF.kafka.periodic.keys():
        processors.append(multiprocessing.Process(
            target=start_process,
            args=(periodic_engine.PeriodicEngine, int(notification_period)))
        )

    try:
        LOG.info('Starting processes')
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
        LOG.exception('Error! Exiting.')
        clean_exit(signal.SIGKILL)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
