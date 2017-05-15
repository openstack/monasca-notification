# (C) Copyright 2016-2017 Hewlett Packard Enterprise Development LP
# Copyright 2017 Fujitsu LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests
from six.moves import urllib
import ujson as json

from debtcollector import removals
from oslo_config import cfg

from monasca_notification.plugins import abstract_notifier

CONF = cfg.CONF


def register_opts(conf):
    gr = cfg.OptGroup(name='%s_notifier' % SlackNotifier.type)
    opts = [
        cfg.IntOpt(name='timeout', default=5, min=1),
        cfg.BoolOpt(name='insecure', default=True),
        cfg.StrOpt(name='ca_certs', default=None),
        cfg.StrOpt(name='proxy', default=None)
    ]

    conf.register_group(gr)
    conf.register_opts(opts, group=gr)


class SlackNotifier(abstract_notifier.AbstractNotifier):
    """This module is a notification plugin to integrate with Slack.

    This plugin supports 2 types of APIs below.

    1st: Slack API
        notification.address = https://slack.com/api/chat.postMessage?token={token}&channel=#foobar

        You need to specify your token and channel name in the address.
        Regarding {token}, login to your slack account via browser and check the following page.
            https://api.slack.com/docs/oauth-test-tokens

    2nd: Incoming webhook
        notification.address = https://hooks.slack.com/services/foo/bar/buz

        You need to get the Incoming webhook URL.
        Login to your slack account via browser and check the following page.
            https://my.slack.com/services/new/incoming-webhook/
        Slack document about incoming webhook:
            https://api.slack.com/incoming-webhooks
    """

    type = 'slack'

    MAX_CACHE_SIZE = 100
    RESPONSE_OK = 'ok'

    _raw_data_url_caches = []

    def __init__(self, log):
        super(SlackNotifier, self).__init__()
        self._log = log

    @removals.remove(
        message='Configuration of notifier is available through oslo.cfg',
        version='1.9.0',
        removal_version='3.0.0'
    )
    def config(self, config_dict):
        pass

    @property
    def statsd_name(self):
        return 'sent_slack_count'

    def _build_slack_message(self, notification):
        """Builds slack message body
        """
        body = {'alarm_id': notification.alarm_id,
                'alarm_definition_id': notification.raw_alarm['alarmDefinitionId'],
                'alarm_name': notification.alarm_name,
                'alarm_description': notification.raw_alarm['alarmDescription'],
                'alarm_timestamp': notification.alarm_timestamp,
                'state': notification.state,
                'old_state': notification.raw_alarm['oldState'],
                'message': notification.message,
                'tenant_id': notification.tenant_id,
                'metrics': notification.metrics}

        slack_request = {}
        slack_request['text'] = json.dumps(body, indent=3)

        return slack_request

    def _check_response(self, result):
        if 'application/json' in result.headers.get('Content-Type'):
            response = result.json()
            if response.get(self.RESPONSE_OK):
                return True
            else:
                self._log.error('Received an error message when trying to send to slack. error={}'
                                .format(response.get('error')))
                return False
        elif self.RESPONSE_OK == result.text:
            return True
        else:
            self._log.error('Received an error message when trying to send to slack. error={}'
                            .format(result.text))
            return False

    def _send_message(self, request_options):
        try:
            url = request_options.get('url')
            result = requests.post(**request_options)
            if result.status_code not in range(200, 300):
                self._log.error('Received an HTTP code {} when trying to post on URL {}.'
                                .format(result.status_code, url))
                return False

            # Slack returns 200 ok even if the token is invalid. Response has valid error message
            if self._check_response(result):
                self._log.info('Notification successfully posted.')
                return True

            self._log.error('Failed to send to slack on URL {}.'.format(url))
            return False
        except Exception as err:
            self._log.exception('Error trying to send to slack on URL {}. Detail: {}'
                                .format(url, err))
            return False

    def send_notification(self, notification):
        """Send the notification via slack
            Posts on the given url
        """

        slack_message = self._build_slack_message(notification)

        address = notification.address
        #  '#' is reserved character and replace it with ascii equivalent
        #  Slack room has '#' as first character
        address = address.replace('#', '%23')

        parsed_url = urllib.parse.urlsplit(address)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        # URL without query params
        url = urllib.parse.urljoin(address, urllib.parse.urlparse(address).path)

        # Default option is to do cert verification
        # If ca_certs is specified, do cert validation and ignore insecure flag
        verify = CONF.slack_notifier.ca_certs or not CONF.slack_notifier.insecure

        proxy = CONF.slack_notifier.proxy
        proxy_dict = None
        if proxy is not None:
            proxy_dict = {'https': proxy}

        data_format_list = ['json', 'data']
        if url in SlackNotifier._raw_data_url_caches:
            data_format_list = ['data']

        for data_format in data_format_list:
            self._log.info('Trying to send message to {} as {}'
                           .format(url, data_format))
            request_options = {
                'url': url,
                'verify': verify,
                'params': query_params,
                'proxies': proxy_dict,
                'timeout': CONF.slack_notifier.timeout,
                data_format: slack_message
            }
            if self._send_message(request_options):
                if (data_format == 'data' and
                        url not in SlackNotifier._raw_data_url_caches and
                        len(SlackNotifier._raw_data_url_caches) < self.MAX_CACHE_SIZE):
                    # NOTE:
                    #    There are a few URLs which can accept only raw data, so
                    #    only the URLs with raw data are kept in the cache. When
                    #    too many URLs exists, it can be considered malicious
                    #    user registers them.
                    #    In this case, older ones should be safer than newer
                    #    ones. When exceeding the cache size, do not replace the
                    #    the old cache with the newer one.
                    SlackNotifier._raw_data_url_caches.append(url)
                return True

            self._log.info('Failed to send message to {} as {}'
                           .format(url, data_format))
        return False
