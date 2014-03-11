from . import Notification


class EmailNotification(Notification):
    def send(self):
        """ Email the notification via SMTP
        """
        pass  # todo
# todo the smtp connection should have the ability to round robin over multiple connections which are managed and kept open
# Make sure there is a timeout so things are not held up here.