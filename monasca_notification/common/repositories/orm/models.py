# -*- coding: utf-8 -*-

# Copyright 2015 Fujitsu Technology Solutions
# (C) Copyright 2016 Hewlett Packard Enterprise Development Company LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime, ForeignKey, Table


def create_alarm_action_model(metadata=None):
    ALARM_STATES = ('UNDETERMINED', 'OK', 'ALARM')
    return Table('alarm_action', metadata,
                 Column('action_id',
                        String(36), ForeignKey('notification_method.id'),
                        nullable=False, primary_key=True),
                 Column('alarm_definition_id', String(36), primary_key=True),
                 Column('alarm_state', Enum(*ALARM_STATES), primary_key=True))


def create_notification_method_model(metadata=None):
    return Table('notification_method', metadata,
                 Column('id', String(36), primary_key=True),
                 Column('address', String(100)),
                 Column('name', String(250)),
                 Column('tenant_id', String(36)),
                 Column('type', String(255)),
                 Column('period', int),
                 Column('created_at', DateTime, default=lambda: datetime.utcnow()),
                 Column('updated_at', DateTime, onupdate=lambda: datetime.utcnow()))
