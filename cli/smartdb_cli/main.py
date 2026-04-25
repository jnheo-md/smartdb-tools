"""
SmartDB CLI
============
Command-line interface for querying and exporting data from the SmartDB
registry via the API server.
"""

from pathlib import Path
from typing import Optional

import typer

from smartdb_cli import __version__
from smartdb_cli.commands.schema import app as schema_app
from smartdb_cli.commands.query import app as query_app
from smartdb_cli.commands.export import app as export_app

app = typer.Typer(
    name="smartdb",
    help=(
        "CLI tool for the SmartDB registry.\n\n"
        "IMPORTANT FOR AI AGENTS: Run 'smartdb guide' first to learn critical "
        "domain rules (e.g., always use 'query followup' for mRS outcomes, "
        "never 'query data' with admission_mrs variables)."
    ),
    no_args_is_help=True,
)

# Register sub-command groups
app.add_typer(schema_app, name="schema", help="Explore hospital schemas, tables, and variables.")
app.add_typer(query_app, name="query", help="Query patient data from the stroke registry.")
app.add_typer(export_app, name="export", help="Export patient data to XLSX files.")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"smartdb-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """SmartDB registry CLI."""


# ---------------------------------------------------------------------------
# Auth commands (top-level)
# ---------------------------------------------------------------------------

@app.command()
def login() -> None:
    """Log in to the SmartDB registry."""
    from smartdb_cli import auth
    from smartdb_cli.api_client import APIError
    from smartdb_cli.formatting import console, print_error, print_success

    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)

    try:
        session = auth.login(email, password)
        level_label = auth.get_user_level_label(session["level"])
        print_success(
            f"Welcome, {session['uname']}! "
            f"(level: {level_label}, hospital: {session['hidx']})"
        )
    except auth.AuthenticationError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)
    except APIError as exc:
        print_error(f"Login failed: {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        print_error(f"Login failed: {exc}")
        raise typer.Exit(code=1)


@app.command()
def logout() -> None:
    """Log out from the SmartDB registry."""
    from smartdb_cli import auth
    from smartdb_cli.formatting import print_success

    auth.logout()
    print_success("Logged out.")


@app.command()
def update() -> None:
    """Update smartdb-cli and MCP server to the latest version."""
    import importlib.metadata
    import shutil
    import subprocess
    import tarfile
    import tempfile
    from urllib.request import urlopen

    from smartdb_cli.config import BIN_DIR, MCP_DIR, REPO_TARBALL_URL, REPO_URL
    from smartdb_cli.formatting import console, print_error, print_success

    old_version = __version__
    tmp_dir = None

    try:
        tmp_dir = tempfile.mkdtemp(prefix="smartdb-update-")
        repo_dir = None

        # -- Step 1: Clone / download latest source --------------------------
        with console.status("[bold cyan]Downloading latest version…"):
            if shutil.which("git"):
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", REPO_URL, f"{tmp_dir}/repo"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    repo_dir = f"{tmp_dir}/repo"

            if repo_dir is None:
                # Fallback: download tarball
                tarball_path = f"{tmp_dir}/repo.tar.gz"
                with urlopen(REPO_TARBALL_URL) as resp:
                    with open(tarball_path, "wb") as f:
                        f.write(resp.read())
                with tarfile.open(tarball_path, "r:gz") as tar:
                    tar.extractall(tmp_dir)
                # Tarball extracts to smartdb-tools-master/
                extracted = [
                    d for d in Path(tmp_dir).iterdir()
                    if d.is_dir() and d.name != "repo"
                ]
                if not extracted:
                    print_error("Failed to extract update archive.")
                    raise typer.Exit(code=1)
                repo_dir = str(extracted[0])

        pip = str(BIN_DIR / "pip")

        # -- Step 2: Upgrade CLI package -------------------------------------
        with console.status("[bold cyan]Upgrading CLI…"):
            result = subprocess.run(
                [pip, "install", "--quiet", "--upgrade", f"{repo_dir}/cli"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print_error(f"CLI upgrade failed:\n{result.stderr}")
                raise typer.Exit(code=1)

        # -- Step 3: Upgrade MCP server dependencies -------------------------
        with console.status("[bold cyan]Upgrading MCP server dependencies…"):
            result = subprocess.run(
                [pip, "install", "--quiet", "mcp[cli]>=1.0.0", "httpx>=0.25.0"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print_error(f"MCP dependency upgrade failed:\n{result.stderr}")
                raise typer.Exit(code=1)

        # -- Step 4: Copy MCP server files -----------------------------------
        with console.status("[bold cyan]Updating MCP server files…"):
            MCP_DIR.mkdir(parents=True, exist_ok=True)
            src_mcp = Path(repo_dir) / "mcp-server"
            for filename in ("server.py", "api_client.py", "variable_safety.py"):
                src = src_mcp / filename
                if src.exists():
                    shutil.copy2(src, MCP_DIR / filename)

        # -- Step 5: Report version ------------------------------------------
        new_version = importlib.metadata.version("smartdb-cli")
        if new_version == old_version:
            print_success(f"Already up to date (v{old_version}).")
        else:
            print_success(f"Updated v{old_version} → v{new_version}")

    except typer.Exit:
        raise
    except Exception as exc:
        print_error(f"Update failed: {exc}")
        raise typer.Exit(code=1)
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)


@app.command()
def whoami() -> None:
    """Show the currently logged-in user."""
    from smartdb_cli import auth
    from smartdb_cli.api_client import APIError
    from smartdb_cli.formatting import console, print_warning

    from rich.panel import Panel
    from rich.table import Table

    user = auth.get_current_user()
    if user is None:
        console.print("[dim]Not logged in.[/dim]")
        raise typer.Exit()

    # Verify token is still valid by calling GET /auth/me
    server_user = auth.verify_token()
    if server_user is None:
        print_warning(
            "Session token may be expired. Run [bold]smartdb login[/bold] to re-authenticate."
        )

    level_label = auth.get_user_level_label(user.get("level", 0))

    info = Table(show_header=False, box=None, padding=(0, 2))
    info.add_column("Field", style="bold cyan")
    info.add_column("Value")

    info.add_row("Name", str(user.get("uname", "")))
    info.add_row("Email", str(user.get("email", "")))
    info.add_row("Level", level_label)
    info.add_row("Hospital (hidx)", str(user.get("hidx", "")))
    info.add_row("Description", str(user.get("description", "")))
    info.add_row("Login time", str(user.get("login_time", "")))
    if server_user:
        info.add_row("Token status", "[green]Valid[/green]")
    else:
        info.add_row("Token status", "[red]Expired or invalid[/red]")

    console.print(Panel(info, title="Current User", border_style="cyan", expand=False))


# ---------------------------------------------------------------------------
# Config commands
# ---------------------------------------------------------------------------

config_app = typer.Typer(name="config", help="Manage CLI configuration.")
app.add_typer(config_app, name="config", help="Manage CLI configuration.")


@config_app.command("set-url")
def config_set_url(
    url: str = typer.Argument(..., help="API server URL (e.g. http://localhost:8000)"),
) -> None:
    """Set the API server URL."""
    from smartdb_cli.config import set_api_url
    from smartdb_cli.formatting import print_success

    set_api_url(url)
    print_success(f"API URL set to: {url}")


@config_app.command("show")
def config_show() -> None:
    """Show current configuration."""
    from smartdb_cli import auth
    from smartdb_cli.config import EXPORT_DIR, get_api_url, SESSION_FILE, CONFIG_FILE
    from smartdb_cli.formatting import console

    from rich.panel import Panel
    from rich.table import Table

    info = Table(show_header=False, box=None, padding=(0, 2))
    info.add_column("Setting", style="bold cyan")
    info.add_column("Value")

    info.add_row("API URL", get_api_url())
    info.add_row("Config file", str(CONFIG_FILE))
    info.add_row("Session file", str(SESSION_FILE))
    info.add_row("Export directory", EXPORT_DIR)

    user = auth.get_current_user()
    if user:
        info.add_row("Logged in as", f"{user.get('uname', '')} ({user.get('email', '')})")
        info.add_row("Session API URL", user.get("api_url", "-"))
    else:
        info.add_row("Logged in as", "[dim]Not logged in[/dim]")

    console.print(Panel(info, title="SmartDB CLI Configuration", border_style="cyan", expand=False))


# ---------------------------------------------------------------------------
# Guide command (for AI agents)
# ---------------------------------------------------------------------------

_GUIDE_TEXT = """\
SmartDB CLI — Domain Guide for AI Agents
==========================================

READ THIS BEFORE querying outcome data. These rules prevent common mistakes.

## 1. Patient Outcomes (mRS) — ALWAYS USE 'query followup'

ALWAYS use 'smartdb query followup' or 'smartdb export followup' for mRS
outcomes at ALL hospitals. These commands handle hospital differences
automatically:
  - YSU: queries the cohort table (db_5) with mRS_calculated + death imputation
  - Other hospitals: falls back to secret_mrs_3month automatically

NEVER query admission_mrs_3month or secret_mrs_3month directly via 'query data'.
  - admission_mrs_3month is empty at most hospitals
  - get_followup_mrs() / 'query followup' already uses the correct source

Note: discharge mRS ('mRS' in db_11) and pre-stroke mRS ('prestroke_mRS')
are fine to query directly — those are not follow-up outcomes.

## 2. NIHSS Scores — LAYOUT-FIRST, NOT 'NIHSS_total_*'

Different hospitals collect NIHSS differently:
  - Some enter 15 individual sub-items (Q1a through Q11) -> auto-calculated totals
  - Most enter just the total score directly -> stored in admission_NIH_day_0/1/dc

DANGEROUS (CALCULATED, produce false zeros):
  NIHSS_total_day_0, NIHSS_total_day_1, NIHSS_total_day_3,
  NIHSS_total_day_7, NIHSS_total_day_14, NIHSS_total_dc

CORRECT (raw, NULL when not recorded):
  admission_NIH_day_0, admission_NIH_day_1, admission_NIH_day_dc
  NIH_before_EVT, secret_nih_after_tPA

ALWAYS check the hospital's form layout first to see which NIHSS
variables they use. For the MCP server, use get_nihss_scores().

NOTE: 'NIHSS_total' does NOT exist as a variable.

## 3. Follow-up Periods

Available: 3m, 6m, 9m, 12m, 2y, 3y, 4y, 5y, 6y, 7y, 8y, 9y, 10y

Each period corresponds to a checkbox column in db_5 (e.g., threefu_cohort).
A single patient can have multiple cohort rows (one per follow-up visit).

## 4. Filtering by Treatment / Subgroup

Use --filters with 'query followup' or 'export followup' to select subgroups:

  # Mechanical thrombectomy patients only
  smartdb query followup YSU -p 3m \\
    -f '[{"variable":"Thr_mechanical","operator":"=","value":"1"}]'

  # Filter by admission date range
  smartdb export followup YSU -p 3m \\
    -f '[{"variable":"adm_date","operator":">=","value":"2024-01-01"}]'

Filters are applied to both the cohort query and the death imputation query.

## 5. Key Date Variables

When filtering patients by time period, use these date variables:
  - 'adm_date' (db_11): Admission date (입원일자) — USE THIS for selecting
    patients by admission period (e.g., "patients from June 2024 onward").
  - 'onset_hospital_arrival' (db_11): Hospital arrival timestamp — this is the
    onset-to-door time, NOT the admission date. Use only for time-interval
    calculations (e.g., onset-to-treatment time).
  - 'fu_date_cohort' (db_5): Follow-up visit date — already included in
    followup command output.

Example: patients admitted from June 2024:
  -f '[{"variable":"adm_date","operator":">=","value":"2024-06-01"}]'

## 6. Variable Value Encoding

SELECT/CHECKBOX variables store coded values, NOT labels:
  - Thr_mechanical: 1 = Yes, 0 = No  (NOT "Yes"/"No")
  - pt_sex: M / F
  - Use 'smartdb schema variable <hospital> <var>' to see the value map.

## 7. Hospital Codes

Use hospital code (e.g., 'YSU') or hidx number (e.g., '1').
Run 'smartdb schema hospitals' to see all available hospitals.
Not all hospitals have the same tables or variables.

## 8. Table Hierarchy

Tables are hierarchical: db_1 (Patient) -> db_11 (Admission) -> db_12 (Treatment).
'query data' automatically JOINs across tables when you request variables from
different tables. No manual JOIN needed.

## 9. Exporting Data

  - 'export xlsx': Export raw variable data to XLSX
  - 'export followup': Export cohort-based mRS outcomes to XLSX (PREFERRED for outcomes)
  - 'export merge': Add new columns to an existing XLSX file by patient matching
"""


@app.command()
def guide() -> None:
    """Print domain guide for AI agents. READ THIS FIRST before querying outcomes."""
    from smartdb_cli.formatting import console
    from rich.markdown import Markdown

    console.print(Markdown(_GUIDE_TEXT))


# ---------------------------------------------------------------------------
# Anonymization lookup command
# ---------------------------------------------------------------------------

@app.command()
def lookup(
    hospital: str = typer.Argument(..., help="Hospital code (e.g., KMU) or hidx number."),
    query: str = typer.Argument(..., help="Search value (chart number, name, or reg_num)."),
    field: str = typer.Option(
        "chart", "--field", "-f",
        help="Field to search: chart (chart number), name (patient name), id (reg_num).",
    ),
    table: str = typer.Option(
        "", "--table", "-t",
        help="Restrict to a specific table (e.g., db_113). Optional.",
    ),
) -> None:
    """Look up anonymized patient identity (chart number, name) from the registry."""
    from smartdb_cli.auth import require_auth
    require_auth()
    from smartdb_cli.api_client import APIError, post
    from smartdb_cli.formatting import console, print_error, print_table

    # Map user-friendly field names to API field names
    field_map = {"chart": "data1", "name": "data2", "id": "reg_num"}
    api_field = field_map.get(field)
    if api_field is None:
        print_error(f"Invalid field '{field}'. Use: chart, name, or id")
        raise typer.Exit(code=1)

    body = {
        "hospital": hospital,
        "query": query,
        "field": api_field,
        "table": table,
        "limit": 20,
    }

    try:
        results = post("/anon/lookup", json_body=body)
    except APIError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    if not results:
        console.print("[dim]No matches found.[/dim]")
        raise typer.Exit()

    # Build display rows
    from rich.table import Table as RichTable

    tbl = RichTable(
        title=f"Anonymization Lookup: {query} ({field})",
        show_lines=False,
        highlight=True,
    )
    tbl.add_column("table", style="cyan")
    tbl.add_column("reg_num", style="bold")
    tbl.add_column("chart# (data1)")
    tbl.add_column("name (data2)")
    tbl.add_column("sex")
    tbl.add_column("age")

    for r in results:
        pd = r.get("patient_data") or {}
        tbl.add_row(
            r.get("table_name", ""),
            str(r.get("reg_num", "")),
            str(r.get("data1", "")),
            str(r.get("data2", "")),
            str(pd.get("pt_sex", "")),
            str(pd.get("pt_age", "")),
        )

    console.print(tbl)


# ---------------------------------------------------------------------------
# Clot (thrombus) composition commands
# ---------------------------------------------------------------------------

clot_app = typer.Typer(name="clot", help="Query thrombus/clot composition data from ARIA.")
app.add_typer(clot_app, name="clot", help="Query thrombus/clot composition data from ARIA.")


@clot_app.command()
def patients(
    hospital: str = typer.Argument(..., help="Hospital code (e.g., YSU)."),
) -> None:
    """List thrombus patients for a hospital."""
    from smartdb_cli.auth import require_auth
    require_auth()
    from smartdb_cli.api_client import APIError, get
    from smartdb_cli.formatting import console, print_error

    from rich.table import Table as RichTable

    try:
        results = get(f"/clot/patients/{hospital}")
    except APIError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    if not results:
        console.print("[dim]No thrombus patients found.[/dim]")
        raise typer.Exit()

    tbl = RichTable(
        title=f"Thrombus Patients — {hospital}",
        show_lines=False,
        highlight=True,
    )
    tbl.add_column("full_code", style="bold")
    tbl.add_column("patient_code")
    tbl.add_column("hospital_code", style="cyan")

    for r in results:
        tbl.add_row(
            str(r.get("full_code", "")),
            str(r.get("patient_code", "")),
            str(r.get("hospital_code", "")),
        )

    console.print(tbl)


@clot_app.command()
def composition(
    hospital: str = typer.Argument(..., help="Hospital code (e.g., YSU)."),
    thrombus_code: str = typer.Argument(..., help="Thrombus code (e.g., YSU001 or 001)."),
) -> None:
    """Get stain composition for a specific thrombus."""
    from smartdb_cli.auth import require_auth
    require_auth()
    from smartdb_cli.api_client import APIError, get
    from smartdb_cli.formatting import console, print_error

    from rich.panel import Panel
    from rich.table import Table as RichTable

    try:
        data = get(f"/clot/composition/{hospital}/{thrombus_code}")
    except APIError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    # Display header info
    header_lines = [
        f"[bold]Thrombus code:[/bold] {data.get('thrombus_code', '')}",
        f"[bold]Patient code:[/bold] {data.get('patient_code', '')}",
    ]
    console.print(Panel("\n".join(header_lines), title="Clot Info", border_style="cyan", expand=False))

    # Display stain table
    stains = data.get("stains", [])
    if not stains:
        console.print("[dim]No stain data available.[/dim]")
        raise typer.Exit()

    tbl = RichTable(
        title="Stain Composition",
        show_lines=False,
        highlight=True,
    )
    tbl.add_column("stain", style="bold")
    tbl.add_column("stain_area", justify="right")
    tbl.add_column("total_area", justify="right")
    tbl.add_column("ratio%", justify="right", style="green")

    for s in stains:
        ratio = s.get("ratio")
        ratio_str = f"{ratio:.2f}" if ratio is not None else ""
        tbl.add_row(
            str(s.get("stain", "")),
            str(s.get("stain_area", "")),
            str(s.get("total_area", "")),
            ratio_str,
        )

    console.print(tbl)


@clot_app.command()
def search(
    hospital: str = typer.Argument(..., help="Hospital code (e.g., YSU)."),
    query: str = typer.Argument(..., help="Search value (chart number or thrombus code)."),
    field: str = typer.Option(
        "patient_code", "--field", "-f",
        help="Field to search: patient_code or thrombus_code.",
    ),
) -> None:
    """Search for clot data by patient code or thrombus code."""
    from smartdb_cli.auth import require_auth
    require_auth()
    from smartdb_cli.api_client import APIError, post
    from smartdb_cli.formatting import console, print_error

    from rich.table import Table as RichTable

    body = {
        "hospital": hospital,
        "query": query,
        "field": field,
        "limit": 20,
    }

    try:
        results = post("/clot/search", json_body=body)
    except APIError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    if not results:
        console.print("[dim]No matches found.[/dim]")
        raise typer.Exit()

    tbl = RichTable(
        title=f"Clot Search: {query} ({field})",
        show_lines=False,
        highlight=True,
    )
    tbl.add_column("full_code", style="bold")
    tbl.add_column("patient_code")
    tbl.add_column("hospital_code", style="cyan")

    for r in results:
        tbl.add_row(
            str(r.get("full_code", "")),
            str(r.get("patient_code", "")),
            str(r.get("hospital_code", "")),
        )

    console.print(tbl)


@clot_app.command()
def summary(
    hospital: str = typer.Argument(..., help="Hospital code (e.g., YSU)."),
) -> None:
    """Show summary statistics for thrombus data."""
    from smartdb_cli.auth import require_auth
    require_auth()
    from smartdb_cli.api_client import APIError, get
    from smartdb_cli.formatting import console, print_error

    from rich.panel import Panel

    try:
        data = get(f"/clot/summary/{hospital}")
    except APIError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1)

    lines = []
    for key, value in data.items():
        lines.append(f"[bold]{key}:[/bold] {value}")

    console.print(Panel(
        "\n".join(lines) if lines else "[dim]No summary data.[/dim]",
        title=f"Clot Summary — {hospital}",
        border_style="cyan",
        expand=False,
    ))


if __name__ == "__main__":
    app()
