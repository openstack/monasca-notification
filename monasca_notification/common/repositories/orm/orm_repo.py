# Copyright 2015 FUJITSU LIMITED
# (C) Copyright 2015,2016 Hewlett Packard Enterprise Development LP
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

import logging
from sqlalchemy import engine_from_config, MetaData
from sqlalchemy.sql import select, bindparam, and_
from sqlalchemy.exc import DatabaseError

from monasca_notification.common.repositories import exceptions as exc
from monasca_notification.common.repositories.orm import models

log = logging.getLogger(__name__)


class OrmRepo(object):
    def __init__(self, config):
        self._orm_engine = engine_from_config(config['database']['orm'], prefix='')

        metadata = MetaData()

        aa = models.create_alarm_action_model(metadata).alias('aa')
        nm = models.create_notification_method_model(metadata).alias('nm')
        nmt = models.create_notification_method_type_model(metadata).alias('nmt')
        a = models.create_alarm_model(metadata).alias('a')

        self._orm_query = select([nm.c.id, nm.c.type, nm.c.name, nm.c.address, nm.c.period])\
            .select_from(aa.join(nm, aa.c.action_id == nm.c.id))\
            .where(
                and_(aa.c.alarm_definition_id == bindparam('alarm_definition_id'),
                     aa.c.alarm_state == bindparam('alarm_state')))

        self._orm_get_alarm_state = select([a.c.state]).where(a.c.id == bindparam('alarm_id'))

        self._orm_nmt_query = select([nmt.c.name])

        self._orm_get_notification = select([nm.c.name, nm.c.type, nm.c.address, nm.c.period])\
            .where(nm.c.id == bindparam('notification_id'))

        self._orm = None

    def fetch_notifications(self, alarm):
        try:
            with self._orm_engine.connect() as conn:
                log.debug('Orm query {%s}', str(self._orm_query))
                notifications = conn.execute(self._orm_query,
                                             alarm_definition_id=alarm['alarmDefinitionId'],
                                             alarm_state=alarm['newState'])

                return [(row[0], row[1].lower(), row[2], row[3], row[4]) for row in notifications]
        except DatabaseError as e:
            log.exception("Couldn't fetch alarms actions %s", e)
            raise exc.DatabaseException(e)

    def get_alarm_current_state(self, alarm_id):
        try:
            with self._orm_engine.connect() as conn:
                log.debug('Orm query {%s}', str(self._orm_get_alarm_state))
                result = conn.execute(self._orm_get_alarm_state,
                                      alarm_id=alarm_id)
                row = result.fetchone()
                state = row[0] if row is not None else None
                return state
        except DatabaseError as e:
            log.exception("Couldn't fetch the current alarm state %s", e)
            raise exc.DatabaseException(e)

    def fetch_notification_method_types(self):
        try:
            with self._orm_engine.connect() as conn:
                log.debug('Orm query {%s}', str(self._orm_nmt_query))
                notification_method_types = conn.execute(self._orm_nmt_query).fetchall()

                return [row[0] for row in notification_method_types]
        except DatabaseError as e:
            log.exception("Couldn't fetch notification method types %s", e)
            raise exc.DatabaseException(e)

    def insert_notification_method_types(self, notification_types):
        try:
            with self._orm_engine.connect() as conn:
                for notification_type in notification_types:
                    conn.execute(self.nmt.insert(), notification_type)

        except DatabaseError as e:
            log.exception("Couldn't insert notification types %s", e)
            raise exc.DatabaseException(e)

    def get_notification(self, notification_id):
        try:
            with self._orm_engine.connect() as conn:
                log.debug('Orm query {%s}', str(self._orm_get_notification))
                result = conn.execute(self._orm_get_notification,
                                      notification_id=notification_id)
                notification = result.fetchone()
                if notification is None:
                    return None
                else:
                    return [notification[0], notification[1].lower(), notification[2], notification[3]]
        except DatabaseError as e:
            log.exception("Couldn't fetch the notification method %s", e)
            raise exc.DatabaseException(e)
