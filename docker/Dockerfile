ARG DOCKER_IMAGE=monasca/notification
ARG APP_REPO=https://review.opendev.org/openstack/monasca-notification
# Branch, tag or git hash to build from.
ARG REPO_VERSION=master
ARG CONSTRAINTS_BRANCH=master
ARG COMMON_VERSION=master
# Extra Python3 dependencies.
ARG EXTRA_DEPS="netaddr gevent==1.3.5 greenlet"
# Always start from `monasca-base` image and use specific tag of it.
ARG BASE_TAG=master
FROM monasca/base:$BASE_TAG
# Environment variables used for our service or wait scripts.
ENV \
    LOG_LEVEL=WARNING \
    LOG_LEVEL_KAFKA=WARNING \
    LOG_LEVEL_PLUGINS=WARNING \
    KAFKA_URI=kafka:9092 \
    KAFKA_LEGACY_CLIENT_ENABLED=false \
    KAFKA_WAIT_FOR_TOPICS=retry-notifications,alarm-state-transitions,alarm-notifications,60-seconds-notifications \
    ZOOKEEPER_URL=zookeeper:2181 \
    NOTIFICATION_PROCESSORS=2 \
    RETRY_INTERVAL=30 \
    RETRY_MAX_ATTEMPTS=5 \
    MYSQL_HOST=mysql \
    MYSQL_PORT=3306 \
    MYSQL_USER=notification \
    MYSQL_PASSWORD=password \
    MYSQL_DB=mon \
    STATSD_ENABLED=true \
    STATSD_HOST=monasca-statsd \
    STATSD_PORT=8125 \
    STAY_ALIVE_ON_FAILURE="false"
# Copy all necessary files to proper locations.
COPY monasca-notification.conf.j2 notification-logging.conf.j2 /etc/monasca/
# Implement start script in `start.sh` file.
CMD ["/start.sh"]
