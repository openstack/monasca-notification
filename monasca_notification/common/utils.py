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
import logging
import monascastatsd

from monasca_common.simport import simport

from monasca_notification.common.repositories import exceptions
from monasca_notification.notification import Notification

log = logging.getLogger(__name__)

NOTIFICATION_DIMENSIONS = {'service': 'monitoring',
                           'component': 'monasca-notification'}


def get_db_repo(config):
    if 'database' in config and 'repo_driver' in config['database']:
        return simport.load(config['database']['repo_driver'])(config)
    else:
        return simport.load('monasca_notification.common.repositories.mysql.mysql_repo:MysqlRepo')(config)


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
            log.debug("Notification method {0} was deleted from database. "
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
        log.warn("Error querying mysql for notification method. "
                 "Using currently cached method.")
        return notification
    except Exception as e:
        log.warn("Error when attempting to construct notification {0}".format(e))
        return None


def grab_stored_notification_method(db_repo, notification_id):
        try:
            stored_notification = db_repo.get_notification(notification_id)
        except exceptions.DatabaseException:
            log.debug('Database Error.  Attempting reconnect')
            stored_notification = db_repo.get_notification(notification_id)

        return stored_notification


def get_statsd_client(config, dimensions=None):
    local_dims = dimensions.copy() if dimensions else {}
    local_dims.update(NOTIFICATION_DIMENSIONS)
    if 'statsd' in config:
        client = monascastatsd.Client(name='monasca',
                                      host=config['statsd'].get('host', 'localhost'),
                                      port=config['statsd'].get('port', 8125),
                                      dimensions=local_dims)
    else:
        client = monascastatsd.Client(name='monasca',
                                      dimensions=local_dims)
    return client
