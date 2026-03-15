"""
Query Commands
===============
CLI commands for querying patient data from the ysr3 stroke registry via the API.
"""

from __future__ import annotations

import json
from typing import Optional

import typer

from ysr3_cli import api_client
from ysr3_cli.api_client import APIError
from ysr3_cli.auth import require_auth
from ysr3_cli.formatting import (
    console,
    format_number,
    print_error,
    print_table,
    print_warning,
)

app = typer.Typer(name="query", help="Query patient data from the stroke registry.")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_filters(filters_json: str) -> list[dict]:
    """Parse a JSON string into a list of filter dicts."""
    if not filters_json or not filters_json.strip():
        return []
    try:
        parsed = json.loads(filters_json)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_variable_list(variables: str) -> list[str]:
    """Parse a comma-separated variable list into individual names."""
    if not variables or not variables.strip():
        return []
    return [v.strip() for v in variables.split(",") if v.strip()]


# ═══════════════════════════════════════════════════════════════════════════
# Command: data
# ═══════════════════════════════════════════════════════════════════════════


@app.command("data")
def query_data(
    hospital: str = typer.Argument(..., help="Hospital code (e.g. 'YSU') or hidx"),
    variables: str = typer.Option(
        ..., "--vars", "-v", help="Comma-separated variable names (e.g. 'pt_sex,pt_age')"
    ),
    filters: str = typer.Option("", "--filters", "-f", help="JSON filter string"),
    limit: int = typer.Option(100, "--limit", "-n", help="Max rows (default 100, max 5000)"),
) -> None:
    """Query patient data for the requested variables with auto-JOINs."""
    try:
        require_auth()

        var_list = _parse_variable_list(variables)
        if not var_list:
            print_error("Please specify at least one variable with --vars.")
            raise typer.Exit(1)

        filter_list = _parse_filters(filters)
        body = {
            "hospital": hospital,
            "variables": var_list,
            "filters": filter_list,
            "limit": max(1, min(limit, 5000)),
        }

        result = api_client.post("/query/data", json_body=body)

        columns = result["columns"]
        rows = result["rows"]
        summary = result.get("summary", {})

        # Header info
        console.print(f"[bold]Hospital:[/bold] {result['hospital']} (hidx={result.get('hidx', '')})")
        console.print(f"[bold]Variables:[/bold] {', '.join(var_list)}")
        if filter_list:
            console.print(f"[bold]Filters:[/bold] {json.dumps(filter_list, ensure_ascii=False)}")
        console.print(f"[bold]Rows returned:[/bold] {format_number(result['row_count'])} (limit: {format_number(result['limit'])})")
        console.print()

        if not rows:
            console.print("[dim]No data found matching the criteria.[/dim]")
            return

        print_table(rows, columns)

        # Summary statistics from API
        if summary:
            console.print()
            console.print("[bold]--- Summary ---[/bold]")
            for col, stats in summary.items():
                if stats.get("type") == "empty":
                    console.print(f"  {col}: {stats['message']}")
                elif stats.get("type") == "numeric":
                    console.print(
                        f"  {col}: n={stats['n']}, "
                        f"mean={stats['mean']:.2f}, median={stats['median']:.2f}, "
                        f"min={stats['min']}, max={stats['max']}"
                    )
                elif stats.get("type") == "categorical":
                    top = stats.get("top", [])
                    top_str = ", ".join(f"{t['value']}={t['count']}" for t in top)
                    console.print(
                        f"  {col}: n={stats['n']}, nulls={stats['nulls']}, "
                        f"unique={stats['unique']}, top: {top_str}"
                    )

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        print_error(f"Query failed: {exc}")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# Command: count
# ═══════════════════════════════════════════════════════════════════════════


@app.command("count")
def get_patient_count(
    hospital: str = typer.Argument(..., help="Hospital code or hidx"),
    filters: str = typer.Option("", "--filters", "-f", help="JSON filter string"),
) -> None:
    """Count patients matching given criteria."""
    try:
        require_auth()

        filter_list = _parse_filters(filters)
        body = {
            "hospital": hospital,
            "filters": filter_list,
        }

        result = api_client.post("/query/count", json_body=body)

        console.print(f"[bold]Hospital:[/bold] {result['hospital']} (hidx={result.get('hidx', '')})")
        if filter_list:
            console.print(f"[bold]Filters:[/bold] {json.dumps(filter_list, ensure_ascii=False)}")
        console.print(f"[bold]Patient count:[/bold] {format_number(result['count'])}")

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        print_error(f"Count query failed: {exc}")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# Command: sql
# ═══════════════════════════════════════════════════════════════════════════


@app.command("sql")
def run_sql(
    query: str = typer.Argument(..., help="SQL SELECT query to execute"),
) -> None:
    """Execute a read-only SQL query against the ysr3 database.

    Only SELECT, WITH, SHOW, DESCRIBE, and EXPLAIN statements are allowed.
    A LIMIT 1000 is automatically added if no LIMIT clause is present.
    """
    try:
        require_auth()

        body = {"query": query}
        result = api_client.post("/query/sql", json_body=body)

        columns = result["columns"]
        rows = result["rows"]

        console.print(f"[bold]Rows returned:[/bold] {format_number(result['row_count'])}")
        console.print(f"[bold]Columns:[/bold] {', '.join(columns)}")
        console.print()

        if rows:
            print_table(rows, columns)
        else:
            console.print("[dim](no rows returned)[/dim]")

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        print_error(f"SQL execution failed: {exc}")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# Command: sample
# ═══════════════════════════════════════════════════════════════════════════


@app.command("sample")
def get_sample_data(
    hospital: str = typer.Argument(..., help="Hospital code or hidx"),
    table: str = typer.Argument(..., help="Table name (e.g. 'db_11')"),
    num_rows: int = typer.Option(5, "--rows", "-n", help="Number of sample rows (max 20)"),
) -> None:
    """Get sample rows from a table to understand data format."""
    try:
        require_auth()

        body = {
            "hospital": hospital,
            "table": table,
            "rows": max(1, min(num_rows, 20)),
        }

        result = api_client.post("/query/sample", json_body=body)

        columns = result["columns"]
        rows = result["rows"]
        code = result.get("hospital", hospital)

        console.print(f"[bold]Hospital:[/bold] {code} | [bold]Table:[/bold] {result.get('table', table)} | [bold]Sample rows:[/bold] {len(rows)}")
        console.print()

        if not rows:
            console.print("[dim](no data found in this table for the given hospital)[/dim]")
            return

        # Show registered variables for this table
        registered_vars = result.get("registered_variables", [])
        if registered_vars:
            console.print(f"[bold]Registered variables:[/bold] {len(registered_vars)}")
            var_names = [v["key"] for v in registered_vars[:15]]
            console.print(f"  {', '.join(var_names)}")
            if len(registered_vars) > 15:
                console.print(f"  ... and {len(registered_vars) - 15} more")
            console.print()

        # For wide tables, display vertically; otherwise use a table
        if len(columns) > 10:
            for i, row in enumerate(rows):
                console.print(f"[bold]--- Row {i + 1} ---[/bold]")
                for col in columns:
                    val = row.get(col)
                    console.print(f"  {col}: {val}")
                console.print()
        else:
            print_table(rows, columns)

        console.print()
        console.print(f"[bold]Total columns:[/bold] {len(columns)}")
        console.print(f"[bold]Column names:[/bold] {', '.join(columns)}")

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        print_error(f"Sample query failed: {exc}")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# Command: followup
# ═══════════════════════════════════════════════════════════════════════════


@app.command("followup")
def get_followup_mrs(
    hospital: str = typer.Argument(..., help="Hospital code (e.g. 'YSU')"),
    period: str = typer.Option("3m", "--period", "-p", help="Follow-up period (3m, 6m, 12m, 2y, etc.)"),
    variables: Optional[str] = typer.Option(None, "--vars", "-v", help="Additional comma-separated variables to include"),
    filters: str = typer.Option("", "--filters", "-f", help="JSON filter string"),
    limit: int = typer.Option(5000, "--limit", "-n", help="Max rows (default 5000)"),
) -> None:
    """THE CORRECT WAY to get mRS outcome data. Uses the cohort table (db_5).

    DO NOT use 'query data' with 'admission_mrs_3month' for outcomes — that
    variable is a quick-note field from db_11, NOT the authoritative outcome.

    This command queries mRS from the cohort table using 'mRS_calculated',
    with death imputation (mRS=6 for patients who died before the period).
    Use --filters to select subgroups (e.g., thrombectomy patients).
    Use 'export followup' to save results as XLSX.

    Available periods: 3m, 6m, 9m, 12m, 2y, 3y, 4y, 5y, 6y, 7y, 8y, 9y, 10y
    """
    try:
        require_auth()

        var_list = _parse_variable_list(variables) if variables else []
        filter_list = _parse_filters(filters)

        body = {
            "hospital": hospital,
            "period": period,
            "variables": var_list,
            "filters": filter_list,
            "limit": max(1, min(limit, 20000)),
        }

        result = api_client.post("/query/followup", json_body=body)

        columns = result["columns"]
        rows = result["rows"]
        code = result.get("hospital", hospital)
        period_key = result.get("period", period)
        period_label = result.get("period_label", period)
        stats = result.get("stats", {})

        # Handle the "note" case (fallback direct mRS columns)
        if result.get("note"):
            print_warning(result["note"])
            console.print()

        console.print(f"[bold]Follow-up mRS at {period_label}[/bold]")
        console.print(f"[bold]Hospital:[/bold] {code}")
        console.print(f"[bold]Period:[/bold] {period_key}")
        console.print(f"[bold]Total patients:[/bold] {format_number(result['row_count'])}")
        if stats:
            console.print(f"  From cohort table: {format_number(stats.get('from_cohort', 0))}")
            imputed = stats.get("imputed_death", 0)
            if imputed:
                console.print(f"  Imputed mRS=6 (died, no cohort row): {format_number(imputed)}")
        console.print()

        if not rows:
            console.print(f"[dim]No patients found with {period_label} follow-up mRS data.[/dim]")
            return

        print_table(rows, columns)

        # mRS distribution from stats
        if stats and stats.get("mrs_distribution"):
            console.print()
            console.print(f"[bold]--- mRS Distribution ({period_label}) ---[/bold]")
            mrs_dist = stats["mrs_distribution"]
            total_mrs = sum(mrs_dist.values())
            for score in sorted(mrs_dist.keys()):
                n = mrs_dist[score]
                pct = n / max(total_mrs, 1) * 100
                bar = "#" * int(pct / 2)
                console.print(f"  mRS {score}: {n:>5} ({pct:5.1f}%) {bar}")
            console.print(f"  Total: {format_number(total_mrs)}")

            # Good/poor outcome
            if stats.get("good_outcome_0_2") is not None:
                console.print(
                    f"  Good outcome (mRS 0-2): {stats['good_outcome_0_2']} ({stats['good_outcome_pct']:.1f}%)"
                )
                console.print(
                    f"  Poor outcome (mRS 3-6): {stats['poor_outcome_3_6']} ({stats['poor_outcome_pct']:.1f}%)"
                )

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        print_error(f"Follow-up query failed: {exc}")
        raise typer.Exit(1)
