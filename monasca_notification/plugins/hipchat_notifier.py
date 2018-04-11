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
import ujson as json

from debtcollector import removals
from oslo_config import cfg
from six.moves import urllib

from monasca_notification.plugins import abstract_notifier

CONF = cfg.CONF

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

SEVERITY_COLORS = {"low": 'green',
                   'medium': 'gray',
                   'high': 'yellow',
                   'critical': 'red'}


def register_opts(conf):
    gr = cfg.OptGroup(name='%s_notifier' % HipChatNotifier.type)
    opts = [
        cfg.IntOpt(name='timeout', default=5, min=1),
        cfg.BoolOpt(name='insecure', default=True),
        cfg.StrOpt(name='ca_certs', default=None),
        cfg.StrOpt(name='proxy', default=None)
    ]

    conf.register_group(gr)
    conf.register_opts(opts, group=gr)


class HipChatNotifier(abstract_notifier.AbstractNotifier):

    type = 'hipchat'

    def __init__(self, log):
        super(HipChatNotifier, self).__init__()
        self._log = log

    @removals.remove(
        message='Configuration of notifier is available through oslo.cfg',
        version='1.9.0',
        removal_version='3.0.0'
    )
    def config(self, config_dict=None):
        pass

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
        hipchat_request['color'] = self._get_color(notification.severity.lower())
        hipchat_request['message_format'] = 'text'
        hipchat_request['message'] = json.dumps(body, indent=3)

        return hipchat_request

    def _get_color(self, severity):
        return SEVERITY_COLORS.get(severity, 'purple')

    def send_notification(self, notification):
        """Send the notification via hipchat
            Posts on the given url
        """

        hipchat_message = self._build_hipchat_message(notification)
        parsed_url = urllib.parse.urlsplit(notification.address)

        query_params = urllib.parse.parse_qs(parsed_url.query)
        # URL without query params
        url = urllib.parse.urljoin(
            notification.address,
            urllib.parse.urlparse(
                notification.address).path)

        # Default option is to do cert verification
        verify = not CONF.hipchat_notifier.insecure
        ca_certs = CONF.hipchat_notifier.ca_certs
        proxy = CONF.hipchat_notifier.proxy

        # If ca_certs is specified, do cert validation and ignore insecure flag
        if ca_certs is not None:
            verify = ca_certs

        proxyDict = None
        if proxy is not None:
            proxyDict = {'https': proxy}

        try:
            # Posting on the given URL
            result = requests.post(url=url,
                                   data=hipchat_message,
                                   verify=verify,
                                   params=query_params,
                                   proxies=proxyDict,
                                   timeout=CONF.hipchat_notifier.timeout)

            if result.status_code in range(200, 300):
                self._log.info("Notification successfully posted.")
                return True
            else:
                msg = ("Received an HTTP code {} when trying to send to hipchat on URL {}"
                       " with response {}.")
                self._log.error(msg.format(result.status_code, url, result.text))
                return False
        except Exception:
            self._log.exception("Error trying to send to hipchat on URL {}".format(url))
            return False
