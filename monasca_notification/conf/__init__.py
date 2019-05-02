# Copyright 2017 FUJITSU LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import collections
import copy

from oslo_config import cfg
from oslo_log import log
from oslo_utils import importutils

from monasca_notification.conf import database
from monasca_notification.conf import kafka
from monasca_notification.conf import keystone
from monasca_notification.conf import notifiers
from monasca_notification.conf import processors
from monasca_notification.conf import queues
from monasca_notification.conf import retry
from monasca_notification.conf import statsd
from monasca_notification.conf import zookeeper
from monasca_notification.plugins import email_notifier
from monasca_notification.plugins import hipchat_notifier
from monasca_notification.plugins import jira_notifier
from monasca_notification.plugins import pagerduty_notifier
from monasca_notification.plugins import slack_notifier
from monasca_notification.plugins import webhook_notifier

LOG = log.getLogger(__name__)
CONF = cfg.CONF

CONF_OPTS = [
    database,
    kafka,
    keystone,
    notifiers,
    processors,
    queues,
    retry,
    statsd,
    zookeeper
]


def register_opts(conf=None):
    if conf is None:
        conf = CONF
    for m in CONF_OPTS:
        m.register_opts(conf)


def register_enabled_plugin_opts(conf=None):
    if conf is None:
        conf = CONF
    for enabled_plugin in conf.notification_types.enabled:
        ep_module = importutils.import_module(enabled_plugin.split(":")[0])
        ep_module.register_opts(conf)


def list_opts():
    PLUGIN_CONF_OPTS = [slack_notifier, jira_notifier,
                        hipchat_notifier, email_notifier,
                        webhook_notifier, pagerduty_notifier]
    CONF_OPTS.extend(PLUGIN_CONF_OPTS)
    opts = collections.defaultdict(list)
    for m in CONF_OPTS:
        configs = copy.deepcopy(m.list_opts())
        for key, val in configs.items():
            opts[key].extend(val)
    return _tupleize(opts)


def _tupleize(d):
    """Convert a dict of options to the 2-tuple format."""
    return [(key, value) for key, value in d.items()]
