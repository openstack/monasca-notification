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

import kafka.client
import kafka.common
import kafka.consumer
import logging
import monascastatsd

from kazoo.client import KazooClient
from kazoo.recipe.partitioner import SetPartitioner
from monasca_notification.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class KafkaConsumer(BaseProcessor):
    """Read alarm from the alarm topic
       No commit is being done until processing is finished
    """
    def __init__(self, kafka_url, zookeeper_url, zookeeper_path, group, topic):
        """Init
             kafka_url, group, topic - kafka connection details
        """

        self._kafka_topic = topic

        self._zookeeper_url = zookeeper_url
        self._zookeeper_path = zookeeper_path

        self._statsd = monascastatsd.Client(name='monasca', dimensions=BaseProcessor.dimensions)

        self._kafka = kafka.client.KafkaClient(kafka_url)

        # No auto-commit so that commits only happen after the alarm is processed.
        self._consumer = kafka.consumer.SimpleConsumer(self._kafka,
                                                       group,
                                                       self._kafka_topic,
                                                       auto_commit=False,
                                                       iter_timeout=5)

        self._consumer.provide_partition_info()  # Without this the partition is not provided in the response
        self._consumer.fetch_last_known_offsets()

    def __iter__(self):
        """Consume messages from kafka using the Kazoo SetPartitioner to
           allow multiple consumer processes to negotiate access to the kafka
           partitions
        """

        # KazooClient and SetPartitioner objects need to be instantiated after
        # the consumer process has forked.  Instantiating prior to forking
        # gives the appearance that things are working but after forking the
        # connection to zookeeper is lost and no state changes are visible

        kazoo_client = KazooClient(hosts=self._zookeeper_url)
        kazoo_client.start()

        set_partitioner = (
            SetPartitioner(kazoo_client,
                           path=self._zookeeper_path,
                           set=self._consumer.fetch_offsets.keys()))

        consumed_from_kafka = self._statsd.get_counter(name='consumed_from_kafka')

        try:
            partitions = []

            while 1:
                if set_partitioner.failed:
                    raise Exception("Failed to acquire partition")

                elif set_partitioner.release:
                    log.info("Releasing locks on partition set {} "
                             "for topic {}".format(partitions,
                                                   self._kafka_topic))
                    set_partitioner.release_set()

                    partitions = []

                elif set_partitioner.acquired:
                    if not partitions:
                        partitions = [p for p in set_partitioner]

                        log.info("Acquired locks on partition set {} "
                                 "for topic {}".format(partitions, self._kafka_topic))

                        # Refresh the last known offsets again to make sure
                        # that they are the latest after having acquired the
                        # lock. Updates self._consumer.fetch_offsets.
                        self._consumer.fetch_last_known_offsets()

                        # Modify self._consumer.fetch_offsets to hold only the
                        # offsets for the set of Kafka partitions acquired
                        # by this instance of the persister.

                        partitioned_fetch_offsets = {}
                        for p in partitions:
                            partitioned_fetch_offsets[p] = (
                                self._consumer.fetch_offsets[p])

                        self._consumer.fetch_offsets = partitioned_fetch_offsets

                    for message in self._consumer:
                        if not set_partitioner.acquired:
                            break
                        consumed_from_kafka += 1
                        log.debug("Consuming message from kafka, "
                                  "partition {}, offset {}".format(message[0],
                                                                   message[1].offset))
                        yield message

                elif set_partitioner.allocating:
                    log.info("Waiting to acquire locks on partition set")
                    set_partitioner.wait_for_acquire()

        except:
            log.exception('KafkaConsumer encountered fatal exception '
                          'processing messages.')
            raise

    def commit(self, partition):
        self._consumer.commit(partition)
