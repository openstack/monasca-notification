from email.mime.text import MIMEText
import logging
import smtplib
import time

from . import BaseProcessor

log = logging.getLogger(__name__)


class NotificationProcessor(BaseProcessor):

    def __init__(self, notification_queue, sent_notification_queue, finished_queue, email_config):
        self.notification_queue = notification_queue
        self.sent_notification_queue = sent_notification_queue
        self.finished_queue = finished_queue

        self.email_config = email_config
        self.smtp = None
        self._smtp_connect()

        # Types as key, method used to process that type as value
        self.notification_types = {'email': self._send_email}

    def _send_email(self, notification):
        """ Send the notification via email
            Returns the notification upon success, None upon failure
        """
        try:
            msg = MIMEText("%s\nAlarm %s transitioned to the %s state at %s\nFull Data:\n%s"
                           % (notification.message,
                              notification.alarm_name,
                              notification.state,
                              notification.alarm_timestamp,
                              notification.to_json()))
            msg['Subject'] = '%s: %s' % (notification.state, notification.alarm_name)
            msg['From'] = self.email_config['from_addr']
            msg['To'] = notification.address
            self.smtp.sendmail(self.email_config['from_addr'], notification.address, msg.as_string())

        except smtplib.SMTPException, e:
            log.error("Error sending Email Notification:%s\nError:%s" % (notification.to_json(), e))
            self._smtp_connect()  # Reconnect in case connection problems caused the failed email
        else:
            return notification

    def _smtp_connect(self):
        """ Connect to the smtp server
        """
        log.info('Connecting to Email Server %s' % self.email_config['server'])
        smtp = smtplib.SMTP(
            self.email_config['server'], self.email_config['port'], timeout=self.email_config['timeout'])

        if self.email_config['user'] is not None:
            smtp.login(self.email_config['user'], self.email_config['password'])

        if self.smtp is not None:
            self.smtp.quit()
        self.smtp = smtp

    def run(self):
        """ Send the notifications
            For each notification in a message it is sent according to its type.
            If all notifications fail the alarm partition/offset are added to the the finished queue
        """
        while True:
            notifications = self.notification_queue.get()
            sent_notifications = []
            for notification in notifications:
                if notification.type not in self.notification_types:
                    log.warn('Notification type %s is not a valid type' % notification.type)
                    continue
                else:
                    sent = self.notification_types[notification.type](notification)
                    if sent is not None:
                        sent.notification_timestamp = time.time()
                        sent_notifications.append(sent)

            if len(sent_notifications) == 0:  # All notifications failed
                self._add_to_queue(
                    self.finished_queue, 'finished', (notifications[0].src_partition, notifications[0].src_offset))
            else:
                self._add_to_queue(self.sent_notification_queue, 'sent_notification', sent_notifications)
