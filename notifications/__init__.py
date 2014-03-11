import json


class Notification(object):
    """ An abstract base class used to define the notification interface and common functions
    """
    def __init__(self, src_partition, src_offset, tenant_id, name, address, timeout=60):
        """ Setup the notification object
            The src_partition and src_offset allow the notification to be linked to the alarm that it came from
            The timeout is how long to wait for the notification to send. Waiting too long will cause other finished
            notifications that come after this one to remain uncommitted.
        """
        self.address = address
        self.name = name
        self.src_partition = src_partition
        self.src_offset = src_offset
        self.tenant_id = tenant_id
        self.timeout = timeout

    def to_json(self):
        """ Return json representation
        """
        return json.dumps(self.__dict__)

    def send(self):
        """ Send the notification
        """
        raise NotImplementedError