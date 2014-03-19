#!/usr/bin/env python
#
"""Used for manually querying/setting offsets associated with the mon_notification daemon.
    This should only be used in unusual circumstances to force reprocessing or skip alarms.
"""

import argparse
import json
import logging
import sys
import yaml

from mon_notification import state_tracker


def listener():
    """Simple listener for ZookeeperStateTracker
    """
    sys.exit(1)


def main():
    # Parse args
    parser = argparse.ArgumentParser(description="Query and set(DANGEROUS) mon_notification kafka consumer offsets\n")
    parser.add_argument('--config', '-c', default='/etc/mon/notification.yaml', help='Configuration File')

    ## Either list or set not both
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', '-l', action='store_true')
    group.add_argument('--set-offsets', '-s',
                       help='A json style dictionary of partition:offset ie {"0": "0", "1": "2", "2": "3"}' +
                            "Only specified partitions are set")

    args = parser.parse_args()

    # Silence most logging from mon_notification
    logging.basicConfig(level=logging.CRITICAL)

    # Parse config and setup state tracker
    config = yaml.load(open(args.config, 'r'))
    tracker = state_tracker.ZookeeperStateTracker(
        config['zookeeper']['url'], config['kafka']['alarm_topic'], None, config['zookeeper']['max_offset_lag'])

    current_offsests = tracker.offsets
    if args.list:
        print(json.dumps(current_offsests))
    else:
        offsets = json.loads(args.set_offsets)
        raw_input("Warning setting offset will affect the behavior of the next notification engine to run.\n" +
                  "\tCtrl-C to exit, enter to continue")
        print("All running mon_notification daemons must be shutdown to allow this process to grab the lock.")

        log = logging.getLogger('mon_notification.state_tracker')
        log.setLevel(logging.DEBUG)

        tracker.lock(listener)
        for partition in offsets.iterkeys():
            tracker._update_offset(int(partition), int(offsets[partition]))

if __name__ == "__main__":
    sys.exit(main())
