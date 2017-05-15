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

cli_opts = [
    cfg.StrOpt(name='yaml_config', default=None,
               positional=True,
               help='Backward compatible option that allows to pass path '
                    'to YAML file containing configuration '
                    'of monasca-notitifcation.',
               deprecated_for_removal=True,
               deprecated_since='1.9.0',
               deprecated_reason='monasca-notification has moved to '
                                 'oslo.conf henceusing YAML based '
                                 'configuration will be removed '
                                 'after PIKE release.')
]


def register_opts(conf):
    for opt in cli_opts:
        conf.register_cli_opt(opt=opt)


def list_opts():
    return {
        'default': cli_opts
    }
