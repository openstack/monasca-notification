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

ap_group = cfg.OptGroup('alarm_processor',
                        title='Alarm processor group',
                        help='Options to configure alarm processor.')

ap_opts = [
    cfg.IntOpt(name='number', min=1, default=2,
               help='Number of alarm processors to spawn',
               deprecated_for_removal=True,
               deprecated_since='1.8.0',
               deprecated_reason='Options is not used in the current code '
                                 'and will be removed in future releases.'),
    cfg.IntOpt(name='ttl', default=14400,
               advanced=True,
               help='Alarms older than TTL are not processed '
                    'by notification engine.')
]

np_group = cfg.OptGroup('notification_processor',
                        title='Notification processor group',
                        help='Options to configure notification processor.')
np_opts = [
    cfg.IntOpt(name='number', min=1,
               default=4, help='Number of notification processors to spawn.')
]


def register_opts(conf):
    conf.register_group(ap_group)
    conf.register_group(np_group)

    conf.register_opts(ap_opts, group=ap_group)
    conf.register_opts(np_opts, group=np_group)


def list_opts():
    return {
        ap_group: ap_opts,
        np_group: np_opts
    }
