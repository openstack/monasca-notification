import json


class Notification(object):
    """ An abstract base class used to define the notification interface and common functions
    """
    def __init__(self, src_partition, src_offset, name, address, alarm, timeout=60):
        """ Setup the notification object
            The src_partition and src_offset allow the notification to be linked to the alarm that it came from
            name - Name used in sending
            address - to send the notification to
            alarm_data - info that caused the notification
            The timeout is how long to wait for the notification to send. Waiting too long will cause other finished
            notifications that come after this one to remain uncommitted.
        """
        self.address = address
        self.name = name
        self.src_partition = src_partition
        self.src_offset = src_offset
        self.timeout = timeout

        self.alarm_id = alarm['alarmId']
        self.alarm_name = alarm['alarmName']
        self.alarm_timestamp = alarm['timestamp']
        self.message = alarm['stateChangeReason']
        self.state = alarm['newState']
        self.tenant_id = alarm['tenantId']

        self.notification_timestamp = None  # to be updated on actual notification send time

    def to_json(self):
        """ Return json representation
        """
        notification_fields = [
            'address',
            'name',
            'alarm_id',
            'alarm_name',
            'alarm_timestamp',
            'message',
            'notification_timestamp',
            'state',
            'tenant_id'
        ]
        notification_data = {name: self.__dict__[name] for name in notification_fields}
        return json.dumps(notification_data)

    def send(self):
        """ Send the notification
        """
        raise NotImplementedError