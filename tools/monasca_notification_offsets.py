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

"""Used for manually querying/setting offsets associated with the monasca_notification daemon.
    This should only be used in unusual circumstances to force reprocessing or skip alarms.
"""

import argparse
import json
import logging
import sys
import yaml

from monasca_notification import state_tracker


def listener():
    """Simple listener for KafkaStateTracker
    """
    sys.exit(1)


def main():
    # Parse args
    parser = argparse.ArgumentParser(description="Query and set(DANGEROUS) monasca_notification kafka offsets\n")
    parser.add_argument('--config', '-c', default='/etc/monasca/notification.yaml', help='Configuration File')

    # Either list or set not both
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', '-l', action='store_true')
    group.add_argument('--set-offsets', '-s',
                       help='A json style dictionary of partition:offset ie {"0": "0", "1": "2", "2": "3"}' +
                            "Only specified partitions are set")

    args = parser.parse_args()

    # Silence most logging from monasca_notification
    logging.basicConfig(level=logging.CRITICAL)

    # Parse config and setup state tracker
    config = yaml.load(open(args.config, 'r'))
    tracker = state_tracker.KafkaStateTracker(None, config['kafka']['url'], config['kafka']['group'],
                                              config['kafka']['alarm_topic'], config['kafka']['max_offset_lag'],
                                              config['zookeeper']['url'])

    if args.list:
        print(json.dumps(tracker.offsets))
    else:
        offsets = json.loads(args.set_offsets)
        raw_input("Warning setting offset will affect the behavior of the next notification engine to run.\n" +
                  "\tCtrl-C to exit, enter to continue")
        print("All running monasca_notification daemons must be shutdown to allow this process to grab the lock.")

        log = logging.getLogger('monasca_notification.state_tracker')
        log.setLevel(logging.DEBUG)

        tracker.lock(listener)
        for partition in offsets.iterkeys():
            tracker.update_offset(int(partition), int(offsets[partition]))

if __name__ == "__main__":
    sys.exit(main())
