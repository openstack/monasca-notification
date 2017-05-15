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

retry_engine_group = cfg.OptGroup('retry_engine',
                                  title='Retry Engine Options',
                                  help='Options under this group allow to '
                                       'configure valid connection '
                                       'for retry engine.')

retry_opts = [
    cfg.IntOpt(name='interval', min=30, default=30,
               advanced=True,
               help='How often should retry happen.'),
    cfg.IntOpt(name='max_attempts', default=5,
               advanced=True,
               help='How many times should retrying be tried.')
]


def register_opts(conf):
    conf.register_group(retry_engine_group)
    conf.register_opts(retry_opts, group=retry_engine_group)


def list_opts():
    return {
        retry_engine_group: retry_opts
    }
