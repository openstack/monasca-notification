import logging

from notification_exceptions import NotificationException

log = logging.getLogger(__name__)


class NotificationProcessor(object):

    def __init__(self, notification_queue, sent_notification_queue):
        self.notification_queue = notification_queue
        self.sent_notification_queue = sent_notification_queue

    def run(self):
        """ Send the notifications
        """
        while True:
            notifications = self.notification_queue.get()
            for notification in notifications:
                try:
                    notification.send()
                except NotificationException, e:
                    log.error("Error sending Notification:%s\nError:%s" % (notification.to_json(), e))
            if self.sent_notification_queue.full():
                log.warn('Sent Notifications sent_queue is full, publishing is blocked')
            self.sent_notification_queue.put(notifications)
            log.debug("Put notifications from alarm partition %d, offset %d on the notification_sent queue"
                      % (notification.src_partition, notification.src_offset))

