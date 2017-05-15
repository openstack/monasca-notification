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

from oslo_log import log as logging

from monasca_notification.common.repositories import exceptions as exc
from monasca_notification.common.utils import get_db_repo
from monasca_notification.common.utils import get_statsd_client
from monasca_notification.types import notifiers

log = logging.getLogger(__name__)


class NotificationProcessor(object):

    def __init__(self):
        self.statsd = get_statsd_client()
        notifiers.init(self.statsd)

        notifiers.load_plugins()
        notifiers.config()

        self._db_repo = get_db_repo()
        self.insert_configured_plugins()

    def _remaining_plugin_types(self):
        configured_plugin_types = notifiers.enabled_notifications()
        persisted_plugin_types = self._db_repo.fetch_notification_method_types()

        return set(configured_plugin_types) - set(persisted_plugin_types)

    def insert_configured_plugins(self):
        """Persists configured plugin types in DB
             For each notification type configured add it in db, if it is not there
        """
        remaining_plugin_types = self._remaining_plugin_types()

        max_retry = len(remaining_plugin_types)
        retry_count = 0
        while remaining_plugin_types:
            retry_count = retry_count + 1
            try:
                log.info("New plugins detected: Adding new notification types %s to database",
                         remaining_plugin_types)
                self._db_repo.insert_notification_method_types(remaining_plugin_types)
            except exc.DatabaseException as e:
                # There is a possibility the other process has already registered the type.
                remaining_plugin_types = self._remaining_plugin_types()
                if remaining_plugin_types and (retry_count >= max_retry):
                    log.exception("Couldn't insert notification types %s", e)
                    raise e
                else:
                    log.debug("Plugin already exists. Ignore exception")

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
