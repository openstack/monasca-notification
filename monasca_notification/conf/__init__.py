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

from monasca_notification.conf import cli
from monasca_notification.conf import database
from monasca_notification.conf import kafka
from monasca_notification.conf import keystone
from monasca_notification.conf import notifiers
from monasca_notification.conf import processors
from monasca_notification.conf import queues
from monasca_notification.conf import retry
from monasca_notification.conf import statsd
from monasca_notification.conf import zookeeper

LOG = log.getLogger(__name__)
CONF = cfg.CONF

CONF_OPTS = [
    cli,
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
    opts = collections.defaultdict(list)
    for m in CONF_OPTS:
        configs = copy.deepcopy(m.list_opts())
        for key, val in configs.items():
            opts[key].extend(val)
    return _tupleize(opts)


def load_from_yaml(yaml_config, conf=None):
    # build named BACKWARD_MAP to modules set_defaults

    if conf is None:
        conf = CONF

    def _noop(*arg, **kwargs):
        pass

    def _plain_override(g=None, **opts):
        for k, v in opts.items():
            conf.set_override(group=g, name=k, override=v)

    def _load_plugin_settings(**notifiers_cfg):
        notifiers_cfg = {t.lower(): v for t, v in notifiers_cfg.items()}
        enabled_plugins = notifiers_cfg.pop('plugins', [])

        # We still can have these 3 (email, pagerduty, webhook)
        #  that are considered as builtin, hence should be always enabled
        conf_to_plugin = {
            'email': 'monasca_notification.plugins.'
                     'email_notifier:EmailNotifier',
            'pagerduty': 'monasca_notification.plugins.'
                         'pagerduty_notifier:PagerdutyNotifier',
            'webhook': 'monasca_notification.plugins.'
                       'webhook_notifier:WebhookNotifier'
        }
        for ctp_key, ctp_clazz in conf_to_plugin.items():
            if ctp_key in notifiers_cfg and ctp_key not in enabled_plugins:
                LOG.debug('%s enabled as builtin plugin', ctp_key)
                enabled_plugins.append(ctp_clazz)

        _plain_override(g='notification_types', enabled=enabled_plugins)
        if not enabled_plugins:
            return

        for ep in enabled_plugins:
            ep_module = importutils.import_module(ep.split(':')[0])
            ep_clazz = importutils.import_class(ep.replace(':', '.'))

            if not hasattr(ep_module, 'register_opts'):
                LOG.debug('%s does not have \'register_opts\' method')
                continue
            if not hasattr(ep_clazz, 'type'):
                LOG.debug('%s does not have \'type\' class variable')
                continue

            ep_r_opt = getattr(ep_module, 'register_opts')
            ep_type = getattr(ep_clazz, 'type')

            ep_r_opt(conf)  # register options
            _plain_override(g='%s_notifier' % ep_type,
                            **notifiers_cfg.get(ep_type))

            LOG.debug('Registered options and values of the %s notifier',
                      ep_type)

    def _configure_and_warn_the_logging(logging_config):
        LOG.warning('Configuration of the logging system from '
                    '\'notification.yml\' has been deprecated and '
                    'Please check how to configure logging with '
                    'oslo.log library.')
        import logging.config
        logging.config.dictConfig(logging_config)

    mappper = {
        'statsd': [lambda d: _plain_override(g='statsd', **d)],
        'retry': [lambda d: _plain_override(g='retry_engine', **d)],
        'database': [
            lambda d: _plain_override(g='database', repo_driver=d['repo_driver']),
            lambda d: _plain_override(g='orm', url=d['orm']['url'])
        ],
        'postgresql': [lambda d: _plain_override(g='postgresql', **d)],
        'mysql': [lambda d: _plain_override(g='mysql', **d)],
        'processors': [
            lambda d: _plain_override(g='alarm_processor',
                                      number=d['alarm']['number'],
                                      ttl=d['alarm']['ttl']),
            lambda d: _plain_override(g='notification_processor',
                                      number=d['notification']['number'])
        ],
        'queues': [lambda d: _plain_override(g='queues', **d)],
        'kafka': [lambda d: _plain_override(g='kafka', **d)],
        'keystone': [lambda d: _plain_override(g='keystone', **d)],
        'zookeeper': [lambda d: _plain_override(g='zookeeper', **d)],
        'notification_types': [lambda d: _load_plugin_settings(**d)],
        'logging': [_configure_and_warn_the_logging]
    }

    for key, opts in yaml_config.items():
        LOG.debug('Loading group %s from deprecated yaml configuration', key)
        handlers = mappper.get(key, [_noop])
        if len(handlers) == 1 and handlers[0] == _noop:
            LOG.warning('Unmapped configuration group %s from YAML file', key)
        [handler(opts) for handler in handlers]


def _tupleize(d):
    """Convert a dict of options to the 2-tuple format."""
    return [(key, value) for key, value in d.items()]
