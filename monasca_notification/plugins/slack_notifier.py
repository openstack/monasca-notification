# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
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

import json
import requests
import urlparse

from monasca_notification.plugins import abstract_notifier

"""
   notification.address = https://slack.com/api/chat.postMessage?token=token&channel=#channel"

   Slack documentation about tokens:
        1. Login to your slack account via browser and check the following pages
             a. https://api.slack.com/docs/oauth-test-tokens
             b. https://api.slack.com/tokens

"""


class SlackNotifier(abstract_notifier.AbstractNotifier):
    def __init__(self, log):
        self._log = log

    def config(self, config_dict):
        self._config = {'timeout': 5}
        self._config.update(config_dict)

    @property
    def type(self):
        return "slack"

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

    def send_notification(self, notification):
        """Send the notification via slack
            Posts on the given url
        """

        slack_message = self._build_slack_message(notification)

        address = notification.address
        #  "#" is reserved character and replace it with ascii equivalent
        #  Slack room has "#" as first character
        address = address.replace("#", "%23")

        parsed_url = urlparse.urlsplit(address)
        query_params = urlparse.parse_qs(parsed_url.query)
        # URL without query params
        url = urlparse.urljoin(address, urlparse.urlparse(address).path)

        # Default option is to do cert verification
        verify = self._config.get('insecure', False)
        # If ca_certs is specified, do cert validation and ignore insecure flag
        if (self._config.get("ca_certs")):
            verify = self._config.get("ca_certs")

        proxyDict = None
        if (self._config.get("proxy")):
            proxyDict = {"https": self._config.get("proxy")}

        try:
            # Posting on the given URL
            self._log.debug("Sending to the url {0} , with query_params {1}".format(url, query_params))
            result = requests.post(url=url,
                                   json=slack_message,
                                   verify=verify,
                                   params=query_params,
                                   proxies=proxyDict,
                                   timeout=self._config['timeout'])

            if result.status_code not in range(200, 300):
                self._log.error("Received an HTTP code {} when trying to post on URL {}."
                                .format(result.status_code, url))
                return False

            # Slack returns 200 ok even if the token is invalid. Response has valid error message
            response = json.loads(result.text)
            if response.get('ok'):
                self._log.info("Notification successfully posted.")
                return True
            else:
                self._log.error("Received an error message {} when trying to send to slack on URL {}."
                                .format(response.get("error"), url))
                return False
        except Exception:
            self._log.exception("Error trying to send to slack  on URL {}".format(url))
            return False
