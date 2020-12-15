# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
# Copyright 2016 FUJITSU LIMITED

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import monascastatsd

from keystoneauth1 import exceptions as kaexception
from keystoneauth1 import loading as kaloading
from oslo_config import cfg
from oslo_log import log

from monasca_notification.common.repositories import exceptions
from monasca_notification.notification import Notification

LOG = log.getLogger(__name__)
CONF = cfg.CONF

NOTIFICATION_DIMENSIONS = {'service': 'monitoring',
                           'component': 'monasca-notification'}


def get_db_repo():
    repo_driver = CONF.database.repo_driver
    LOG.debug('Enabling the %s RDB repository', repo_driver)
    return repo_driver(CONF)


def construct_notification_object(db_repo, notification_json):
    try:
        notification = Notification(notification_json['id'],
                                    notification_json['type'],
                                    notification_json['name'],
                                    notification_json['address'],
                                    notification_json['period'],
                                    notification_json['retry_count'],
                                    notification_json['raw_alarm'])
        # Grab notification method from database to see if it was changed
        stored_notification = grab_stored_notification_method(db_repo, notification.id)
        # Notification method was deleted
        if stored_notification is None:
            LOG.debug("Notification method {0} was deleted from database. "
                      "Will stop sending.".format(notification.id))
            return None
        # Update notification method with most up to date values
        else:
            notification.name = stored_notification[0]
            notification.type = stored_notification[1]
            notification.address = stored_notification[2]
            notification.period = stored_notification[3]
            return notification
    except exceptions.DatabaseException:
        LOG.warn("Error querying mysql for notification method. "
                 "Using currently cached method.")
        return notification
    except Exception as e:
        LOG.warn("Error when attempting to construct notification {0}".format(e))
        return None


def grab_stored_notification_method(db_repo, notification_id):
    try:
        stored_notification = db_repo.get_notification(notification_id)
    except exceptions.DatabaseException:
        LOG.debug('Database Error.  Attempting reconnect')
        stored_notification = db_repo.get_notification(notification_id)

    return stored_notification


def get_statsd_client(dimensions=None):
    local_dims = dimensions.copy() if dimensions else {}
    local_dims.update(NOTIFICATION_DIMENSIONS)
    if CONF.statsd.enable:
        LOG.debug("Establishing connection with statsd on {0}:{1}"
                  .format(CONF.statsd.host, CONF.statsd.port))
        client = monascastatsd.Client(name='monasca',
                                      host=CONF.statsd.host,
                                      port=CONF.statsd.port,
                                      dimensions=local_dims)
    else:
        LOG.warn("StatsD monitoring disabled. Overriding monascastatsd.Client to use it offline")
        client = OfflineClient(name='monasca',
                               host=CONF.statsd.host,
                               port=CONF.statsd.port,
                               dimensions=local_dims)
    return client


class OfflineClient(monascastatsd.Client):

    def _set_connection(self, connection, host, port):
        if connection is None:
            self.connection = OfflineConnection(host=host,
                                                port=port,
                                                max_buffer_size=self._max_buffer_size)
        else:
            self.connection = connection


class OfflineConnection(monascastatsd.Connection):

    def __init__(self, host='localhost', port=8125, max_buffer_size=50):
        """Initialize an Offline Connection object.

        >>> monascastatsd = MonascaStatsd()

        :name: the name for this client.  Everything sent by this client
            will be prefixed by name
        :param host: the host of the MonascaStatsd server.
        :param port: the port of the MonascaStatsd server.
        :param max_buffer_size: Maximum number of metric to buffer before
         sending to the server if sending metrics in batch
        """
        self.max_buffer_size = max_buffer_size
        self._send = self._send_to_server
        self.connect(host, port)
        self.encoding = 'utf-8'

    def connect(self, host, port):
        """Avoid connecting to the monascastatsd server.

        """
        pass

    def _send_to_server(self, packet):
        pass


def get_keystone_session():

    auth_details = {}
    auth_details['auth_url'] = CONF.keystone.auth_url
    auth_details['username'] = CONF.keystone.username
    auth_details['password'] = CONF.keystone.password
    auth_details['project_name'] = CONF.keystone.project_name
    auth_details['user_domain_name'] = CONF.keystone.user_domain_name
    auth_details['project_domain_name'] = CONF.keystone.project_domain_name
    loader = kaloading.get_plugin_loader('password')
    auth_plugin = loader.load_from_options(**auth_details)
    session = kaloading.session.Session().load_from_options(
        auth=auth_plugin)
    return session


def get_auth_token():
    error_message = 'Keystone request failed: {}'
    try:
        session = get_keystone_session()
        auth_token = session.get_token()
        return auth_token
    except (kaexception.Unauthorized, kaexception.DiscoveryFailure) as e:
        LOG.exception(error_message.format(str(e)))
        raise
    except Exception as e:
        LOG.exception(error_message.format(str(e)))
        raise
