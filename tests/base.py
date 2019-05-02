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

from unittest import mock

import fixtures

from oslo_config import cfg
from oslo_config import fixture as oo_cfg
from oslotest import base as oslotest_base

from monasca_notification import conf
from monasca_notification import config


class DisableStatsdFixture(fixtures.Fixture):

    def setUp(self):
        super(DisableStatsdFixture, self).setUp()
        statsd_patch = mock.patch('monascastatsd.Connection')
        statsd_patch.start()
        self.addCleanup(statsd_patch.stop)


class ConfigFixture(oo_cfg.Config):
    """Mocks configuration"""

    def __init__(self):
        super(ConfigFixture, self).__init__(config.CONF)

    def setUp(self):
        super(ConfigFixture, self).setUp()

        self.addCleanup(self._clean_config_loaded_flag)

        conf.register_opts()
        config.parse_args(argv=[])

    @staticmethod
    def _clean_config_loaded_flag():
        config._CONF_LOADED = False


class BaseTestCase(oslotest_base.BaseTestCase):

    def setUp(self):
        super(BaseTestCase, self).setUp()
        self.useFixture(ConfigFixture())
        self.useFixture(DisableStatsdFixture())

    @staticmethod
    def conf_override(**kw):
        """Override flag variables for a test."""
        group = kw.pop('group', None)
        for k, v in kw.items():
            cfg.CONF.set_override(k, v, group)

    @staticmethod
    def conf_default(**kw):
        """Override flag variables for a test."""
        group = kw.pop('group', None)
        for k, v in kw.items():
            cfg.CONF.set_default(k, v, group)


class PluginTestCase(BaseTestCase):
    register_opts = None

    def setUp(self, register_opts=None):
        super(PluginTestCase, self).setUp()
        if register_opts:
            register_opts(conf.CONF)
