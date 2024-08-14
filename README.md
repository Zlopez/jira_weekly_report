# jira_weekly_report
Script for generating reports from JIRA project

## Installation

1. Clone the repository using git

   `git clone https://github.com/Zlopez/jira_weekly_report.git`

   `cd jira_weekly_report`

2. Install poetry

   On Fedora:

   `dnf install poetry`

   From PyPI:

   `pip install poetry`

3. Install the script using poetry

   `poetry install`

## Configuration

`jira_weekly_report` needs configuration file provided by the user. The example is available
[here](https://github.com/Zlopez/jira_weekly_report/blob/main/config.example.toml).

To get JIRA API key look at
[official documentation](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/).

## Usage

All the commands needs to be run with `poetry run`. Example `poetry run jira_weekly_report --help`

* Print help

  `jira_weekly_report --help`

* Print `generate-report` command help

  `jira_weekly_report generate-report --help`

* Verbose mode

  `jira_weekly_report -v <command>`

* Generate report for last 7 days

  `jira_weekly_report generate-report --config config.toml`

* Generate report for week from 12.08.2024 -> 16.08.2024

  `jira_weekly_report generate-report --till 2024-08-16 --config config.toml --days_ago 7`
