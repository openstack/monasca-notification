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

keystone_group = cfg.OptGroup('keystone',
                              title='Keystone Options',
                              help='Options under this group allow to configure '
                                   'valid connection via Keystone'
                                   'authentication.')

keystone_opts = [
    cfg.BoolOpt(name='auth_required', default='False',
                help='This option enable or disable authentication using '
                     'keystone'),
    cfg.StrOpt(name='auth_url', default='http://127.0.0.1/identity/v3',
               help='URL of identity service'),
    cfg.StrOpt(name='username', default='admin',
               help='Username'),
    cfg.StrOpt(name='password', default='password',
               help='Password of identity service'),
    cfg.StrOpt(name='project_name', default='admin',
               help='Name of project'),
    cfg.StrOpt(name='user_domain_name', default='default',
               help='User domain name'),
    cfg.StrOpt(name='project_domain_name', default='default',
               help='Project domain name'),
    cfg.StrOpt(name='auth_type', default='password',
               help='Type of authentication')
]


def register_opts(conf):
    conf.register_group(keystone_group)
    conf.register_opts(keystone_opts, group=keystone_group)


def list_opts():
    return {
        keystone_group: keystone_opts
    }
