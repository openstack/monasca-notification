ARG DOCKER_IMAGE=monasca/notification
ARG APP_REPO=https://git.openstack.org/openstack/monasca-notification

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
    KAFKA_URI=kafka:9092 \
    KAFKA_WAIT_FOR_TOPICS=retry-notifications,alarm-state-transitions,alarm-notifications,60-seconds-notifications \
    ZOOKEEPER_URL=zookeeper:2181 \
    ALARM_PROCESSORS=2 \
    NOTIFICATION_PROCESSORS=2 \
    RETRY_INTERVAL=30 \
    RETRY_MAX_ATTEMPTS=5 \
    MYSQL_DB_HOST=mysql \
    MYSQL_DB_PORT=3306 \
    MYSQL_DB_USERNAME=notification \
    MYSQL_DB_PASSWORD=password \
    MYSQL_DB_DATABASE=mon \
    STATSD_HOST=monasca-statsd \
    STATSD_PORT=8125 \
    STAY_ALIVE_ON_FAILURE="false"

# Copy all neccessary files to proper locations.
COPY notification.yaml.j2 /etc/monasca/

# Implement start script in `start.sh` file.
CMD ["/start.sh"]