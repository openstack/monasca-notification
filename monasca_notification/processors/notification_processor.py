# (C) Copyright 2014-2016 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from monasca_notification.common.utils import get_db_repo
from monasca_notification.common.utils import get_statsd_client
from monasca_notification.types import notifiers

log = logging.getLogger(__name__)


class NotificationProcessor(object):

    def __init__(self, config):
        self.statsd = get_statsd_client(config)
        notifiers.init(self.statsd)
        notifiers.load_plugins(config['notification_types'])
        notifiers.config(config['notification_types'])
        self._db_repo = get_db_repo(config)
        self.insert_configured_plugins()

    def insert_configured_plugins(self):
        """Persists configured plugin types in DB
             For each notification type configured add it in db, if it is not there
        """
        configured_plugin_types = notifiers.enabled_notifications()

        persisted_plugin_types = self._db_repo.fetch_notification_method_types()
        remaining_plugin_types = set(configured_plugin_types) - set(persisted_plugin_types)

        if remaining_plugin_types:
            log.info("New plugins detected: Adding new notification types {} to database"
                     .format(remaining_plugin_types))
            self._db_repo.insert_notification_method_types(remaining_plugin_types)

    def send(self, notifications):
        """Send the notifications
             For each notification in a message it is sent according to its type.
             If all notifications fail the alarm partition/offset are added to the finished queue
        """

        invalid_type_count = self.statsd.get_counter(name='invalid_type_count')
        sent_failed_count = self.statsd.get_counter(name='sent_failed_count')

        sent, failed, invalid = notifiers.send_notifications(notifications)

        if failed:
            sent_failed_count.increment(len(failed))

        if invalid:
            invalid_type_count.increment(len(invalid))

        return sent, failed
