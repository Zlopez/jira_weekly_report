"""Script for creating reports from JIRA project."""
import logging
import tomllib
import re

import arrow
import click

from jira_weekly_report.jira_wrapper import JIRA


log = logging.getLogger(__name__)
# This HTTP regex was obtained from
# https://stackoverflow.com/questions/3809401/what-is-a-good-regular-expression-to-match-a-url
HTTP_REGEX = re.compile(r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)")


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Will print verbose messages.")
def cli(verbose: bool):
    """
    Click main function.
    """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    log.addHandler(ch)
    if verbose:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)


@cli.command()
@click.option("--days-ago", default=7, help="How many days ago to look for open issues.")
@click.option("--till", default=None, help="Show results till this date. Expects date in YYYY-MM-DD format (2021-12-20).")
@click.option("--config", default="config.toml", help="Path to configuration file.")
def generate_report(days_ago: int, till: str, config: str):
    """
    Get open issues from the repository and print their count.

    Params:
      days_ago: How many days ago to look for the issues
      till: Limit results to the day set by this argument. Default None will be replaced by `arrow.utcnow()`.
      config: Configuration file to use
      output: Output HTML file to write to.
    """
    if till:
        till = arrow.get(till, "YYYY-MM-DD")
    else:
        till = arrow.utcnow()
    since_arg = till.shift(days=-days_ago)

    with open(config, "rb") as config_file:
        config_dict = tomllib.load(config_file)

    jira = JIRA(
        url=config_dict["General"]["jira_instance"],
        token=config_dict["General"]["jira_token"],
        project=config_dict["General"]["jira_project"],
    )

    jira_closed_states = config_dict["General"]["jira_closed_states"]
    jira_open_states = config_dict["General"]["jira_open_states"]
    jira_components = config_dict["General"]["jira_components"]

    closed_issues = jira.get_issues(jira_components, jira_closed_states, since_arg, till)

    open_issues = jira.get_issues(jira_components, jira_open_states)

    log.debug("Retrieved %s closed issues", len(closed_issues))
    log.debug("Retrieved %s open issues", len(open_issues))

    url_field = config_dict["General"]["url_field"]

    jira_closed_issues = process_issues(closed_issues, False, url_field)
    jira_open_issues = process_issues(open_issues, True, url_field)

    jira_issues = {}

    for repo in jira_open_issues:
        if repo not in jira_issues:
            jira_issues[repo] = {}
        jira_issues[repo]["open"] = jira_open_issues[repo]
    for repo in jira_closed_issues:
        if repo not in jira_issues:
            jira_issues[repo] = {}
        jira_issues[repo]["closed"] = jira_closed_issues[repo]

    for repo in jira_issues:
        log.debug(
            "Retrieved %s issues from repo %s",
            (len(jira_issues[repo]["open"]) if "open" in jira_issues[repo] else 0) +
            (len(jira_issues[repo]["closed"]) if "closed" in jira_issues[repo] else 0),
            repo
        )

    # Prepare the report for print
    output = ""
    for repo in jira_issues:
        output = output + f"<h1>{repo}</h1>\n"
        output = output + "<ul>\n"
        if "open" in jira_issues[repo]:
            output = output + "\t<li>Open:</li>\n"
            output = output + "\t<ul>\n"
            for issue in jira_issues[repo]["open"]:
                output = output + f"\t\t<li><a href=\"{jira_issues[repo]['open'][issue]}\">{issue}</a>\n"
            output = output + "\t</ul>\n"
        if "closed" in jira_issues[repo]:
            output = output + "\t<li>Closed:</li>\n"
            output = output + "\t<ul>\n"
            for issue in jira_issues[repo]["closed"]:
                output = output + f"\t\t<li><a href=\"{jira_issues[repo]['closed'][issue]}\">{issue}</a>\n"
            output = output + "\t</ul>\n"
        output = output + "</ul>\n\n"
    print(output)


def process_issues(issues: list, open: bool, url_field: str) -> dict:
    """
    Process issues retrieved from JIRA and return dictionary we can work with.

    Params:
      issues: List of issues to process
      open: Boolean to switch between open and closed issue processing
      url_field: Field to get url from

    Returns:
      Processed dictionary with only the values we care about
    """
    jira_issues = {}

    for issue in issues:
        url = ""
        # Get the link to ticket from field
        if url_field:
            try:
                if issue.get_field(url_field):
                    result = re.match(HTTP_REGEX, issue.get_field(url_field))
                    if result:
                        url = result[0]
                        repo = "/".join(url.split("/")[:-2])
                        # Just get the repository from the url
                        # Expecting url in format https://<forge>/<org>/<repo>/issue(s)/<issue_nr>
                        if repo not in jira_issues:
                            jira_issues[repo] = {}
                        jira_issues[repo][issue.fields.summary.strip()] = url
            except AttributeError:
                log.debug("Couldn't retrieve the url from %s", issue.fields.summary)
                pass
        # Link field is not set, let's use the ticket URL instead
        else:
            url = issue.permalink()
            repo = "/".join(url.split("/")[:-2])
            # Just get the repository from the url
            # Expecting url in format https://<forge>/<org>/<repo>/issue(s)/<issue_nr>
            if repo not in jira_issues:
                jira_issues[repo] = {}
            jira_issues[repo][issue.fields.summary.strip()] = url

    return jira_issues
