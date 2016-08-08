# Copyright 2015 FUJITSU LIMITED
# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing permissions and limitations under
# the License.


class BaseRepo(object):
    def __init__(self, config):
        self._find_alarm_action_sql = """SELECT id, type, name, address, period
                                         FROM alarm_action as aa
                                         JOIN notification_method as nm ON aa.action_id = nm.id
                                         WHERE aa.alarm_definition_id = %s and aa.alarm_state = %s"""
        self._find_alarm_state_sql = """SELECT state
                                         FROM alarm
                                         WHERE alarm.id = %s"""
        self._insert_notification_types_sql = """INSERT INTO notification_method_type (name) VALUES ( %s)"""
        self._find_all_notification_types_sql = """SELECT name from notification_method_type """
        self._get_notification_sql = """SELECT name, type, address, period
                                        FROM notification_method
                                        WHERE id = %s"""
