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

from oslo_log import log
import yaml

from monasca_notification import conf
from monasca_notification import version

LOG = log.getLogger(__name__)
CONF = conf.CONF
_CONF_LOADED = False


def parse_args(argv, no_yaml=False):
    """Sets up configuration of monasca-notification."""

    global _CONF_LOADED
    if _CONF_LOADED:
        LOG.debug('Configuration has been already loaded')
        return

    conf.register_opts(CONF)
    log.register_options(CONF)

    default_log_levels = (log.get_default_log_levels())
    log.set_defaults(default_log_levels=default_log_levels)

    CONF(args=argv,
         project='monasca',
         prog='notification',
         version=version.version_string,
         description='''
         monasca-notification is an engine responsible for
         transforming alarm transitions into proper notifications
         ''')

    conf.register_enabled_plugin_opts(CONF)

    log.setup(CONF,
              product_name='monasca-notification',
              version=version.version_string)

    if not no_yaml:
        # note(trebskit) used only in test cases as the notification.yml
        # will be dropped eventually
        set_from_yaml()

    _CONF_LOADED = True


def set_from_yaml():
    if CONF.yaml_config:
        LOG.info('Detected usage of deprecated YAML configuration')
        yaml_cfg = yaml.safe_load(open(CONF.yaml_config, 'rb'))
        conf.load_from_yaml(yaml_cfg)
