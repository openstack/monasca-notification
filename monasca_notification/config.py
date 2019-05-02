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
from oslo_log import log
import sys

from monasca_notification import conf
from monasca_notification import version

LOG = log.getLogger(__name__)
CONF = conf.CONF
_CONF_LOADED = False


def parse_args(argv):
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
         prog=sys.argv[1:],
         version=version.version_string,
         default_config_files=_get_config_files(),
         description='''
         monasca-notification is an engine responsible for
         transforming alarm transitions into proper notifications
         ''')

    conf.register_enabled_plugin_opts(CONF)

    log.setup(CONF,
              product_name='monasca-notification',
              version=version.version_string)

    _CONF_LOADED = True


def _get_config_files():
    """Get the possible configuration files accepted by oslo.config

    This also includes the deprecated ones
    """
    # default files
    conf_files = cfg.find_config_files(project='monasca',
                                       prog='monasca-notification')
    # deprecated config files (only used if standard config files are not there)
    if len(conf_files) == 0:
        old_conf_files = cfg.find_config_files(project='monasca',
                                               prog='notification')
        if len(old_conf_files) > 0:
            LOG.warning('Found deprecated old location "{}" '
                        'of main configuration file'.format(old_conf_files))
            conf_files += old_conf_files
    return conf_files
