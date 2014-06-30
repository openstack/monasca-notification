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

log = logging.getLogger(__name__)


class BaseProcessor(object):
    @staticmethod
    def _add_to_queue(queue, queue_name, msg):
        """Warns on full queue then does a blocking push to the queue.
        """
        if queue.full():
            log.warn('Queue %s is full, publishing is blocked' % queue_name)
        queue.put(msg)
        log.debug("Put message %s on queue %s" % (msg, queue_name))
