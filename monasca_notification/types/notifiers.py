# (C) Copyright 2015,2016 Hewlett Packard Enterprise Development LP
# Copyright 2017 Fujitsu LIMITED
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

import time

from debtcollector import removals
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils

from monasca_notification.plugins import email_notifier
from monasca_notification.plugins import pagerduty_notifier
from monasca_notification.plugins import webhook_notifier

log = logging.getLogger(__name__)
CONF = cfg.CONF

possible_notifiers = None
configured_notifiers = None
statsd_counter = None

statsd = None
statsd_timer = None


def init(statsd_obj):
    global statsd, statsd_timer, \
        possible_notifiers, configured_notifiers,\
        statsd_counter

    statsd = statsd_obj
    statsd_timer = statsd.get_timer()

    statsd_counter = {}
    configured_notifiers = {}

    possible_notifiers = [
        email_notifier.EmailNotifier(log),
        webhook_notifier.WebhookNotifier(log),
        pagerduty_notifier.PagerdutyNotifier(log)
    ]


def load_plugins():
    global possible_notifiers
    for plugin_class in CONF.notification_types.enabled:
        try:
            plugin_class = plugin_class.replace(':', '.')
            clz = importutils.import_class(plugin_class)
            possible_notifiers.append(clz(logging.getLogger(plugin_class)))
        except Exception:
            log.exception("unable to load the class %s , ignoring it" %
                          plugin_class)


def enabled_notifications():
    global configured_notifiers

    results = []
    for key in configured_notifiers:
        results.append(key.upper())
    return results


@removals.remove(
    message='Loading the plugin configuration has been moved to oslo, '
            'This method will be fully deleted in future releases',
    version='1.9.0',
    removal_version='3.0.0'
)
def config():
    global possible_notifiers, configured_notifiers, statsd_counter

    for notifier in possible_notifiers:
        ntype = notifier.type.lower()
        configured_notifiers[ntype] = notifier
        statsd_counter[ntype] = statsd.get_counter(notifier.statsd_name)
        log.info("{} notification ready".format(ntype))


def send_notifications(notifications):
    sent = []
    failed = []
    invalid = []

    for notification in notifications:
        ntype = notification.type
        if ntype not in configured_notifiers:
            log.warn("attempting to send unconfigured notification: {}".format(ntype))
            invalid.append(notification)
            continue

        notification.notification_timestamp = time.time()

        with statsd_timer.time(ntype + '_time'):
            result = send_single_notification(notification)

        if result:
            sent.append(notification)
            statsd_counter[ntype].increment(1)
        else:
            failed.append(notification)

    return sent, failed, invalid


def send_single_notification(notification):
    global configured_notifiers

    ntype = notification.type
    try:
        return configured_notifiers[ntype].send_notification(notification)
    except Exception:
        log.exception("send_notification exception for {}".format(ntype))
        return False
