# (C) Copyright 2016 Hewlett Packard Enterprise Development Company LP
# Copyright 2017 Fujitsu LIMITED
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
from six.moves import urllib
import ujson as json
import yaml

from debtcollector import removals
from oslo_config import cfg

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
            user: username
            password: password

    Sample notification:
       monasca notification-create MyIssuer JIRA https://jira.hpcloud.net/?project=MyProject
       monasca notification-create MyIssuer1 JIRA https://jira.hpcloud.net/?project=MyProject&
                           component=MyComponent

"""


CONF = cfg.CONF


def register_opts(conf):
    gr = cfg.OptGroup(name='%s_notifier' % JiraNotifier.type)
    opts = [
        cfg.IntOpt(name='timeout', default=5, min=1),
        cfg.StrOpt(name='user', required=False),
        cfg.StrOpt(name='password', required=False, secret=True),
        cfg.StrOpt(name='custom_formatter', default=None),
        cfg.StrOpt(name='proxy', default=None)
    ]

    conf.register_group(gr)
    conf.register_opts(opts, group=gr)


class JiraNotifier(AbstractNotifier):

    type = 'jira'
    _search_query = search_query = "project={} and reporter='{}' and summary ~ '{}'"

    def __init__(self, log):
        super(JiraNotifier, self).__init__()
        self._log = log
        self.jira_fields_format = None

    @removals.remove(
        message='Configuration of notifier is available through oslo.cfg',
        version='1.9.0',
        removal_version='3.0.0'
    )
    def config(self, config_dict):
        pass

    @property
    def statsd_name(self):
        return 'jira_notifier'

    def _get_jira_custom_format_fields(self):
        jira_fields_format = None

        formatter = CONF.jira_notifier.custom_formatter
        if not self.jira_fields_format and formatter:
            try:
                with open(formatter, 'r') as f:
                    jira_fields_format = yaml.safe_load(f)
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
        summary_format_string = ("Monasca alarm for alarm_defintion {0} status changed to {1} "
                                 "for the alarm_id {2}")
        jira_fields["summary"] = summary_format_string.format(notification.alarm_name,
                                                              notification.state,
                                                              notification.alarm_id)
        jira_fields["comments"] = "{code}%s{code}" % (json.dumps(body, indent=3))
        jira_fields["description"] = 'Monasca alarm'

        return jira_fields

    def _build_jira_message(self, notification):
        formatter = CONF.jira_notifier.custom_formatter
        if formatter:
            return self._build_custom_jira_message(notification,
                                                   self._get_jira_custom_format_fields())

        return self._build_default_jira_message(notification)

    def send_notification(self, notification):
        """Creates or Updates an issue in Jira
        """

        jira_fields = self._build_jira_message(notification)

        parsed_url = urllib.parse.urlsplit(notification.address)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        # URL without query params
        url = urllib.parse.urljoin(
            notification.address,
            urllib.parse.urlparse(
                notification.address).path)

        jira_fields["project"] = query_params["project"][0]
        if query_params.get("component"):
            jira_fields["component"] = query_params["component"][0]

        auth = (
            CONF.jira_notifier.user,
            CONF.jira_notifier.password
        )
        proxy = CONF.jira_notifier.proxy
        proxy_dict = None
        if proxy is not None:
            proxy_dict = {"https": proxy}

        try:
            jira_obj = jira.JIRA(url, basic_auth=auth, proxies=proxy_dict)

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
                      'description': jira_fields["description"],
                      'issuetype': {'name': 'Bug'}, }

        # If the JIRA workflow is created with mandatory components
        if jira_fields.get("component"):
            issue_dict["components"] = [{"name": jira_fields.get("component")}]

        search_term = self._search_query.format(issue_dict["project"]["key"],
                                                CONF.jira_notifier.user,
                                                notification.alarm_id)
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
                allowed_transistions = [(t['id'], t['name'])
                                        for t in transitions if "reopen" in t['name'].lower()]
                if allowed_transistions:
                    # Reopen the issue
                    jira_obj.transition_issue(issue, allowed_transistions[0][0])

        jira_comment_message = jira_fields.get("comments")
        if jira_comment_message:
            jira_obj.add_comment(issue, jira_comment_message)
