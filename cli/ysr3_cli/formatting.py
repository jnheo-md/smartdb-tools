"""
Rich Formatting Helpers
========================
Console output utilities using the Rich library.
"""

from __future__ import annotations

import json as _json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def print_table(
    rows: list[dict],
    columns: list[str] | None = None,
    title: str = "",
) -> None:
    """Render *rows* as a Rich table.

    If *columns* is None, columns are inferred from the keys of the first row.
    """
    if not rows:
        console.print("[dim]No rows to display.[/dim]")
        return

    if columns is None:
        columns = list(rows[0].keys())

    table = Table(title=title, show_lines=False, highlight=True)
    for col in columns:
        table.add_column(col)

    for row in rows:
        table.add_row(*(str(row.get(c, "")) for c in columns))

    console.print(table)


def print_panel(content: str, title: str = "") -> None:
    """Print *content* inside a Rich panel."""
    console.print(Panel(content, title=title, expand=False))


def print_json_data(data) -> None:
    """Pretty-print JSON-serialisable *data* to the console."""
    console.print_json(_json.dumps(data, default=str, ensure_ascii=False))


def print_error(msg: str) -> None:
    """Print a red error message."""
    console.print(f"[bold red]Error:[/bold red] {msg}")


def print_success(msg: str) -> None:
    """Print a green success message."""
    console.print(f"[bold green]Success:[/bold green] {msg}")


def print_warning(msg: str) -> None:
    """Print a yellow warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {msg}")


def print_variable_info(var_dict: dict) -> None:
    """Print formatted variable details, including value maps."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")

    simple_fields = ["key", "col", "table", "label", "type_label"]
    for field in simple_fields:
        if field in var_dict:
            table.add_row(field, str(var_dict[field]))

    if var_dict.get("options"):
        table.add_row("options", str(var_dict["options"]))

    console.print(table)

    if var_dict.get("value_map"):
        console.print()
        vm_table = Table(title="Value Map", show_lines=False)
        vm_table.add_column("DB Value", style="bold")
        vm_table.add_column("Label")
        for db_val, label in var_dict["value_map"].items():
            vm_table.add_row(str(db_val), label)
        console.print(vm_table)


def format_number(n) -> str:
    """Format a number with comma separators."""
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)
