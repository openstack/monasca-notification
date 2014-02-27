
class KafkaConsumer(object):
    pass

# Todo I need to intelligently handle partitions so that multiple notification engines can run
# I need to make sure to not advance the marker in kafka so that is only done by the SentNotificationProcessor