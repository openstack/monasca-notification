import logging

log = logging.getLogger(__name__)


class BaseProcessor(object):
    @staticmethod
    def _add_to_queue(queue, queue_name, msg):
        """ Warns on full queue then does a blocking push to the queue.
        """
        if queue.full():
            log.warn('Queue %s is full, publishing is blocked' % queue_name)
        queue.put(msg)
        log.debug("Put message %s on queue %s" % (msg, queue_name))
