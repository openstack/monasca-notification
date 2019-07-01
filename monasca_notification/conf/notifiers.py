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

_KEY_MAP = {
    'email': 'monasca_notification.plugins.email_notifier:EmailNotifier',
    'pagerduty': 'monasca_notification.plugins.'
                 'pagerduty_notifier:PagerdutyNotifier',
    'webhook': 'monasca_notification.plugins.webhook_notifier:WebhookNotifier',
    'hipchat': 'monasca_notification.plugins.hipchat_notifier:HipChatNotifier',
    'slack': 'monasca_notification.plugins.slack_notifier:SlackNotifier',
    'jira': 'monasca_notification.plugins.jira_notifier:JiraNotifier'
}

notifier_group = cfg.OptGroup('notification_types',
                              title='Notification types',
                              help='Group allows to configure available '
                                   'notifiers inside notification engine.')

notifier_opts = [
    cfg.ListOpt(name='enabled', default=['email', 'pagerduty', 'webhook'],
                item_type=lambda x: _KEY_MAP.get(x, x), bounds=False,
                advanced=True, sample_default=','.join(_KEY_MAP.keys()),
                help='List of enabled notification types. You may specify '
                     'full class name {} '
                     'or shorter label {}.'.format(_KEY_MAP.get('hipchat'),
                                                   'hipchat')
                )
]


def register_opts(conf):
    conf.register_group(notifier_group)
    conf.register_opts(notifier_opts, group=notifier_group)


def list_opts():
    return {
        notifier_group: notifier_opts,
    }
