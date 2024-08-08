"""
Wrapper around the JIRA API.

See https://developer.atlassian.com/server/jira/platform/rest-apis/
"""

import logging
from typing import cast

import arrow
import jira

# Help out mypy, it trips over directly using jira.resources.Issue.
from jira import Issue

log = logging.getLogger(__name__)


class JIRA:
    """
    Class for interacting with JIRA API.

    Attributes:
      jira: Instance of the jira.JIRA object
      project: Project to work with
    """

    jira: jira.client.JIRA
    project: str

    def __init__(
        self,
        url: str,
        token: str,
        project: str,
    ):
        """
        Class constructor.

        Params:
          url: URL to JIRA server
          token: Token to use for authentication
          project: Project to work with
        """
        self.jira = jira.client.JIRA(url, token_auth=token)
        self.project = project

    def get_issues(
            self,
            labels: list[str],
            components: list[str],
            states: list[str],
            updated_since: arrow.Arrow = None,
            updated_till: arrow.Arrow = None,
    ) -> list[Issue]:
        """
        Retrieve issues with provided labels in provided states.
        This could be limited by dates.

        Params:
          labels: Label to retrieve the issues by.
          components: Components to retrieve the issues by.
          states: List of states to retrieve
          updated_since: Arrow object containing date we want tickets from.
                         Default: None
          updated_till: Arrow object containing date we want tickets till.
                        Default: None

        Returns:
          List of issues.
        """
        states_comma = ', '.join("'" + state + "'" for state in states)
        search_query = (
            "project = "
            + self.project
            + " AND status in (" + states_comma + ")"
        )

        if labels:
            labels_comma = ', '.join("'" + label + "'" for label in labels)
            search_query = search_query + (
                ' AND labels in ('
                + labels_comma
                + ')'
            )

        if components:
            components_comma = ', '.join("'" + component + "'" for component in components)
            search_query = search_query + (
                ' AND component in ('
                + components_comma
                + ')'
            )

        if updated_since and updated_till:
            search_query = search_query + (
                " AND updatedDate >= " + updated_since.format("YYYY-MM-DD")
                + " AND updatedDate <= " + updated_till.format("YYYY-MM-DD")
            )
        issues = cast(
            jira.client.ResultList[Issue],
            self.jira.search_issues(
                search_query,
                maxResults=0,
            ),
        )
        return issues
