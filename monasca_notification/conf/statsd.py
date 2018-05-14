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

_DEFAULT_HOST = '127.0.0.1'
_DEFAULT_PORT = 8125

statsd_group = cfg.OptGroup('statsd',
                            title='statsd Options',
                            help='Options under this group allow '
                            'to configure valid connection '
                            'to statsd server launched by monasca-agent.')

statsd_opts = [
    cfg.BoolOpt('enable', default=True,
                help='Enable or disable self monitoring.'),
    cfg.HostAddressOpt('host', default=_DEFAULT_HOST,
                       help='IP address of statsd server.'),
    cfg.PortOpt('port', default=_DEFAULT_PORT, help='Port of statsd server.'),
]


def register_opts(conf):
    conf.register_group(statsd_group)
    conf.register_opts(statsd_opts, group=statsd_group)


def list_opts():
    return {
        statsd_group: statsd_opts
    }
