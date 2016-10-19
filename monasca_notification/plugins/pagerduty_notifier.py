# (C) Copyright 2015,2016 Hewlett Packard Enterprise Development LP
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

from monasca_notification.plugins import abstract_notifier


VALID_HTTP_CODES = [200, 201, 204]


class PagerdutyNotifier(abstract_notifier.AbstractNotifier):
    def __init__(self, log):
        self._log = log

    def config(self, config):
        self._config = {
            'timeout': 5,
            'url': 'https://events.pagerduty.com/generic/2010-04-15/create_event.json'}
        self._config.update(config)

    @property
    def type(self):
        return "pagerduty"

    @property
    def statsd_name(self):
        return 'sent_pagerduty_count'

    def send_notification(self, notification):
        """Send pagerduty notification
        """

        url = self._config['url']
        headers = {"content-type": "application/json"}
        body = {"service_key": notification.address,
                "event_type": "trigger",
                "description": notification.message,
                "client": "Monasca",
                "client_url": "",
                "details": {"alarm_id": notification.alarm_id,
                            "alarm_name": notification.alarm_name,
                            "current": notification.state,
                            "message": notification.message}}

        try:
            result = requests.post(url=url,
                                   data=json.dumps(body),
                                   headers=headers,
                                   timeout=self._config['timeout'])

            if result.status_code in VALID_HTTP_CODES:
                return True

            self._log.error("Error with pagerduty request. key=<{}> response={}"
                            .format(notification.address, result.status_code))
            return False
        except Exception:
            self._log.exception("Exception on pagerduty request. key=<{}>"
                                .format(notification.address))
            return False
