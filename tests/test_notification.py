# (C) Copyright 2014-2016 Hewlett Packard Enterprise Development LP
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

"""Tests the notification class."""

import json
from monasca_notification import notification


def test_json():
    """Test the to_json method to verify it behaves as expected.
    """
    ts = 1429029121239
    alarm = {'alarmId': 'alarmId',
             'alarmName': 'alarmName',
             'timestamp': ts,
             'stateChangeReason': 'stateChangeReason',
             'newState': 'newState',
             'severity': 'LOW',
             "link": "some-link",
             "lifecycleState": "OPEN",
             'tenantId': 'tenantId',
             'metrics': 'cpu_util'}
    test_notification = notification.Notification(1, 'ntype', 'name',
                                                  'address', 0, 0, alarm)

    expected_dict = {u'id': 1,
                     u'name': u'name',
                     u'type': u'ntype',
                     u'notification_timestamp': None,
                     u'tenant_id': u'tenantId',
                     u'alarm_name': u'alarmName',
                     u'alarm_id': u'alarmId',
                     u'state': u'newState',
                     u'severity': u'LOW',
                     u'link': u'some-link',
                     u'lifecycle_state': u'OPEN',
                     u'alarm_timestamp': ts / 1000,
                     u'address': u'address',
                     u'message': u'stateChangeReason',
                     u'period': 0,
                     u'retry_count': 0,
                     u'raw_alarm': {
                         u'alarmId': u'alarmId',
                         u'alarmName': u'alarmName',
                         u'timestamp': ts,
                         u'stateChangeReason': u'stateChangeReason',
                         u'newState': u'newState',
                         u'severity': u'LOW',
                         u'link': u'some-link',
                         u'lifecycleState': u'OPEN',
                         u'tenantId': u'tenantId',
                         u'metrics': u'cpu_util'}}

    # Compare as dicts so ordering is not an issue
    assert json.loads(test_notification.to_json()) == expected_dict


def test_json_non_zero_period():
    """Test the to_json method to verify it behaves as expected.
    """
    ts = 1429029121239
    alarm = {'alarmId': 'alarmId',
             'alarmName': 'alarmName',
             'timestamp': ts,
             'stateChangeReason': 'stateChangeReason',
             'newState': 'newState',
             'severity': 'LOW',
             "link": "some-link",
             "lifecycleState": "OPEN",
             'tenantId': 'tenantId',
             'metrics': 'cpu_util'}
    test_notification = notification.Notification(1, 'ntype', 'name',
                                                  'address', 60, 0, alarm)

    expected_dict = {u'id': 1,
                     u'name': u'name',
                     u'type': u'ntype',
                     u'notification_timestamp': None,
                     u'tenant_id': u'tenantId',
                     u'alarm_name': u'alarmName',
                     u'alarm_id': u'alarmId',
                     u'state': u'newState',
                     u'severity': u'LOW',
                     u'link': u'some-link',
                     u'lifecycle_state': u'OPEN',
                     u'alarm_timestamp': ts / 1000,
                     u'address': u'address',
                     u'message': u'stateChangeReason',
                     u'period': 60,
                     u'retry_count': 0,
                     u'raw_alarm': {
                         u'alarmId': u'alarmId',
                         u'alarmName': u'alarmName',
                         u'timestamp': ts,
                         u'stateChangeReason': u'stateChangeReason',
                         u'newState': u'newState',
                         u'severity': u'LOW',
                         u'link': u'some-link',
                         u'lifecycleState': u'OPEN',
                         u'tenantId': u'tenantId',
                         u'metrics': u'cpu_util'}}

    # Compare as dicts so ordering is not an issue
    assert json.loads(test_notification.to_json()) == expected_dict


def test_equal():
    alarm = {'alarmId': 'alarmId',
             'alarmName': 'alarmName',
             'timestamp': 1429029121239,
             'stateChangeReason': 'stateChangeReason',
             'newState': 'newState',
             'severity': 'LOW',
             "link": "some-link",
             "lifecycleState": "OPEN",
             'tenantId': 'tenantId',
             'metrics': 'cpu_util'}
    test_notification = notification.Notification(0, 'ntype', 'name',
                                                  'address', 0, 0, alarm)
    test_notification2 = notification.Notification(0, 'ntype', 'name',
                                                   'address', 0, 0, alarm)

    assert(test_notification == test_notification2)


def test_unequal():
    alarm = {'alarmId': 'alarmId',
             'alarmName': 'alarmName',
             'timestamp': 1429029121239,
             'stateChangeReason': 'stateChangeReason',
             'newState': 'newState',
             'severity': 'LOW',
             "link": "some-link",
             "lifecycleState": "OPEN",
             'tenantId': 'tenantId',
             'metrics': 'cpu_util'}
    test_notification = notification.Notification(0, 'ntype', 'name',
                                                  'address', 0, 0, alarm)
    test_notification2 = notification.Notification(1, 'ntype', 'name',
                                                   'address', 0, 0, alarm)
    test_notification2.alarm_id = None

    assert(test_notification != test_notification2)
