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
   notification.address = https://hipchat.hpcloud.net/v2/room/<room_id>/notification?auth_token=432432

   How to get access token?
       1) Login to Hipchat with the user account which is used for notification
       2) Go to this page. https://hipchat.hpcloud.net/account/api (Replace your hipchat server name)
       3) You can see option to "Create token". Use the capability "SendNotification"

   How to get the Room ID?
       1) Login to Hipchat with the user account which is used for notification
       2) Go to this page. https://hipchat.hpcloud.net/account/api (Replace your hipchat server name)
       3) Click on the Rooms tab
       4) Click on any Room of your choice.
       5) Room ID is the API ID field

"""


class HipChatNotifier(abstract_notifier.AbstractNotifier):
    def __init__(self, log):
        self._log = log

    def config(self, config_dict):
        self._config = {'timeout': 5}
        self._config.update(config_dict)

    @property
    def type(self):
        return "hipchat"

    @property
    def statsd_name(self):
        return 'sent_hipchat_count'

    def _build_hipchat_message(self, notification):
        """Builds hipchat message body
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

        hipchat_request = {}
        hipchat_request['color'] = 'green'
        hipchat_request['message_format'] = 'text'
        hipchat_request['message'] = json.dumps(body, indent=3)

        return hipchat_request

    def send_notification(self, notification):
        """Send the notification via hipchat
            Posts on the given url
        """

        hipchat_message = self._build_hipchat_message(notification)
        parsed_url = urlparse.urlsplit(notification.address)

        query_params = urlparse.parse_qs(parsed_url.query)
        # URL without query params
        url = urlparse.urljoin(notification.address, urlparse.urlparse(notification.address).path)

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
            result = requests.post(url=url,
                                   data=hipchat_message,
                                   verify=verify,
                                   params=query_params,
                                   proxies=proxyDict,
                                   timeout=self._config['timeout'])

            if result.status_code in range(200, 300):
                self._log.info("Notification successfully posted.")
                return True
            else:
                msg = "Received an HTTP code {} when trying to send to  hipchat on URL {} with response {} ."
                self._log.error(msg.format(result.status_code, url, result.text))
                return False
        except Exception:
            self._log.exception("Error trying to send to hipchat  on URL {}".format(url))
            return False
