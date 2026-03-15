"""
Schema Commands
================
CLI commands for exploring the stroke registry schema via the API.
"""

from __future__ import annotations

import typer

from ysr3_cli import api_client
from ysr3_cli.api_client import APIError
from ysr3_cli.auth import require_auth
from ysr3_cli.formatting import (
    console,
    format_number,
    print_error,
)

from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

app = typer.Typer(name="schema", help="Explore hospital schemas, tables, and variables.")


def _format_options(options: str | None, type_label: str) -> str:
    """Return a human-readable representation of a variable's options field."""
    if options is None:
        return "-"
    if type_label in ("SELECT", "RADIO"):
        return " | ".join(options.split("|"))
    if type_label == "CALCULATED":
        return f"formula: {options}"
    if type_label == "NUMBER/TEXT":
        subtype_map = {"1": "text", "2": "number", "3": "date"}
        return subtype_map.get(str(options), str(options))
    return str(options)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("hospitals")
def list_hospitals() -> None:
    """List all hospitals in the stroke registry."""
    try:
        require_auth()
        hospitals = api_client.get("/schema/hospitals")

        if not hospitals:
            console.print("[dim]No hospitals found in the schema.[/dim]")
            return

        table = Table(
            title="Hospitals in the Stroke Registry",
            show_lines=False,
            highlight=True,
        )
        table.add_column("Code", style="bold cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("HIDX", justify="right", style="magenta")
        table.add_column("Variables", justify="right", style="green")
        table.add_column("Root Tables", style="dim")

        for h in hospitals:
            roots_str = ", ".join(h.get("root_tables", [])) if h.get("root_tables") else "-"
            table.add_row(
                h["code"],
                h["name"],
                str(h["hidx"]),
                format_number(h["variable_count"]),
                roots_str,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(hospitals)} hospital(s)[/dim]")

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Failed to list hospitals: {e}")
        raise typer.Exit(code=1)


@app.command("tables")
def list_tables(
    hospital: str = typer.Argument(..., help="Hospital code (e.g. 'YSU') or hidx number"),
) -> None:
    """List all tables/registries for a specific hospital."""
    try:
        require_auth()
        tables = api_client.get(f"/schema/tables/{hospital}")

        if not tables:
            console.print(f"[dim]No tables found for hospital '{hospital}'.[/dim]")
            return

        # Get hospital name from first table or title
        hospital_name = hospital
        # Tables already have depth from the API

        table_widget = Table(
            title=f"Tables for {hospital}",
            show_lines=False,
            highlight=True,
        )
        table_widget.add_column("Table", style="bold cyan")
        table_widget.add_column("dbidx", justify="right", style="magenta")
        table_widget.add_column("Variables", justify="right", style="green")
        table_widget.add_column("Rows", justify="right", style="yellow")
        table_widget.add_column("Parent", style="dim")

        for t in tables:
            depth = t.get("depth", 0)
            indent = "  " * depth
            name_display = f"{indent}{t['table']}"
            if t.get("dbname"):
                name_display += f" ({t['dbname']})"

            parent_display = t["parent_table"] if t.get("parent_table") else "(root)"
            row_display = format_number(t["row_count"]) if t.get("row_count") else "-"

            table_widget.add_row(
                name_display,
                str(t["dbidx"]),
                format_number(t["variable_count"]),
                row_display,
                parent_display,
            )

        console.print(table_widget)

        total_vars = sum(t["variable_count"] for t in tables)
        console.print(
            f"\n[dim]Total: {len(tables)} table(s), "
            f"{format_number(total_vars)} variable(s)[/dim]"
        )

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list tables: {e}")
        raise typer.Exit(code=1)


@app.command("search")
def search_variables(
    hospital: str = typer.Argument(..., help="Hospital code or hidx"),
    query: str = typer.Argument(..., help="Search query (e.g. 'NIHSS', 'hypertension')"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results to return"),
) -> None:
    """Search for variables by name or label."""
    try:
        require_auth()
        results = api_client.get(
            f"/schema/search/{hospital}",
            params={"q": query, "limit": limit},
        )

        if not results:
            console.print(
                f"[dim]No variables matching '{query}' found for hospital "
                f"'{hospital}'.[/dim]\n"
                f"[dim]Try a broader search term or check spelling.[/dim]"
            )
            return

        table = Table(
            title=f"Search Results for '{query}' in {hospital}  ({len(results)} found)",
            show_lines=False,
            highlight=True,
        )
        table.add_column("#", justify="right", style="dim")
        table.add_column("Key", style="bold cyan", no_wrap=True)
        table.add_column("Column", style="white")
        table.add_column("Label")
        table.add_column("Table", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Score", justify="right", style="yellow")

        for i, r in enumerate(results, 1):
            table.add_row(
                str(i),
                r["key"],
                r["col"],
                r.get("label", ""),
                r["table"],
                r["type_label"],
                str(r.get("score", "")),
            )

        console.print(table)

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Search failed: {e}")
        raise typer.Exit(code=1)


@app.command("variable")
def get_variable_info(
    hospital: str = typer.Argument(..., help="Hospital code or hidx"),
    variable: str = typer.Argument(..., help="Exact variable key name (e.g. 'pt_sex')"),
) -> None:
    """Get detailed information about a specific variable."""
    try:
        require_auth()
        info = api_client.get(f"/schema/variable/{hospital}/{variable}")

        # Build a detail table inside a panel
        detail_table = Table(show_header=False, box=None, padding=(0, 2))
        detail_table.add_column("Field", style="bold cyan")
        detail_table.add_column("Value")

        detail_table.add_row("Key", info["key"])
        detail_table.add_row("Column", info["col"])
        detail_table.add_row("Table", info["table"])
        detail_table.add_row("Label", info.get("label", ""))
        detail_table.add_row("Type", f"{info['type_label']} (code {info['type']})")
        detail_table.add_row("Options", _format_options(info.get("options"), info["type_label"]))

        console.print(Panel(
            detail_table,
            title=f"Variable: {info['key']}  (hospital {hospital})",
            border_style="cyan",
            expand=False,
        ))

        # Show value map if available
        if info.get("value_map"):
            vm = info["value_map"]
            vm_table = Table(
                title=f"Value Map ({len(vm)} values)",
                show_lines=False,
            )
            vm_table.add_column("DB Value", style="bold")
            vm_table.add_column("Label")
            for db_val, label in vm.items():
                vm_table.add_row(str(db_val), label)
            console.print(vm_table)
        elif info["type_label"] in ("SELECT", "RADIO") and info.get("options"):
            choices = info["options"].split("|")
            ch_table = Table(
                title=f"Display Labels ({len(choices)})",
                show_lines=False,
            )
            ch_table.add_column("Index", style="bold", justify="right")
            ch_table.add_column("Label")
            for j, choice in enumerate(choices):
                ch_table.add_row(str(j), choice.strip())
            console.print(ch_table)

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get variable info: {e}")
        raise typer.Exit(code=1)


@app.command("table-vars")
def get_table_variables(
    hospital: str = typer.Argument(..., help="Hospital code or hidx"),
    table: str = typer.Argument(..., help="Table name (e.g. 'db_1', 'db_11')"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max variables to show"),
) -> None:
    """List all variables in a specific table."""
    try:
        require_auth()
        variables = api_client.get(
            f"/schema/table-vars/{hospital}/{table}",
            params={"limit": limit},
        )

        if not variables:
            console.print(
                f"[dim]No variables found for table '{table}' in hospital '{hospital}'.[/dim]"
            )
            raise typer.Exit(code=1)

        total = len(variables)

        tbl_widget = Table(
            title=f"Variables in {table} (hospital {hospital})  --  {total} total",
            show_lines=False,
            highlight=True,
        )
        tbl_widget.add_column("#", justify="right", style="dim")
        tbl_widget.add_column("Key", style="bold cyan", no_wrap=True)
        tbl_widget.add_column("Column", style="white")
        tbl_widget.add_column("Type", style="green")
        tbl_widget.add_column("Label")

        for i, v in enumerate(variables, 1):
            tbl_widget.add_row(
                str(i),
                v["key"],
                v["col"],
                v["type_label"],
                v.get("label", ""),
            )

        console.print(tbl_widget)

        if total >= limit:
            console.print(
                f"\n[dim]Showing up to {limit} variables. "
                f"Use --limit to see more.[/dim]"
            )

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list table variables: {e}")
        raise typer.Exit(code=1)


@app.command("describe")
def describe_registry(
    hospital: str = typer.Argument(..., help="Hospital code or hidx"),
) -> None:
    """Get a comprehensive overview of a hospital's registry structure."""
    try:
        require_auth()
        data = api_client.get(f"/schema/describe/{hospital}")

        summary = data["summary"]
        tables = data["tables"]
        variable_distribution = data["variable_distribution"]
        type_breakdown = data["type_breakdown"]

        # ---- Hospital summary panel ----
        summary_table = Table(show_header=False, box=None, padding=(0, 2))
        summary_table.add_column("Field", style="bold cyan")
        summary_table.add_column("Value")

        summary_table.add_row("Code", summary["code"])
        summary_table.add_row("Name", summary["name"])
        summary_table.add_row("Hospital Index", str(summary["hidx"]))
        summary_table.add_row("Total Variables", format_number(summary["variable_count"]))
        summary_table.add_row("Total Tables", str(len(tables)))
        root_tables_str = ", ".join(summary.get("root_tables", [])) or "-"
        summary_table.add_row("Root Tables", root_tables_str)

        console.print(Panel(
            summary_table,
            title=f"Registry Overview: {summary['code']}",
            border_style="cyan",
            expand=False,
        ))

        # ---- Table hierarchy tree ----
        children_map: dict[str, list[str]] = {}
        table_lookup: dict[str, dict] = {t["table"]: t for t in tables}
        root_table_names: list[str] = []

        for t in tables:
            parent = t.get("parent_table")
            if parent:
                children_map.setdefault(parent, []).append(t["table"])
            else:
                root_table_names.append(t["table"])

        def _build_tree_branch(tree_node: Tree, table_name: str) -> None:
            kids = children_map.get(table_name, [])
            for child in kids:
                child_meta = table_lookup.get(child, {})
                var_count = child_meta.get("variable_count", 0)
                row_count = child_meta.get("row_count", 0)
                label = f"[bold]{child}[/bold] [{var_count} vars"
                if row_count:
                    label += f", {format_number(row_count)} rows"
                label += "]"
                branch = tree_node.add(label)
                _build_tree_branch(branch, child)

        hierarchy_tree = Tree("[bold]Table Hierarchy[/bold]")
        for rt in root_table_names:
            rt_meta = table_lookup.get(rt, {})
            var_count = rt_meta.get("variable_count", 0)
            row_count = rt_meta.get("row_count", 0)
            dbname = rt_meta.get("dbname")
            label = f"[bold cyan]{rt}[/bold cyan]"
            if dbname:
                label += f" ({dbname})"
            label += f" [{var_count} vars"
            if row_count:
                label += f", {format_number(row_count)} rows"
            label += "]"
            root_branch = hierarchy_tree.add(label)
            _build_tree_branch(root_branch, rt)

        console.print(hierarchy_tree)
        console.print()

        # ---- Variable distribution table ----
        dist_table = Table(
            title="Variable Distribution",
            show_lines=False,
            highlight=True,
        )
        dist_table.add_column("Table", style="bold cyan")
        dist_table.add_column("Variables", justify="right", style="green")
        dist_table.add_column("Sample Fields", style="dim")

        for vd in variable_distribution:
            sample_str = ", ".join(vd.get("sample_fields", []))
            if vd["variable_count"] > 5:
                sample_str += ", ..."
            dist_table.add_row(
                vd["table"],
                format_number(vd["variable_count"]),
                sample_str,
            )

        console.print(dist_table)
        console.print()

        # ---- Variable type breakdown ----
        type_table = Table(
            title="Variable Types",
            show_lines=False,
            highlight=True,
        )
        type_table.add_column("Type", style="bold")
        type_table.add_column("Count", justify="right", style="green")
        type_table.add_column("%", justify="right", style="yellow")

        for tb in type_breakdown:
            type_table.add_row(
                tb["type"],
                format_number(tb["count"]),
                f"{tb['percentage']:.1f}%",
            )

        console.print(type_table)

        console.print(
            f"\n[dim]Total: {len(tables)} table(s), "
            f"{format_number(summary['variable_count'])} variable(s)[/dim]"
        )

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to describe registry: {e}")
        raise typer.Exit(code=1)
