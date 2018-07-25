=====================================
Docker image for Monasca notification
=====================================
The Monasca notification image is based on the monasca-base image.


Building monasca-base image
===========================
See https://github.com/openstack/monasca-common/tree/master/docker/README.rst


Building Monasca notification image
===================================

Example:
  $ ./build_image.sh <repository_version> <upper_constains_branch> <common_version>

Requirements from monasca-base image
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
health_check.py
  This file will be used for checking the status of the Monasca persister
  application.


Scripts
~~~~~~~
start.sh
  In this starting script provide all steps that lead to the proper service
  start. Including usage of wait scripts and templating of configuration
  files. You also could provide the ability to allow running container after
  service died for easier debugging.

build_image.sh
  Please read detailed build description inside the script.


Environment variables
~~~~~~~~~~~~~~~~~~~~~
============================== ======================================================================================== ================================================
Variable                       Default                                                                                  Description
============================== ======================================================================================== ================================================
KAFKA_URI                      kafka:9092                                                                               The host and port for kafka
KAFKA_WAIT_FOR_TOPICS          retry-notifications,alarm-state-transitions,alarm-notifications,60-seconds-notifications Topics to wait on at startup
KAFKA_WAIT_RETRIES 	           24                                                                                       Number of kafka connect attempts
KAFKA_WAIT_DELAY               5                                                                                        Seconds to wait between attempts
ZOOKEEPER_URL 	               zookeeper:2181 	                                                                        URL to Zookeeper
ALARM_PROCESSORS               2 	                                                                                    Number of alarm processing threads
NOTIFICATION_PROCESSORS        2 	                                                                                    Number of notification processing threads
RETRY_INTERVAL 	               30 	                                                                                    Retry interval in seconds
RETRY_MAX_ATTEMPTS 	           5 	                                                                                    Max number of notification retries
LOG_LEVEL 	                   WARN 	                                                                                Logging level
STATSD_HOST                    monasca-statsd 	                                                                        Monasca agent StatsD host for self-monitoring
STATSD_PORT                    8125     	                                                                            Monasca agent StatsD port for self-monitoring
NF_PLUGINS 	                   <not set>  	                                                                            See below "Notification Plugins"
MYSQL_DB_HOST                  mysql                                                                                    The host for MySQL
MYSQL_DB_PORT                  3306                                                                                     The port for MySQL
MYSQL_DB_USERNAME              notification                                                                             The MySQL username
MYSQL_DB_PASSWORD              password                                                                                 The MySQL password
MYSQL_DB_DATABASE              mon                                                                                      The MySQL database name
STAY_ALIVE_ON_FAILURE          false                                                                                    If true, container runs 2 hours even start fails
============================== ======================================================================================== ================================================


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


HipChat
-------
Name: hipchat

Notifies via a HipChat message to some room. Authentication and destination details are configured with the notification.

Options:
 * NF_HIPCHAT_TIMEOUT: timeout in seconds, default: 5
 * NF_HIPCHAT_SSL_CERTS: path to SSL certs, default: system certs
 * NF_HIPCHAT_INSECURE: if true, don't verify SSL
 * NF_HIPCHAT_PROXY: if set, use the given HTTP(S) proxy server to send notifications


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
* notification.yaml.j2


Links
~~~~~
https://github.com/openstack/monasca-notification/blob/master/README.rst
