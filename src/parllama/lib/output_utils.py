"""Output formatting utilities."""

from __future__ import annotations

import csv
import io
from enum import StrEnum
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table

console = Console(stderr=True)


class DisplayOutputFormat(StrEnum):
    """Enum for display output format choices."""

    NONE = "none"
    PLAIN = "plain"
    MD = "md"
    CSV = "csv"
    JSON = "json"


def csv_to_table(data: str, title: str = "Results") -> Table:
    """Convert csv data to a table."""
    data = data.strip()
    table = Table(title=title)
    if not data:
        table.add_column("Empty", justify="left", style="cyan", no_wrap=True)
        return table
    reader = csv.DictReader(io.StringIO(data))
    if not reader.fieldnames:
        table.add_column("Empty", justify="left", style="cyan", no_wrap=True)
        return table
    data = list(reader)  # pyright: ignore
    for f in reader.fieldnames:
        table.add_column(f, justify="left", style="cyan", no_wrap=True)

    for row in data:
        table.add_row(*[v for n, v in row.items()])  # pyright: ignore
    return table


def csv_file_to_table(csv_file: Path, title: str | None = None) -> Table:
    """Convert csv file to a table."""
    return csv_to_table(
        csv_file.read_text(encoding="utf-8").strip(),
        csv_file.name if title is None else title,
    )


def highlight_json(data: str) -> Syntax:
    """Highlight JSON data."""
    return Syntax(data, "json", background_color="default")


def highlight_json_file(json_file: Path) -> Syntax:
    """Highlight JSON data."""
    return highlight_json(json_file.read_text(encoding="utf-8").strip())


def get_output_format_prompt(display_format: DisplayOutputFormat) -> str:
    """Get the output format prompt."""
    preamble = """Follow the following instructions for output:"""
    if display_format == DisplayOutputFormat.MD:
        return f"""
{preamble}
    * Output properly formatted Markdown.
    * Use table / list formatting when applicable or requested.
    * Do not include an opening ```markdown or closing ```
"""
    if display_format == DisplayOutputFormat.JSON:
        return f"""
{preamble}
    * Output proper JSON.
    * Use a schema if provided.
    * Only output JSON. Do not include any other text / markdown or formatting such as opening ```json or closing ```
"""
    if display_format == DisplayOutputFormat.CSV:
        return f"""
{preamble}
    * Output proper CSV format.
    * Ensure you use double quotes on fields containing line breaks or commas.
    * Include a header with names of the fields.
    * Only output the CSV header and data.
    * Do not include any other text / Markdown such as opening ```csv or closing ```
"""
    if display_format == DisplayOutputFormat.PLAIN:
        return f"""
{preamble}
    * Output plain text without formatting, do not include any other formatting such as markdown.
"""
    return ""


def display_formatted_output(
    content: str, display_format: DisplayOutputFormat, out_console: Console | None = None
) -> None:
    """Display formatted output."""
    if display_format == DisplayOutputFormat.NONE:
        return

    if not out_console:
        out_console = console

    if display_format == DisplayOutputFormat.PLAIN:
        out_console.print(content)
    elif display_format == DisplayOutputFormat.MD:
        out_console.print(Markdown(content))
    elif display_format == DisplayOutputFormat.CSV:
        # Convert CSV to rich Table
        table = Table(title="CSV Data")
        csv_reader = csv.reader(io.StringIO(content))
        headers = next(csv_reader)
        for header in headers:
            table.add_column(header, style="cyan")
        for row in csv_reader:
            table.add_row(*row)
        out_console.print(table)
    elif display_format == DisplayOutputFormat.JSON:
        out_console.print(Syntax(content, "json"))
