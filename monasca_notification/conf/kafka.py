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

_DEFAULT_URL = '127.0.0.1:9092'
_DEFAULT_GROUP = 'monasca-notification'
_DEFAULT_ALARM_TOPIC = 'alarm-state-transitions'
_DEFAULT_NOTIFICATION_TOPIC = 'alarm-notifications'
_DEFAULT_RETRY_TOPIC = 'retry-notifications'
_DEFAULT_PERIODIC_TOPICS = {
    60: '60-seconds-notifications'
}
_DEFAULT_MAX_OFFSET_LAG = 600

kafka_group = cfg.OptGroup('kafka',
                           title='Kafka Options',
                           help='Options under this group allow to configure '
                                'valid connection or Kafka queue.')

kafka_opts = [
    cfg.ListOpt(name='url', item_type=types.HostAddressPortType(),
                bounds=False,
                default=_DEFAULT_URL, required=True,
                help='List of addresses (with ports) pointing '
                     'at zookeeper cluster.'),
    cfg.StrOpt(name='group', default=_DEFAULT_GROUP,
               required=True, advanced=True,
               help='Consumer\'s group for monasca-notification client.'),
    cfg.StrOpt(name='alarm_topic', default=_DEFAULT_ALARM_TOPIC,
               required=True, advanced=True,
               help='Topic name in kafka where alarm '
                    'transitions are stored.'),
    cfg.StrOpt(name='notification_topic', default=_DEFAULT_NOTIFICATION_TOPIC,
               required=True, advanced=True,
               help='Topic name in kafka where alarm '
                    'notifications are stored.'),
    cfg.StrOpt(name='notification_retry_topic', default=_DEFAULT_RETRY_TOPIC,
               required=True, advanced=True,
               help='Topic name in kafka where notifications, that have '
                    'failed to be sent and are waiting for retry operations, '
                    'are stored.'),
    cfg.DictOpt(name='periodic', default=_DEFAULT_PERIODIC_TOPICS,
                required=True, advanced=True,
                help='Dict of periodic topics. Keys are the period and '
                     'values the actual topic names in kafka where '
                     'notifications are stored.'),
    cfg.IntOpt(name='max_offset_lag', default=_DEFAULT_MAX_OFFSET_LAG,
               required=True, advanced=True,
               help='Maximum lag for topic that is acceptable by '
                    'the monasca-notification. Notifications that are older '
                    'than this offset are skipped.')
]


def register_opts(conf):
    conf.register_group(kafka_group)
    conf.register_opts(kafka_opts, group=kafka_group)


def list_opts():
    return {
        kafka_group: kafka_opts
    }
