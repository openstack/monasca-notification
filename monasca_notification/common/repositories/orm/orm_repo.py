# Copyright 2015 FUJITSU LIMITED
# (C) Copyright 2015,2016 Hewlett Packard Enterprise Development Company LP
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

        self._orm_query = select([nm.c.name, nm.c.type, nm.c.address, nm.c.periodic_interval])\
            .select_from(aa.join(nm, aa.c.action_id == nm.c.id))\
            .where(
                and_(aa.c.alarm_definition_id == bindparam('alarm_definition_id'),
                     aa.c.alarm_state == bindparam('alarm_state')))

        self._orm = None

    def fetch_notification(self, alarm):
        try:
            with self._orm_engine.connect() as conn:
                log.debug('Orm query {%s}', str(self._orm_query))
                notifications = conn.execute(self._orm_query,
                                             alarm_definition_id=alarm['alarmDefinitionId'],
                                             alarm_state=alarm['newState'])

                return [(row[1].lower(), row[0], row[2], row[3]) for row in notifications]
        except DatabaseError as e:
            log.exception("Couldn't fetch alarms actions %s", e)
            raise exc.DatabaseException(e)
