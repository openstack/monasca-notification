# -*- coding: utf-8 -*-

# Copyright 2016 Fujitsu Technology Solutions
# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
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

from datetime import datetime
from sqlalchemy import Column, String, Integer, Enum, DateTime, ForeignKey, Table

ALARM_STATES = ('UNDETERMINED', 'OK', 'ALARM')


def create_alarm_action_model(metadata=None):
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
                 Column('period', Integer),
                 Column('created_at', DateTime, default=lambda: datetime.utcnow()),
                 Column('updated_at', DateTime, onupdate=lambda: datetime.utcnow()))


def create_notification_method_type_model(metadata=None):
    return Table('notification_method_type', metadata,
                 Column('name', String(20), primary_key=True))


def create_alarm_model(metadata=None):
    return Table('alarm', metadata,
                 Column('id', String(20), primary_key=True),
                 Column('alarm_definition_id', String(36)),
                 Column('state', Enum(*ALARM_STATES)),
                 Column('lifecycle_state', String(50)),
                 Column('link', String(512)),
                 Column('created_at', DateTime, default=lambda: datetime.utcnow()),
                 Column('updated_at', DateTime, onupdate=lambda: datetime.utcnow()),
                 Column('state_updated_at', DateTime))
