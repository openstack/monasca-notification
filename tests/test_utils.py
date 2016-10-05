# Copyright 2016 FUJITSU LIMITED
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

from mock import patch
import unittest

from monasca_notification.common import utils


class TestStatsdConnection(unittest.TestCase):
    extra_dimensions = {'foo': 'bar'}
    base_name = 'monasca'

    def test_statsd_default_connection(self):
        config = {}
        with patch(
                'monasca_notification.common.utils.monascastatsd.Client') as c:
            utils.get_statsd_client(config)
            c.assert_called_once_with(dimensions=utils.NOTIFICATION_DIMENSIONS,
                                      name=self.base_name)

    def test_statsd_config_connection(self):
        port_number = 9999
        hostname = 'www.example.org'
        config = {'statsd': {'host': hostname, 'port': port_number}}
        with patch(
                'monasca_notification.common.utils.monascastatsd.Client') as c:
            utils.get_statsd_client(config)
            c.assert_called_once_with(dimensions=utils.NOTIFICATION_DIMENSIONS,
                                      name=self.base_name,
                                      port=port_number,
                                      host=hostname)

    def test_statsd_update_dimmensions(self):
        config = {}
        expected_dimensions = utils.NOTIFICATION_DIMENSIONS.copy()
        expected_dimensions.update(self.extra_dimensions)
        with patch(
                'monasca_notification.common.utils.monascastatsd.Client') as c:
            utils.get_statsd_client(config, dimensions=self.extra_dimensions)
            c.assert_called_once_with(dimensions=expected_dimensions,
                                      name=self.base_name)
