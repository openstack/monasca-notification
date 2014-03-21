"""Tests the notification class."""

import json
from mon_notification import notification


def test_json():
    """Test the to_json method to verify it behaves as expected.
    """
    alarm = {'alarmId': 'alarmId',
             'alarmName': 'alarmName',
             'timestamp': 'timestamp',
             'stateChangeReason': 'stateChangeReason',
             'newState': 'newState',
             'tenantId': 'tenantId'}
    test_notification = notification.Notification('ntype', 'src_partition', 'src_offset', 'name', 'address', alarm)

    expected_dict = {u'name': u'name',
                     u'notification_timestamp': None,
                     u'tenant_id': u'tenantId',
                     u'alarm_name': u'alarmName',
                     u'alarm_id': u'alarmId',
                     u'state': u'newState',
                     u'alarm_timestamp': u'timestamp',
                     u'address': u'address',
                     u'message': u'stateChangeReason'}
    # Compare as dicts so ordering is not an issue
    assert json.loads(test_notification.to_json()) == expected_dict


def test_equal():
    alarm = {'alarmId': 'alarmId',
             'alarmName': 'alarmName',
             'timestamp': 'timestamp',
             'stateChangeReason': 'stateChangeReason',
             'newState': 'newState',
             'tenantId': 'tenantId'}
    test_notification = notification.Notification('ntype', 'src_partition', 'src_offset', 'name', 'address', alarm)
    test_notification2 = notification.Notification('ntype', 'src_partition', 'src_offset', 'name', 'address', alarm)

    assert(test_notification == test_notification2)


def test_unequal():
    alarm = {'alarmId': 'alarmId',
             'alarmName': 'alarmName',
             'timestamp': 'timestamp',
             'stateChangeReason': 'stateChangeReason',
             'newState': 'newState',
             'tenantId': 'tenantId'}
    test_notification = notification.Notification('ntype', 'src_partition', 'src_offset', 'name', 'address', alarm)
    test_notification2 = notification.Notification('ntype', 'src_partition', 'src_offset', 'name', 'address', alarm)
    test_notification2.alarm_id = None

    assert(test_notification != test_notification2)
