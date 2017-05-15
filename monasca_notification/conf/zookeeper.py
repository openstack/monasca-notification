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

from oslo_config import cfg

from monasca_notification.conf import types

_DEFAULT_URL = '127.0.0.1:2181'
_DEFAULT_NOTIFICATION_PATH = '/notification/alarms'
_DEFAULT_RETRY_PATH = '/notification/retry'
_DEFAULT_PERIODIC_PATH = {
    60: '/notification/60_seconds'
}

zookeeper_group = cfg.OptGroup('zookeeper',
                               title='Zookeeper Options',
                               help='Options under this group allow to '
                                    'configure settings for zookeeper '
                                    'handling.')

zookeeper_opts = [
    cfg.ListOpt(name='url', item_type=types.HostAddressPortType(),
                default=_DEFAULT_URL, required=True,
                help='List of addresses (with ports) pointing '
                     'at zookeeper cluster.'),
    cfg.StrOpt(name='notification_path', default=_DEFAULT_NOTIFICATION_PATH,
               required=True, advanced=True,
               help='Path in zookeeper tree to track notification offsets.'),
    cfg.StrOpt(name='notification_retry_path', default=_DEFAULT_RETRY_PATH,
               required=True, advanced=True,
               help='Path in zookeeper tree to track notification '
                    'retries offsets.'),
    cfg.DictOpt(name='periodic_path', default=_DEFAULT_PERIODIC_PATH,
                required=True, advanced=True,
                help='Paths in zookeeper tree to track periodic offsets. '
                     'Keys must be integers describing the interval '
                     'of periodic notification. Values are actual '
                     'paths inside zookeeper tree.')
]


def register_opts(conf):
    conf.register_group(zookeeper_group)
    conf.register_opts(zookeeper_opts, group=zookeeper_group)


def list_opts():
    return {
        zookeeper_group: zookeeper_opts
    }
