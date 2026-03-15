"""
Export Commands
================
CLI commands for exporting patient data to XLSX files via the API.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import typer

from ysr3_cli import api_client
from ysr3_cli.api_client import APIError
from ysr3_cli.auth import require_auth
from ysr3_cli.config import EXPORT_DIR
from ysr3_cli.formatting import (
    console,
    format_number,
    print_error,
    print_success,
    print_warning,
)

app = typer.Typer(name="export", help="Export patient data to XLSX files.")


# ---------------------------------------------------------------------------
# Helpers
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


def _human_size(num_bytes: int | float) -> str:
    """Format a byte count as a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# Command: export xlsx
# ---------------------------------------------------------------------------


@app.command("xlsx")
def export_xlsx(
    hospital: str = typer.Argument(..., help="Hospital code (e.g. 'YSU')"),
    vars: str = typer.Option(..., "--vars", "-v", help="Comma-separated variable names (e.g. 'pt_sex,NIHSS_total')"),
    filters: str = typer.Option("", "--filters", "-f", help="JSON filter string"),
    filename: str = typer.Option("", "--filename", "-o", help="Output filename (auto-generated if empty)"),
    limit: int = typer.Option(20000, "--limit", "-n", help="Max rows (default 20000)"),
) -> None:
    """Export patient data to an XLSX file."""
    try:
        require_auth()

        variables = [v.strip() for v in vars.split(",") if v.strip()]
        if not variables:
            print_error("Please specify at least one variable to export.")
            raise typer.Exit(code=1)

        filter_list = _parse_filters(filters)

        body = {
            "hospital": hospital,
            "variables": variables,
            "filters": filter_list,
            "filename": filename,
            "limit": max(1, min(int(limit), 50000)),
        }

        with console.status("Exporting data..."):
            saved_path = api_client.download("/export/xlsx", json_body=body)

        file_size = saved_path.stat().st_size

        # Print summary
        print_success("Export complete!")
        console.print(f"  [bold]File:[/bold]     {saved_path}")
        console.print(f"  [bold]Size:[/bold]     {_human_size(file_size)}")
        console.print(f"  [bold]Hospital:[/bold] {hospital}")
        console.print(f"  [bold]Variables:[/bold] {', '.join(variables)}")
        if filter_list:
            console.print(f"  [bold]Filters:[/bold]  {json.dumps(filter_list, ensure_ascii=False)}")

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Export failed: {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Command: export merge
# ---------------------------------------------------------------------------


@app.command("merge")
def merge_xlsx(
    existing_file: str = typer.Argument(..., help="Path to existing XLSX file"),
    hospital: str = typer.Argument(..., help="Hospital code for database lookup"),
    vars: str = typer.Option(..., "--vars", "-v", help="Comma-separated new variable names to add"),
    match_column: str = typer.Option("patient_id", "--match-column", "-m", help="Column in XLSX used for matching"),
    db_match_variable: str = typer.Option("", "--db-match-variable", help="DB variable to match against (default: db_idx)"),
) -> None:
    """Add new columns to an existing XLSX file by matching patient records.

    Note: The merge operation is currently handled locally. The existing file
    is uploaded to the API server for processing if a merge endpoint is available,
    otherwise the CLI falls back to local query + pandas merge.
    """
    try:
        require_auth()

        new_variables = [v.strip() for v in vars.split(",") if v.strip()]
        if not new_variables:
            print_error("Please specify at least one new variable to add.")
            raise typer.Exit(code=1)

        # Resolve file path
        file_path = existing_file
        if not os.path.isabs(file_path):
            file_path = os.path.join(EXPORT_DIR, file_path)

        if not os.path.exists(file_path):
            print_error(f"File not found: {file_path}")
            raise typer.Exit(code=1)

        # For merge, we need to:
        # 1. Read the existing file locally to get match values
        # 2. Query the API for the new variables
        # 3. Merge locally and save
        import pandas as pd

        with console.status("Reading existing XLSX file..."):
            df_existing = pd.read_excel(file_path, engine="openpyxl")

        if match_column not in df_existing.columns:
            print_error(
                f"Match column '{match_column}' not found in the existing file. "
                f"Available columns: {', '.join(df_existing.columns.tolist())}"
            )
            raise typer.Exit(code=1)

        match_values = df_existing[match_column].dropna().unique().tolist()
        if not match_values:
            print_error(f"No non-null values found in column '{match_column}'.")
            raise typer.Exit(code=1)

        use_db_idx = not db_match_variable or db_match_variable.lower() in ("db_idx", "patient_id")

        # Build query via the API
        if use_db_idx:
            query_vars = list(new_variables)
            filter_list = [{
                "variable": "db_idx",
                "operator": "IN",
                "value": [str(int(v)) for v in match_values if v is not None],
            }]
            db_merge_key = "patient_id"
        else:
            query_vars = list(new_variables)
            if db_match_variable not in query_vars:
                query_vars.insert(0, db_match_variable)
            filter_list = [{
                "variable": db_match_variable,
                "operator": "IN",
                "value": [str(v) for v in match_values],
            }]
            db_merge_key = db_match_variable

        body = {
            "hospital": hospital,
            "variables": query_vars,
            "filters": filter_list,
            "limit": 50000,
        }

        with console.status("Querying API for new columns..."):
            result = api_client.post("/query/data", json_body=body)

        rows = result.get("rows", [])
        columns = result.get("columns", [])

        if not rows:
            print_warning(
                f"No matching records found in the database for the values in "
                f"column '{match_column}'. Nothing to merge."
            )
            raise typer.Exit(code=0)

        df_new = pd.DataFrame(rows, columns=columns)

        # Ensure matching column types are compatible
        if use_db_idx:
            df_existing[match_column] = pd.to_numeric(
                df_existing[match_column], errors="coerce"
            )
            df_new[db_merge_key] = pd.to_numeric(
                df_new[db_merge_key], errors="coerce"
            )
        else:
            df_existing[match_column] = df_existing[match_column].astype(str)
            df_new[db_merge_key] = df_new[db_merge_key].astype(str)

        # Identify which columns are truly new
        existing_cols = set(df_existing.columns)
        new_cols_to_add = [c for c in df_new.columns if c not in existing_cols and c != db_merge_key]
        merge_subset = [db_merge_key] + new_cols_to_add

        df_merge_right = df_new[merge_subset].drop_duplicates(subset=[db_merge_key])

        df_merged = df_existing.merge(
            df_merge_right,
            left_on=match_column,
            right_on=db_merge_key,
            how="left",
        )

        if db_merge_key != match_column and db_merge_key in df_merged.columns:
            df_merged.drop(columns=[db_merge_key], inplace=True)

        # Compute merge statistics
        total_rows = len(df_existing)
        matched = int(df_merged[new_cols_to_add[0]].notna().sum()) if new_cols_to_add else 0
        unmatched = total_rows - matched

        # Generate output filename
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{base_name}_merged_{ts}.xlsx"
        output_path = os.path.join(EXPORT_DIR, output_name)

        with console.status("Writing merged XLSX file..."):
            df_merged.to_excel(output_path, index=False, engine="openpyxl")

        file_size = os.path.getsize(output_path)

        print_success("Merge complete!")
        console.print(f"  [bold]Output file:[/bold]      {output_path}")
        console.print(f"  [bold]Size:[/bold]              {_human_size(file_size)}")
        console.print(f"  [bold]Total rows:[/bold]        {len(df_merged):,}")
        console.print(f"  [bold]Matched rows:[/bold]      {matched:,}")
        console.print(f"  [bold]Unmatched rows:[/bold]    {unmatched:,}")
        console.print(f"  [bold]Original columns:[/bold]  {len(df_existing.columns)}")
        console.print(f"  [bold]New columns added:[/bold] {len(new_cols_to_add)} ({', '.join(new_cols_to_add)})")
        console.print(f"  [bold]Total columns now:[/bold] {len(df_merged.columns)}")
        console.print(f"  [bold]Match:[/bold]             '{match_column}' (XLSX) <-> '{db_merge_key}' (DB)")
        console.print(f"  [bold]Source file:[/bold]       {file_path}")

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Merge failed: {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Command: export followup
# ---------------------------------------------------------------------------


@app.command("followup")
def export_followup(
    hospital: str = typer.Argument(..., help="Hospital code (e.g. 'YSU') or hidx"),
    period: str = typer.Option("3m", "--period", "-p", help="Follow-up period (3m, 6m, 12m, 2y, etc.)"),
    vars: str = typer.Option("", "--vars", "-v", help="Additional comma-separated variables to include"),
    filters: str = typer.Option("", "--filters", "-f", help="JSON filter string"),
    filename: str = typer.Option("", "--filename", "-o", help="Output filename (auto-generated if empty)"),
    limit: int = typer.Option(20000, "--limit", "-n", help="Max rows (default 20000)"),
) -> None:
    """Export mRS follow-up outcomes from the COHORT TABLE to XLSX.

    THIS IS THE CORRECT WAY to export patient outcomes. Uses the cohort table
    (db_5, mRS_calculated) with death imputation — NOT admission_mrs variables.

    Example:
        ysr3 export followup YSU -p 3m -v "pt_sex,pt_age" \\
          -f '[{"variable":"Thr_mechanical","operator":"=","value":"1"}]'
    """
    try:
        require_auth()

        additional_vars = [v.strip() for v in vars.split(",") if v.strip()] if vars else []
        filter_list = _parse_filters(filters)

        body = {
            "hospital": hospital,
            "period": period,
            "variables": additional_vars,
            "filters": filter_list,
            "limit": max(1, min(int(limit), 50000)),
        }

        with console.status("Querying follow-up data from cohort table..."):
            result = api_client.post("/query/followup", json_body=body)

        columns = result.get("columns", [])
        rows = result.get("rows", [])
        stats = result.get("stats", {})
        period_label = result.get("period_label", period)

        if not rows:
            print_warning(f"No patients found with {period_label} follow-up mRS data.")
            raise typer.Exit(code=0)

        # Build XLSX locally
        try:
            import pandas as pd
        except ImportError:
            print_error("pandas is required for export. Install with: pip install pandas openpyxl")
            raise typer.Exit(code=1)

        df = pd.DataFrame(rows, columns=columns)

        # Generate filename
        if not filename:
            period_key = result.get("period", period)
            code = result.get("hospital", hospital)
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{code}_followup_mRS_{period_key}_{ts}.xlsx"

        output_path = os.path.join(EXPORT_DIR, filename)

        with console.status("Writing XLSX file..."):
            df.to_excel(output_path, index=False, engine="openpyxl")

        file_size = os.path.getsize(output_path)

        print_success("Follow-up export complete!")
        console.print(f"  [bold]File:[/bold]         {output_path}")
        console.print(f"  [bold]Size:[/bold]         {_human_size(file_size)}")
        console.print(f"  [bold]Hospital:[/bold]     {result.get('hospital', hospital)}")
        console.print(f"  [bold]Period:[/bold]       {period_label}")
        console.print(f"  [bold]Total rows:[/bold]   {len(df):,}")
        if stats:
            console.print(f"  [bold]From cohort:[/bold]  {stats.get('from_cohort', 0):,}")
            imputed = stats.get("imputed_death", 0)
            if imputed:
                console.print(f"  [bold]Death imputed:[/bold] {imputed:,} (mRS=6)")
        if additional_vars:
            console.print(f"  [bold]Extra vars:[/bold]  {', '.join(additional_vars)}")
        if filter_list:
            console.print(f"  [bold]Filters:[/bold]    {json.dumps(filter_list, ensure_ascii=False)}")

        # mRS distribution
        mrs_col = f"mRS_{result.get('period', period)}"
        if mrs_col in df.columns:
            console.print()
            console.print(f"  [bold]--- mRS Distribution ({period_label}) ---[/bold]")
            dist = df[mrs_col].value_counts().sort_index()
            total = len(df)
            for score, n in dist.items():
                pct = n / max(total, 1) * 100
                bar = "#" * int(pct / 2)
                console.print(f"    mRS {score}: {n:>5} ({pct:5.1f}%) {bar}")

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Follow-up export failed: {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Command: export list
# ---------------------------------------------------------------------------


@app.command("list")
def list_exports() -> None:
    """List all previously exported XLSX files."""
    from rich.table import Table

    try:
        require_auth()
        files = api_client.get("/export/list")

        if not files:
            console.print("[dim]No exported XLSX files found on the server.[/dim]")
            return

        console.print(f"[bold]Total files:[/bold] {len(files)}")
        console.print()

        table = Table(show_lines=False, highlight=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Filename", style="cyan")
        table.add_column("Size", justify="right")
        table.add_column("Modified")

        for i, f in enumerate(files, 1):
            name = f["filename"]
            if len(name) > 55:
                name = name[:54] + "\u2026"
            table.add_row(str(i), name, f.get("size_human", ""), f.get("modified", ""))

        console.print(table)

        total_size = sum(f.get("size", 0) for f in files)
        console.print(f"\n[bold]Total size:[/bold] {_human_size(total_size)}")

    except APIError as e:
        print_error(str(e))
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list exports: {e}")
        raise typer.Exit(code=1)
