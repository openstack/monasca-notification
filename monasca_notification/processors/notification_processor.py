# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
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
import monascastatsd

from monasca_notification.processors.base import BaseProcessor
from monasca_notification.types import notifiers

log = logging.getLogger(__name__)


class NotificationProcessor(BaseProcessor):

    def __init__(self, notification_queue,
                 sent_notification_queue, finished_queue, config):

        self.notification_queue = notification_queue
        self.sent_notification_queue = sent_notification_queue
        self.finished_queue = finished_queue

        self.statsd = monascastatsd.Client(name='monasca', dimensions=BaseProcessor.dimensions)

        self.config = config

    def run(self):
        """Send the notifications
             For each notification in a message it is sent according to its type.
             If all notifications fail the alarm partition/offset are added to the the finished queue
        """

        notifiers.init(self.statsd)
        notifiers.config(self.config)

        invalid_type_count = self.statsd.get_counter(name='invalid_type_count')
        sent_failed_count = self.statsd.get_counter(name='sent_failed_count')

        while True:
            notifications = self.notification_queue.get()
            sent, failed, invalid = notifiers.send_notifications(notifications)

            if failed > 0:
                sent_failed_count.increment(failed)

            if invalid > 0:
                invalid_type_count.increment(invalid)

            if sent:
                self._add_to_queue(self.sent_notification_queue,
                                   'sent_notification',
                                   sent)
            else:  # All notifications failed
                self._add_to_queue(self.finished_queue,
                                   'finished',
                                   (notifications[0].src_partition, notifications[0].src_offset))
