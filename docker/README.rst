=====================================
Docker image for Monasca notification
=====================================
The Monasca notification image is based on the monasca-base image.


Building monasca-base image
===========================
See https://opendev.org/openstack/monasca-common/src/branch/master/docker/README.rst


Building Monasca notification image
===================================

Example:
  $ ./build_image.sh <repository_version> <upper_constrains_branch> <common_version>

Everything after ``./build_image.sh`` is optional and by default configured
to get versions from ``Dockerfile``. ``./build_image.sh`` also contain more
detailed build description.

Environment variables
~~~~~~~~~~~~~~~~~~~~~
============================== ================= ================================================
Variable                       Default           Description
============================== ================= ================================================
LOG_LEVEL                      WARNING           Log level for main logging
LOG_LEVEL_KAFKA                WARNING           Log level for Kafka
LOG_LEVEL_PLUGINS              WARNING           Log level for plugins (email, webhook, etc)
KAFKA_URI                      kafka:9092        The host and port for kafka
KAFKA_LEGACY_CLIENT_ENABLED    false             Enable legacy Kafka client
ZOOKEEPER_URL                  zookeeper:2181    URL to Zookeeper
NOTIFICATION_PROCESSORS        2                 Number of notification processing threads
RETRY_INTERVAL                 30                Retry interval in seconds
RETRY_MAX_ATTEMPTS             5                 Max number of notification retries
STATSD_ENABLED                 true              Monasca agent StatsD enable or disable
STATSD_HOST                    monasca-statsd    Monasca agent StatsD host for self-monitoring
STATSD_PORT                    8125              Monasca agent StatsD port for self-monitoring
NF_PLUGINS                     <not set>         See below "Notification Plugins"
MYSQL_HOST                     mysql             The host for MySQL
MYSQL_PORT                     3306              The port for MySQL
MYSQL_USER                     notification      The MySQL username
MYSQL_PASSWORD                 password          The MySQL password
MYSQL_DB                       mon               The MySQL database name
STAY_ALIVE_ON_FAILURE          false             If true, container runs 2 hours even start fails
============================== ================= ================================================

Wait scripts environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
======================== ========================== ==========================================
Variable                 Default                    Description
======================== ========================== ==========================================
KAFKA_URI                kafka:9092                 URI to Apache Kafka
KAFKA_WAIT_FOR_TOPICS    retry-notifications,       The topics where metric-api streams
                         alarm-state-transitions,   the metric messages and alarm-states
                         alarm-notifications,
                         60-seconds-notifications
KAFKA_WAIT_RETRIES       24                         Number of kafka connect attempts
KAFKA_WAIT_DELAY         5                          Seconds to wait between attempts
MYSQL_HOST               mysql                      The host for MySQL
MYSQL_PORT               3306                       The port for MySQL
MYSQL_USER               notification               The MySQL username
MYSQL_PASSWORD           password                   The MySQL password
MYSQL_DB                 mon                        The MySQL database name
MYSQL_WAIT_RETRIES       24                         Number of MySQL connection attempts
MYSQL_WAIT_DELAY         5                          Seconds to wait between attempts
======================== ========================== ==========================================

Scripts
~~~~~~~
start.sh
  In this starting script provide all steps that lead to the proper service
  start. Including usage of wait scripts and templating of configuration
  files. You also could provide the ability to allow running container after
  service died for easier debugging.

health_check.py
  This file will be used for checking the status of the application.

Notification Plugins
--------------------
A list of notification plugins can be provided by setting NF_PLUGINS to a comma-separated list of plugin names
e.g. email,webhook,hipchat.


Email
-----
Name: email

This plugin sends email notifications when an alarm is triggered.

Options:
 * NF_EMAIL_SERVER: SMTP server address, required, unset by default
 * NF_EMAIL_PORT: SMTP server port, default: 25
 * NF_EMAIL_USER: SMTP username, optional, unset by default
 * NF_EMAIL_PASSWORD, SMTP password, required only if NF_EMAIL_USER is set
 * NF_EMAIL_FROM_ADDR: "from" field for emails sent, e.g. "Name" <name@example.com>
 * NF_EMAIL_GRAFANA_URL: grafana url, required, unset by default


Webhook
-------
Name: webhook

This plugin calls a webhook when an alarm is triggered. Specific parameters, like the URL to load, are part of the notification rather than the notification plugin.

Options:
 * NF_WEBHOOK_TIMEOUT: timeout in seconds, default: 5


PagerDuty
---------
Name: pagerduty

Creates a PagerDuty event for the given alarm.

Options:
 * NF_PAGERDUTY_TIMEOUT: timeout in seconds, default: 5
 * NF_PAGERDUTY_URL: PagerDuty Event API endpoint, defaults to official URL


Slack
-----
Name: slack

Notifies via a Slack message.

Options:
 * NF_SLACK_TIMEOUT: timeout in seconds, default: 5
 * NF_SLACK_CERTS: path to SSL certs, default: system certs
 * NF_SLACK_INSECURE: if true, don't verify SSL
 * NF_SLACK_PROXY: if set, use the given HTTP(S) proxy server to send notifications


Provide Configuration templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* monasca-notification.conf.j2
* notification-logging.conf.j2

Links
~~~~~
https://opendev.org/openstack/monasca-notification/src/branch/master/README.rst
