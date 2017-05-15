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

queues_group = cfg.OptGroup('queues',
                            title='Queues Options',
                            help=('Options under this group allow to '
                                  'configure valid connection sizes of '
                                  'all queues.'))

queues_opts = [
    cfg.IntOpt(name='alarms_size', min=1, default=256,
               help='Size of the alarms queue.'),
    cfg.IntOpt(name='finished_size', min=1, default=256,
               help='Size of the finished alarms queue.'),
    cfg.IntOpt(name='notifications_size', min=1, default=256,
               help='Size of notifications queue.'),
    cfg.IntOpt(name='sent_notifications_size', min=1, default=50,
               help='Size of sent notifications queue. '
                    'Limiting this size reduces potential or '
                    're-sent notifications after a failure.')
]


def register_opts(conf):
    conf.register_group(queues_group)
    conf.register_opts(queues_opts, group=queues_group)


def list_opts():
    return {
        queues_group: queues_opts
    }
