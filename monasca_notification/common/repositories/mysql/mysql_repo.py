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
import pymysql

from monasca_notification.common.repositories.base import base_repo
from monasca_notification.common.repositories import exceptions as exc

log = logging.getLogger(__name__)


class MysqlRepo(base_repo.BaseRepo):
    def __init__(self, config):
        super(MysqlRepo, self).__init__(config)
        if 'ssl' in config['mysql']:
            self._mysql_ssl = config['mysql']['ssl']
        else:
            self._mysql_ssl = None

        if 'port' in config['mysql']:
            self._mysql_port = config['mysql']['port']
        else:
            #
            # If port isn't specified in the config file,
            # set it to the default value.
            #
            self._mysql_port = 3306

        self._mysql_host = config['mysql']['host']
        self._mysql_user = config['mysql']['user']
        self._mysql_passwd = config['mysql']['passwd']
        self._mysql_dbname = config['mysql']['db']
        self._mysql = None

    def _connect_to_mysql(self):
        self._mysql = None
        try:
            self._mysql = pymysql.connect(host=self._mysql_host,
                                          port=self._mysql_port,
                                          user=self._mysql_user,
                                          passwd=unicode(self._mysql_passwd).encode('utf-8'),
                                          db=self._mysql_dbname,
                                          ssl=self._mysql_ssl,
                                          use_unicode=True,
                                          charset="utf8")
            self._mysql.autocommit(True)
        except pymysql.Error as e:
            log.exception('MySQL connect failed %s', e)
            raise

    def fetch_notifications(self, alarm):
        try:
            if self._mysql is None:
                self._connect_to_mysql()
            cur = self._mysql.cursor()
            cur.execute(self._find_alarm_action_sql, (alarm['alarmDefinitionId'], alarm['newState']))

            for row in cur:
                yield (row[0], row[1].lower(), row[2], row[3], row[4])
        except pymysql.Error as e:
            self._mysql = None
            log.exception("Couldn't fetch alarms actions %s", e)
            raise exc.DatabaseException(e)

    def get_alarm_current_state(self, alarm_id):
        try:
            if self._mysql is None:
                self._connect_to_mysql()
            cur = self._mysql.cursor()
            cur.execute(self._find_alarm_state_sql, alarm_id)
            row = cur.fetchone()
            state = row[0] if row is not None else None
            return state
        except pymysql.Error as e:
            self._mysql = None
            log.exception("Couldn't fetch the current alarm state %s", e)
            raise exc.DatabaseException(e)

    def fetch_notification_method_types(self):
        try:
            if self._mysql is None:
                self._connect_to_mysql()
            cur = self._mysql.cursor()
            cur.execute(self._find_all_notification_types_sql)

            for row in cur:
                yield (row[0])
        except pymysql.Error as e:
            self._mysql = None
            log.exception("Couldn't fetch notification types %s", e)
            raise exc.DatabaseException(e)

    def insert_notification_method_types(self, notification_types):
        try:
            if self._mysql is None:
                self._connect_to_mysql()
            cur = self._mysql.cursor()
            cur.executemany(self._insert_notification_types_sql, notification_types)

        except pymysql.IntegrityError as ignoredException:
            # If multiple instances of the notification engine tries to write the
            # same content at the same time, only one of them will succeed and others will
            # get duplicate primary key, integrity error. We can safely ignore this error.
            # This may happen only during the first start when the tables are empty.
            code, mesg = ignoredException.args
            if code == pymysql.constants.ER.DUP_ENTRY:
                log.debug("Notification type exists in DB. Ignoring the exception  {}".format(mesg))
            else:
                raise exc.DatabaseException(ignoredException)
        except pymysql.Error as e:
            self._mysql = None
            log.exception("Couldn't insert notification types %s", e)
            raise exc.DatabaseException(e)

    def get_notification(self, notification_id):
        try:
            if self._mysql is None:
                self._connect_to_mysql()
            cur = self._mysql.cursor()
            cur.execute(self._get_notification_sql, notification_id)
            row = cur.fetchone()
            if row is None:
                return None
            else:
                return [row[0], row[1].lower(), row[2], row[3]]
        except pymysql.Error as e:
            self._mysql = None
            log.exception("Couldn't fetch the notification method %s", e)
            raise exc.DatabaseException(e)
