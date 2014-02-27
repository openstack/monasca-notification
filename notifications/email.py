from . import Notification

class EmailNotification(Notification):
    pass

# todo the smtp connection should have the ability to round robin over multiple connections which are managed and kept open