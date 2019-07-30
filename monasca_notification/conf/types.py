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
from oslo_config import types
from oslo_log import log
from oslo_utils import importutils
from oslo_utils import netutils

LOG = log.getLogger(__name__)


class Plugin(types.String):
    def __init__(self, ignore_missing=False, choices=None, plugin_map=None):

        if not plugin_map:
            # since simport is used, we cannot tell where plugin is located
            # thus plugin map wouldn't contain it
            plugin_map = {}

        super(Plugin, self).__init__(choices, quotes=False, ignore_case=True,
                                     type_name='plugin value')
        self._plugin_map = plugin_map
        self._ingore_mission = ignore_missing

    def __call__(self, value):
        value = super(Plugin, self).__call__(value)
        value = self._get_actual_target(value)
        cls = None

        try:
            value = value.replace(':', '.')
            cls = importutils.import_class(value)
        except ImportError:
            if not self._ingore_mission:
                raise ValueError('%s cannot be imported' % value)
            else:
                LOG.exception('%s cannot be imported', value)

        return cls

    def _get_actual_target(self, value):

        # NOTE(trebskit) missing values will be handled
        # by choices from StringType

        if value in self._plugin_map.keys():
            return self._plugin_map[value]

        return value


class PluginOpt(cfg.Opt):
    def __init__(self, name, choices=None, plugin_map=None, **kwargs):
        plugin = Plugin(choices=choices, plugin_map=plugin_map)
        super(PluginOpt, self).__init__(name,
                                        type=plugin,
                                        **kwargs)


class HostAddressPortType(types.HostAddress):
    """HostAddress with additional port"""

    def __init__(self, version=None):
        type_name = 'host address port value'
        super(HostAddressPortType, self).__init__(version,
                                                  type_name=type_name)

    def __call__(self, value):
        addr, port = netutils.parse_host_port(value)

        addr = self._validate_addr(addr)
        port = self._validate_port(port)
        LOG.debug('addr: %s port: %s' % (addr, port))

        if addr and port:
            return '%s:%d' % (addr, port)
        raise ValueError('%s is not valid host address with optional port')

    @staticmethod
    def _validate_port(port=80):
        port = types.Port()(port)
        return port

    def _validate_addr(self, addr):
        try:
            addr = self.ip_address(addr)
        except ValueError:
            try:
                addr = self.hostname(addr)
            except ValueError:
                raise ValueError("%s is not a valid host address", addr)
        return addr
