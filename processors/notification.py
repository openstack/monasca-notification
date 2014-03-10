import logging

log = logging.getLogger(__name__)


class NotificationProcessor(object):

    def __init__(self, notification_queue, sent_notification_queue):
        self.notification_queue = notification_queue
        self.sent_notification_queue = sent_notification_queue

    def run(self):
        """ Send the notifications
        """
        while True:
            notification = self.notification_queue.get()
# todo block if the sent_notification sent_queue is full
#            if self.sent_notification_queue.full():
#                log.debug('Sent Notifications sent_queue is full, publishing is blocked')
            notification.send()
            self.sent_notification_queue.put(notification)
            log.debug("Put notification on the sent notification sent_queue")  # todo make this debug info better

