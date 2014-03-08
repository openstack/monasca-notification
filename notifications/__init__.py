import json

class Notification(object):
    """ An abstract base class used to define the notification interface and common functions
    """
    def __init__(self, src_partition, src_offset):
        """ Setup the notification object
            The src_partition and src_offset allow the notification to be linked to the alarm that it came from
        """
        self.src_partition = src_partition
        self.src_offset = src_offset
        # todo clearly more fields needed here.

    def to_json(self):
        """ Return json representation
        """
        return json.dumps(self.__dict__)

    def send(self):
        """ Send the notification
        """
        raise NotImplementedError