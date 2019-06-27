# Copyright 2017 FUJITSU LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg

from monasca_notification.conf import types

_POSTGRESQL = 'postgresql'
_MYSQL = 'mysql'
_ORM = 'orm'
_REPO_DRIVERS_MAP = {
    _POSTGRESQL: 'monasca_notification.common.repositories.'
                 'postgres.pgsql_repo:PostgresqlRepo',
    _MYSQL: 'monasca_notification.common.repositories.'
            'mysql.mysql_repo:MysqlRepo',
    _ORM: 'monasca_notification.common.repositories.'
          'orm.orm_repo:OrmRepo'
}
_ACCEPTABLE_DRIVER_KEYS = set(list(_REPO_DRIVERS_MAP.keys()) +
                              list(_REPO_DRIVERS_MAP.values()))

_DEFAULT_DB_HOST = '127.0.0.1'
_DEFAULT_DB_USER = 'notification'
_DEFAULT_DB_PASSWORD = 'password'  # nosec bandit B105
_DEFAULT_DB_NAME = 'mon'
_DEFAULT_POSTGRESQL_PORT = 5432
_DEFAULT_MYSQL_PORT = 3306

db_group = cfg.OptGroup('database',
                        title='Database Options',
                        help='Driver configuration for database connectivity.')

db_opts = [
    types.PluginOpt(name='repo_driver', choices=_ACCEPTABLE_DRIVER_KEYS,
                    default=_MYSQL, plugin_map=_REPO_DRIVERS_MAP,
                    required=True, advanced=True,
                    help='Driver name (or full class path) that should be '
                         'used to handle RDB connections. Accepts either '
                         'short labels {0} or full class names {1}. '
                         'Configuring either of them will require presence of '
                         'one of following sections {0} inside configuration '
                         'file.'.format(_REPO_DRIVERS_MAP.keys(),
                                        _REPO_DRIVERS_MAP.values())
                    )
]

orm_group = cfg.OptGroup('orm',
                         title='ORM Options',
                         help='Configuration options to configure '
                              'ORM RBD driver.')
orm_opts = [
    cfg.StrOpt(name='url', default=None,
               help='Connection string for sqlalchemy.')
]

mysql_group = cfg.OptGroup('mysql',
                           title='MySQL Options',
                           help='Configuration options to configure '
                                'plain MySQL RBD driver.')
mysql_opts = [
    cfg.HostAddressOpt(name='host', default=_DEFAULT_DB_HOST,
                       help='IP address of MySQL instance.'),
    cfg.PortOpt(name='port', default=_DEFAULT_MYSQL_PORT,
                help='Port number of MySQL instance.'),
    cfg.StrOpt(name='user', default=_DEFAULT_DB_USER,
               help='Username to connect to MySQL '
                    'instance and given database.'),
    cfg.StrOpt(name='passwd', default=_DEFAULT_DB_PASSWORD,
               ignore_case=True, secret=True,
               help='Password to connect to MySQL instance '
                    'and given database.'),
    cfg.DictOpt(name='ssl', default={},
                help='A dict of arguments similar '
                     'to mysql_ssl_set parameters.'),
    cfg.StrOpt(name='db', default=_DEFAULT_DB_NAME,
               help='Database name available in given MySQL instance.')
]

postgresql_group = cfg.OptGroup('postgresql',
                                title='PostgreSQL Options',
                                help='Configuration options to configure '
                                     'plain PostgreSQL RBD driver.')
postgresql_opts = [
    cfg.HostAddressOpt(name='host', default=_DEFAULT_DB_HOST,
                       help='IP address of PostgreSQL instance.'),
    cfg.PortOpt(name='port', default=_DEFAULT_POSTGRESQL_PORT,
                help='Port number of PostgreSQL instance.'),
    cfg.StrOpt(name='user', default=_DEFAULT_DB_USER,
               help='Username to connect to PostgreSQL '
                    'instance and given database.'),
    cfg.StrOpt(name='password', default=_DEFAULT_DB_PASSWORD,
               secret=True, help='Password to connect to PostgreSQL '
                                 'instance and given database'),
    cfg.StrOpt(name='database', default=_DEFAULT_DB_NAME,
               help='Database name available in '
                    'given PostgreSQL instance.')
]


def register_opts(conf):
    conf.register_group(db_group)
    conf.register_group(orm_group)
    conf.register_group(mysql_group)
    conf.register_group(postgresql_group)

    conf.register_opts(db_opts, group=db_group)
    conf.register_opts(orm_opts, group=orm_group)
    conf.register_opts(mysql_opts, group=mysql_group)
    conf.register_opts(postgresql_opts, group=postgresql_group)


def list_opts():
    return {
        db_group: db_opts,
        orm_group: orm_opts,
        mysql_group: mysql_opts,
        postgresql_group: postgresql_opts,
    }
