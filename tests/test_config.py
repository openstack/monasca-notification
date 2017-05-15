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

import mock
from oslo_config import cfg
from oslo_utils import importutils
import yaml

from monasca_notification import conf
from monasca_notification import config
from tests import base


class TestConfig(base.BaseTestCase):
    @mock.patch('monasca_notification.config.conf')
    def test_should_load_deprecated_yaml(self, conf):
        fake_config = """
        sayians:
            - goku
            - vegeta
        """
        yaml_config = self.create_tempfiles(
            files=[('notification', fake_config)],
            ext='.yml'
        )[0]

        self.conf_override(yaml_config=yaml_config)

        config.set_from_yaml()

        fake_yaml_config = {
            'sayians': ['goku', 'vegeta']
        }
        conf.load_from_yaml.assert_called_once_with(fake_yaml_config)

    @mock.patch('monasca_notification.config.conf')
    def test_should_not_load_deprecated_yaml(self, conf):
        config.set_from_yaml()
        conf.load_from_yaml.assert_not_called()


class TestYamlOverriding(base.BaseTestCase):
    # TOP_LEVEL keys represents old groups in YAML file
    VERIFIERS = {
        'statsd': {
            'groups': [
                ('statsd', {
                    'host': 'localhost',
                    'port': 8125
                })
            ]
        },
        'retry': {
            'groups': [
                ('retry_engine', {
                    'interval': 300,
                    'max_attempts': 500
                })
            ]
        },
        'queues': {
            'groups': [
                ('queues', {
                    'alarms_size': 1024,
                    'finished_size': 1024,
                    'notifications_size': 1024,
                    'sent_notifications_size': 1024
                })
            ]
        },
        'zookeeper': {
            'groups': [
                ('zookeeper', {
                    'url': ['127.0.0.1:2181'],
                    'notification_path': '/foo/bar',
                    'periodic_path': {
                        666: '/bu/666_bubu'
                    },
                })
            ]
        },
        'kafka': {
            'groups': [
                ('kafka', {
                    'url': ['127.0.0.1:9092'],
                    'group': 'a',
                    'alarm_topic': 'b',
                    'notification_topic': 'c',
                    'notification_retry_topic': 'd',
                    'periodic': {
                        60: 'e'
                    },
                    'max_offset_lag': 666
                })
            ]
        },
        'processors': {
            'groups': [
                ('alarm_processor', {'number': 666, 'ttl': 666}),
                ('notification_processor', {'number': 666})
            ]
        },
        'postgresql': {
            'groups': [
                ('postgresql', {
                    'host': '100.10.100.10',
                    'port': 9999,
                    'user': 'goku',
                    'password': 'kame-ha-me-ha',
                    'database': 'planet_vegeta'
                })
            ]
        },
        'mysql': {
            'groups': [
                ('mysql', {
                    'host': '100.99.100.99',
                    'port': 3306,
                    'user': 'goku',
                    'passwd': 'kame-ha-me-ha',
                    'db': 'planet_vegeta',
                    'ssl': {}
                })
            ]
        },
        'database': {
            'groups': [
                ('database', {'repo_driver': importutils.import_class(
                    'monasca_notification.common.repositories.mysql.'
                    'mysql_repo.MysqlRepo')}),
                ('orm', {'url': 'postgres://a:b@127.0.0.1:9999/goo'})
            ]
        },
        'notification_types': {
            'groups': [
                ('notification_types', {
                    'enabled': [
                        'monasca_notification.plugins.hipchat_notifier:HipChatNotifier',
                        'monasca_notification.plugins.slack_notifier:SlackNotifier',
                        'monasca_notification.plugins.jira_notifier:JiraNotifier',
                        'monasca_notification.plugins.email_notifier:EmailNotifier',
                        'monasca_notification.plugins.pagerduty_notifier:PagerdutyNotifier',
                        'monasca_notification.plugins.webhook_notifier:WebhookNotifier',
                    ]
                }),
                ('email_notifier', {
                    'server': '127.0.0.1',
                    'port': 25,
                    'user': None,
                    'password': None,
                    'timeout': 60,
                    'from_addr': 'root@localhost',
                    'grafana_url': 'http://127.0.0.1:3000'
                }),
                ('webhook_notifier', {'timeout': 123}),
                ('pagerduty_notifier', {
                    'timeout': 231,
                    'url': 'https://a.b.c/d/e/f.json'
                }),
                ('hipchat_notifier', {
                    'timeout': 512,
                    'ca_certs': "/a.crt",
                    'insecure': True,
                    'proxy': 'https://myproxy.corp.invalid:9999'
                }),
                ('slack_notifier', {
                    'timeout': 512,
                    'ca_certs': "/a.crt",
                    'insecure': True,
                    'proxy': 'https://myproxy.corp.invalid:9999'
                }),
                ('jira_notifier', {
                    'user': 'username',
                    'password': 'password',
                    'timeout': 666,
                    'custom_formatter': '/some_yml.yml',
                    'proxy': 'www.example.org'
                })
            ]
        }
    }

    def setUp(self):
        super(TestYamlOverriding, self).setUp()
        self.yaml_config = yaml.safe_load(
            open('tests/resources/notification.yaml', 'rb')
        )

    def test_overriding(self):

        conf.load_from_yaml(yaml_config=self.yaml_config, conf=config.CONF)
        opts = config.CONF

        for group in self.VERIFIERS.keys():
            verifier_details = self.VERIFIERS[group]
            groups = verifier_details['groups']

            for opt_group, opt_values in groups:

                for key, value in opt_values.items():
                    try:
                        opt_value = opts[opt_group][key]
                    except (cfg.NoSuchOptError, cfg.NoSuchGroupError) as ex:
                        self.fail(str(ex))
                    else:
                        msg = ('%s not overridden in group %s'
                               % (key, opt_group))

                        if (isinstance(value, list) and
                                isinstance(opt_value, list)):
                            for v in value:
                                self.assertIn(v, opt_value, msg)
                            continue

                        self.assertEqual(value, opt_value, msg)
