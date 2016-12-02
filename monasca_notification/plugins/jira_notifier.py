# (C) Copyright 2016 Hewlett Packard Enterprise Development Company LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from jinja2 import Template
import jira
import json
import urlparse
import yaml

from monasca_notification.plugins.abstract_notifier import AbstractNotifier

"""
   Note:
     This plugin doesn't support multi tenancy. Multi tenancy requires support for
     multiple JIRA server url. JIRA doesn't support OAUTH2 tokens, we may need to get
     the user credentials in query params and store them in monasca DB which we don't want to do.
     That is the reason for not supporting true multitenancy.

    MultiTenancy can be achieved by creating issues in different project for different tenant on
    the same JIRA server.

   notification.address = https://<jira_url>/?project=<project_name>

   Dependency for Jira
       1) Jira plugin requires Jira library. Consumers need to install
         JIRA via pip
       2) (i.e) pip install jira

   Jira Configuration
       1) jira:
            username: username
            password: password

    Sample notification:
       monasca notification-create MyIssuer JIRA https://jira.hpcloud.net/?project=MyProject
       monasca notification-create MyIssuer1 JIRA https://jira.hpcloud.net/?project=MyProject&
                           component=MyComponent

"""


class JiraNotifier(AbstractNotifier):

    _search_query = search_query = "project={} and reporter='{}' and summary ~ '{}'"

    def __init__(self, log):
        self._log = log
        self.jira_fields_format = None

    def config(self, config_dict):
        self._config = {'timeout': 5}
        if not config_dict.get("user") and not config_dict.get("password"):
            message = "Missing user and password settings in JIRA plugin configuration"
            self._log.exception(message)
            raise Exception(message)

        self._config.update(config_dict)
        self.jira_fields_format = self._get_jira_custom_format_fields()

    @property
    def type(self):
        return "jira"

    @property
    def statsd_name(self):
        return 'jira_notifier'

    def _get_jira_custom_format_fields(self):
        jira_fields_format = None

        if (not self.jira_fields_format and self._config.get("custom_formatter")):
            try:
                with open(self._config.get("custom_formatter")) as f:
                    jira_fields_format = yaml.load(f)
            except Exception:
                self._log.exception("Unable to read custom_formatter file. Check file location")
                raise
            # Remove the top element
            jira_fields_format = jira_fields_format["jira_format"]

        return jira_fields_format

    def _build_custom_jira_message(self, notification, jira_fields_format):

        jira_fields = {}

        # Templatize the message object
        jira_field_summary_field = jira_fields_format.get("summary", None)
        if jira_field_summary_field:
            template = Template(jira_field_summary_field)
            jira_fields["summary"] = template.render(notification=notification)

        jira_field_comments_field = jira_fields_format.get("comments", None)
        if jira_field_comments_field:
            template = Template(jira_field_comments_field)
            jira_fields["comments"] = template.render(notification=notification)

        jira_field_description_field = jira_fields_format.get("description", None)
        if jira_field_description_field:
            template = Template(jira_field_description_field)
            jira_fields["description"] = template.render(notification=notification)

        return jira_fields

    def _build_default_jira_message(self, notification):
        """Builds jira message body
        """
        body = {'alarm_id': notification.alarm_id,
                'alarm_definition_id': notification.raw_alarm['alarmDefinitionId'],
                'alarm_name': notification.alarm_name,
                'alarm_description': notification.raw_alarm['alarmDescription'],
                'alarm_timestamp': notification.alarm_timestamp,
                'state': notification.state,
                'old_state': notification.raw_alarm['oldState'],
                'message': notification.message,
                'tenant_id': notification.tenant_id,
                'metrics': notification.metrics}

        jira_fields = {}
        summary_format_string = "Monasca alarm for alarm_defintion {0} status changed to {1} for the alarm_id {2}"
        jira_fields["summary"] = summary_format_string.format(notification.alarm_name,
                                                              notification.state,
                                                              notification.alarm_id)
        jira_fields["comments"] = "{code}%s{code}" % (json.dumps(body, indent=3))

        return jira_fields

    def _build_jira_message(self, notification):
        if self._config.get("custom_formatter"):
            return self._build_custom_jira_message(notification, self.jira_fields_format)

        return self._build_default_jira_message(notification)

    def send_notification(self, notification):
        """Creates or Updates an issue in Jira
        """

        jira_fields = self._build_jira_message(notification)

        parsed_url = urlparse.urlsplit(notification.address)
        query_params = urlparse.parse_qs(parsed_url.query)
        # URL without query params
        url = urlparse.urljoin(notification.address, urlparse.urlparse(notification.address).path)

        jira_fields["project"] = query_params["project"][0]
        if query_params.get("component"):
            jira_fields["component"] = query_params["component"][0]

        auth = (self._config["user"], self._config["password"])
        proxyDict = None
        if (self._config.get("proxy")):
            proxyDict = {"https": self._config.get("proxy")}

        try:
            jira_obj = jira.JIRA(url, basic_auth=auth, proxies=proxyDict)

            self.jira_workflow(jira_fields, jira_obj, notification)
        except Exception:
            self._log.exception("Error creating issue in Jira at URL {}".format(url))
            return False

        return True

    def jira_workflow(self, jira_fields, jira_obj, notification):
        """How does Jira plugin work?
           1) Check whether the issue with same description exists?
           2) If issue exists, and if it is closed state, open it
           3) if the issue doesn't exist, then create the issue
           4) Add current alarm details in comments
        """

        issue_dict = {'project': {'key': jira_fields["project"]},
                      'summary': jira_fields["summary"],
                      'description': 'Monasca alaram',
                      'issuetype': {'name': 'Bug'}, }

        # If the JIRA workflow is created with mandatory components
        if jira_fields.get("component"):
            issue_dict["components"] = [{"name": jira_fields.get("component")}]

        search_term = self._search_query.format(issue_dict["project"]["key"],
                                                self._config["user"], notification.alarm_id)
        issue_list = jira_obj.search_issues(search_term)
        if not issue_list:
            self._log.debug("Creating an issue with the data {}".format(issue_dict))
            issue = jira_obj.create_issue(fields=issue_dict)
        else:
            issue = issue_list[0]
            self._log.debug("Found an existing issue {} for this notification".format(issue))
            current_state = issue.fields.status.name
            if current_state.lower() in ["resolved", "closed"]:
                # Open the the issue
                transitions = jira_obj.transitions(issue)
                allowed_transistions = [(t['id'], t['name']) for t in transitions if "reopen" in t['name'].lower()]
                if allowed_transistions:
                    # Reopen the issue
                    jira_obj.transition_issue(issue, allowed_transistions[0][0])

        jira_comment_message = jira_fields.get("comments")
        if jira_comment_message:
            jira_obj.add_comment(issue, jira_comment_message)
