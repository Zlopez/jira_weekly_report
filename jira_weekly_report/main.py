"""Script for creating reports from JIRA project."""

import logging
import tomllib
import re
from typing import Dict, List, Tuple

import arrow
import click
from PIL import Image, ImageDraw, ImageFont, ImageOps

from jira_weekly_report.jira_wrapper import JIRA


log = logging.getLogger(__name__)
# This HTTP regex was obtained from
# https://stackoverflow.com/questions/3809401/what-is-a-good-regular-expression-to-match-a-url
HTTP_REGEX = re.compile(
    r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
)


def create_image_report(jira_issues: Dict, output_path: str, categories: list):
    """
    Create an image report from JIRA issues using header, content, and footer templates.
    Args:
        jira_issues: Dictionary containing categorized JIRA issues
        output_path: Path where to save the image
        categories: List of (display_name, pattern) tuples, in the order to display columns
    """
    from PIL import ImageOps

    log = logging.getLogger(__name__)
    log.debug("Starting create_image_report")
    # Load template images
    header_img = Image.open("img/header_template.png").convert("RGB")
    content_img = Image.open("img/content_template.png").convert("RGB")
    footer_img = Image.open("img/footer_template.png").convert("RGB")

    width = header_img.width
    header_height = header_img.height
    content_template_height = content_img.height
    footer_height = footer_img.height

    # Increased font size
    try:
        text_font_size = 32
        header_font_size = text_font_size * 3
        header_font = ImageFont.truetype("DejaVuSans-Bold", header_font_size)
        text_font = ImageFont.truetype("DejaVuSans", text_font_size)
    except IOError:
        header_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        header_font_size = 48  # fallback
        text_font_size = 16

    # Increased column width and spacing
    num_cols = len(categories)
    margin = 60
    col_spacing = 70
    col_width = (width - 2 * margin - (num_cols - 1) * col_spacing) // num_cols
    col_y0 = 0  # relative to content_img
    columns = []
    for i in range(num_cols):
        x0 = margin + i * (col_width + col_spacing)
        x1 = x0 + col_width
        columns.append((x0, col_y0, x1))

    # Calculate max number of closed issues in any column
    items_per_col = [
        len(jira_issues.get(pattern, {}).get("closed", {})) for _, pattern in categories
    ]
    max_items = max(items_per_col) if items_per_col else 0
    content_height_per_item = 60  # adjust for larger font
    top_padding = 40
    bottom_padding = 40
    content_height = top_padding + max_items * content_height_per_item + bottom_padding
    content_height = max(content_height, content_template_height)

    # Stretch content_img to the new height
    content_img_resized = content_img.resize((width, content_height))

    # Compose the final image
    total_height = header_height + content_height + footer_height
    final_img = Image.new("RGB", (width, total_height), (255, 255, 255))
    final_img.paste(header_img, (0, 0))
    final_img.paste(content_img_resized, (0, header_height))
    final_img.paste(footer_img, (0, header_height + content_height))

    draw = ImageDraw.Draw(final_img)

    # Draw issues in the content area
    for idx, (display_name, pattern) in enumerate(categories):
        box = columns[idx]
        issues = jira_issues.get(pattern, {}).get("closed", {})
        log.debug(
            f"Processing category '{display_name}' (pattern: '{pattern}') with {len(issues)} closed issues."
        )
        # Draw category header (display_name) with much larger font and higher position
        header_bbox = draw.textbbox((0, 0), display_name, font=header_font)
        header_width = header_bbox[2] - header_bbox[0]
        # Position: one header_font_size above previous
        header_y = header_height + 20 - header_font_size
        draw.text(
            (box[0] + (col_width - header_width) // 2, header_y),
            display_name,
            font=header_font,
            fill=(255, 255, 255),
        )
        y_offset = header_height + top_padding + 80  # 80px below category header
        for summary, data in issues.items():
            issue_text = f"[{data['key']}] {summary}"
            log.debug(
                f"Drawing issue {data['key']}: '{summary}' at x={box[0]+30}, y={y_offset}"
            )
            # Wrap text if too long
            words = issue_text.split()
            lines = []
            current_line = []
            for word in words:
                test_line = " ".join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=text_font)
                if bbox[2] - bbox[0] < (box[2] - box[0] - 60):
                    current_line.append(word)
                else:
                    lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
            for line in lines:
                draw.text(
                    (box[0] + 30, y_offset), line, font=text_font, fill=(255, 255, 255)
                )
                y_offset += 50
            y_offset += 20

    log.debug(f"Saving image report to {output_path}")
    final_img.save(output_path)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Will print verbose messages.")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Set the logging level.",
)
def cli(verbose: bool, log_level: str):
    """
    Click main function.
    """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    log.addHandler(ch)

    # Set log level based on the option
    log.setLevel(getattr(logging, log_level))

    # If verbose flag is set, override to DEBUG level
    if verbose:
        log.setLevel(logging.DEBUG)


@cli.command()
@click.option(
    "--days-ago", default=7, help="How many days ago to look for open issues."
)
@click.option(
    "--till",
    default=None,
    help="Show results till this date. Expects date in YYYY-MM-DD format (2021-12-20).",
)
@click.option("--config", default="config.toml", help="Path to configuration file.")
@click.option(
    "--html-output", default="report.html", help="Output HTML file to write to."
)
@click.option(
    "--image-output", default="report.png", help="Output image file to write to."
)
def generate_report(
    days_ago: int, till: str, config: str, html_output: str, image_output: str
):
    """
    Get open issues from the repository and generate HTML and image reports.

    Params:
      days_ago: How many days ago to look for the issues
      till: Limit results to the day set by this argument. Default None will be replaced by `arrow.utcnow()`.
      config: Configuration file to use
      html_output: Output HTML file to write to
      image_output: Output image file to write to
    """
    if till:
        till = arrow.get(till, "YYYY-MM-DD")
    else:
        till = arrow.utcnow()
    since_arg = till.shift(days=-days_ago)

    log.info(
        "Generating report for period %s to %s",
        since_arg.format("YYYY-MM-DD"),
        till.format("YYYY-MM-DD"),
    )

    with open(config, "rb") as config_file:
        config_dict = tomllib.load(config_file)
        log.info("Loaded configuration from %s", config)

    jira = JIRA(
        url=config_dict["General"]["jira_instance"],
        token=config_dict["General"]["jira_token"],
        project=config_dict["General"]["jira_project"],
    )

    jira_closed_states = config_dict["General"]["jira_closed_states"]
    jira_open_states = config_dict["General"]["jira_open_states"]
    jira_labels = config_dict["General"]["jira_labels"]
    jira_components = config_dict["General"]["jira_components"]

    log.info("Retrieving closed issues with states: %s", ", ".join(jira_closed_states))
    closed_issues = jira.get_issues(
        jira_labels, jira_components, jira_closed_states, since_arg, till
    )
    log.info("Retrieved %d closed issues", len(closed_issues))

    log.info("Retrieving open issues with states: %s", ", ".join(jira_open_states))
    open_issues = jira.get_issues(jira_labels, jira_components, jira_open_states)
    log.info("Retrieved %d open issues", len(open_issues))

    category_labels = config_dict["categories"].values()
    url_field = config_dict["General"]["url_field"]

    log.info("Processing closed issues")
    jira_closed_issues = process_issues(
        closed_issues, False, category_labels, url_field
    )
    log.info("Processing open issues")
    jira_open_issues = process_issues(open_issues, True, category_labels, url_field)

    jira_issues = {}
    issue_count = 0

    for label in jira_open_issues:
        if label not in jira_issues:
            jira_issues[label] = {}
        jira_issues[label]["open"] = jira_open_issues[label]
        issue_count += len(jira_issues[label]["open"])
        log.info(
            "Category '%s': %d open issues", label, len(jira_issues[label]["open"])
        )

    for label in jira_closed_issues:
        if label not in jira_issues:
            jira_issues[label] = {}
        jira_issues[label]["closed"] = jira_closed_issues[label]
        issue_count += len(jira_issues[label]["closed"])
        log.info(
            "Category '%s': %d closed issues", label, len(jira_issues[label]["closed"])
        )

    log.info("Total issues processed: %d", issue_count)

    # Generate HTML report
    log.info("Generating HTML report to %s", html_output)
    html_output_content = ""
    jira_instance = config_dict["General"]["jira_instance"]
    for label in jira_issues:
        html_output_content = html_output_content + f"<h1>{label}</h1>\n"
        html_output_content = html_output_content + "<ul>\n"
        if "open" in jira_issues[label]:
            html_output_content = html_output_content + "\t<li>Open:</li>\n"
            html_output_content = html_output_content + "\t<ul>\n"
            for issue in jira_issues[label]["open"]:
                issue_data = jira_issues[label]["open"][issue]
                jira_url = f"{jira_instance}/browse/{issue_data['key']}"
                html_output_content = (
                    html_output_content
                    + f"\t\t<li><a href=\"{jira_url}\">{issue_data['key']}</a> - <a href=\"{issue_data['url']}\">{issue}</a></li>\n"
                )
            html_output_content = html_output_content + "\t</ul>\n"
        if "closed" in jira_issues[label]:
            html_output_content = html_output_content + "\t<li>Closed:</li>\n"
            html_output_content = html_output_content + "\t<ul>\n"
            for issue in jira_issues[label]["closed"]:
                issue_data = jira_issues[label]["closed"][issue]
                jira_url = f"{jira_instance}/browse/{issue_data['key']}"
                html_output_content = (
                    html_output_content
                    + f"\t\t<li><a href=\"{jira_url}\">{issue_data['key']}</a> - <a href=\"{issue_data['url']}\">{issue}</a></li>\n"
                )
            html_output_content = html_output_content + "\t</ul>\n"
        html_output_content = html_output_content + "</ul>\n\n"

    with open(html_output, "w") as f:
        f.write(html_output_content)
    log.info("HTML report generated successfully")

    # Generate image report
    log.info("Generating image report to %s", image_output)
    create_image_report(jira_issues, image_output, category_labels)
    log.info("Image report generated successfully")


def process_issues(
    issues: list, open: bool, category_labels: list, url_field: str
) -> dict:
    """
    Process issues retrieved from JIRA and return dictionary we can work with.

    Params:
      issues: List of issues to process
      open: Boolean to switch between open and closed issue processing
      category_labels: Labels (regex patterns) to use for categorizing issues
      url_field: Field to get url from

    Returns:
      Processed dictionary with only the values we care about
    """
    import re

    no_label = "Uncategorized"

    # Compile regex patterns for category labels
    compiled_category_labels = [
        (pattern, re.compile(pattern)) for (label, pattern) in category_labels
    ]

    jira_issues = {}
    skipped_issues = []

    for issue in issues:
        url = ""
        # Get the link to ticket from field
        if url_field:
            try:
                result = re.match(HTTP_REGEX, issue.get_field(url_field))
                if result:
                    url = result[0]
            except AttributeError:
                log.debug("Couldn't retrieve the url from %s", issue.fields.summary)
                pass
        # Link field is not set, let's use the ticket URL instead
        else:
            url = issue.permalink()

        issue_added = False
        if issue.fields.labels:
            for label in issue.fields.labels:
                matched_category = None
                for cat_pattern, cat_regex in compiled_category_labels:
                    if cat_regex.match(label):
                        matched_category = cat_pattern
                        break
                if matched_category:
                    if matched_category not in jira_issues:
                        jira_issues[matched_category] = {}
                    jira_issues[matched_category][issue.fields.summary.strip()] = {
                        "url": url,
                        "key": issue.key,
                    }
                    issue_added = True
        else:
            if no_label not in jira_issues:
                jira_issues[no_label] = {}
            jira_issues[no_label][issue.fields.summary.strip()] = {
                "url": url,
                "key": issue.key,
            }
            issue_added = True

        if not issue_added and not open:  # Only log skipped closed issues
            skipped_issues.append(
                {
                    "key": issue.key,
                    "summary": issue.fields.summary,
                    "labels": issue.fields.labels or [],
                }
            )

    if skipped_issues and not open:
        log.debug(
            "The following closed issues were not added to the report (no matching category labels):"
        )
        for issue in skipped_issues:
            log.debug(
                "  - %s: %s (labels: %s)",
                issue["key"],
                issue["summary"],
                ", ".join(issue["labels"]) if issue["labels"] else "none",
            )

    return jira_issues
