"""
YSR3 Stroke Registry MCP Server (v2 — API-backed)
===================================================
Connects to the YSR3 API server over HTTPS instead of direct MySQL.
Shares login session with the ysr3-cli (~/.ysr3/session.json).

If not logged in, tools will return an error asking the user to run
'ysr3 login' in the CLI first.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
import api_client

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "YSR3 Stroke Registry",
    instructions=(
        "You have access to the YSR3 Stroke Registry database containing clinical data "
        "for ~16,000+ stroke patients across 27 Korean hospitals. The registry has ~3,000 "
        "variables covering demographics, risk factors, imaging, labs, treatment, and outcomes.\n\n"
        "Start by using list_hospitals() to see available hospitals, then list_tables() to "
        "understand the table structure, and search_variables() to find specific clinical "
        "variables.\n\n"
        "The main hospital is YSU (Yonsei Severance Hospital) with the richest data.\n"
        "Key tables: db_1 (Patient demographics), db_11 (Admission - main clinical data), "
        "db_12 (Thrombolysis/Treatment), db_5 (Cohort follow-up), db_19 (Stent procedures).\n\n"
        "IMPORTANT RULES:\n"
        "- For mRS outcomes, ALWAYS use get_followup_mrs() — it queries the cohort table "
        "(db_5, mRS_calculated) with death imputation. NEVER use query_data() with "
        "admission_mrs_3month or similar db_11 variables for outcomes.\n"
        "- For filtering by date, use 'adm_date' (admission date), NOT 'onset_hospital_arrival'.\n"
        "- SELECT/CHECKBOX variables store coded values: Thr_mechanical=1 means Yes, 0 means No.\n"
        "- Use get_variable_info() to check value encoding before filtering."
    ),
)


# ---------------------------------------------------------------------------
# Auth check helper
# ---------------------------------------------------------------------------

def _require_auth() -> None:
    """Raise if not logged in."""
    if not api_client.is_logged_in():
        raise api_client.APIError(
            "Not logged in. Please run 'ysr3 login' in the CLI first to authenticate, "
            "then restart this MCP server.",
            status_code=401,
        )


def _format_table(rows: list[dict], columns: list[str], max_rows: int = 50) -> str:
    """Format rows as a simple text table."""
    if not rows:
        return "(no data)"
    lines = [" | ".join(columns)]
    lines.append("-+-".join("-" * max(len(c), 8) for c in columns))
    for row in rows[:max_rows]:
        vals = [str(row.get(c, "")) for c in columns]
        lines.append(" | ".join(vals))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Schema Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def list_hospitals() -> str:
    """List all hospitals in the stroke registry system.
    Returns a formatted table of hospital codes, names, and statistics."""
    _require_auth()
    result = api_client.get("/schema/hospitals")
    lines = ["Hospitals in the Stroke Registry", ""]
    for h in result:
        lines.append(
            f"  {h['code']:5s}  hidx={h['hidx']:<3}  {h['name']:<30s}  "
            f"vars={h.get('variable_count', '?'):>5}  root={','.join(h.get('root_tables', []))}"
        )
    lines.append(f"\nTotal: {len(result)} hospital(s)")
    return "\n".join(lines)


@mcp.tool()
async def list_tables(hospital_code: str) -> str:
    """List all tables/registries for a specific hospital.
    Shows table name, purpose, number of variables, and row count.

    Args:
        hospital_code: Hospital code (e.g., 'YSU', 'EWU') or hidx number
    """
    _require_auth()
    result = api_client.get(f"/schema/tables/{hospital_code}")
    lines = [f"Tables for {hospital_code}", ""]
    for t in result:
        indent = "  " * t.get("depth", 0)
        name = t.get("table", "")
        label = t.get("label", "")
        vars_count = t.get("variable_count", 0)
        rows = t.get("row_count")
        parent = t.get("parent_table", "")
        row_str = f"rows={rows}" if rows else ""
        lines.append(f"  {indent}{name} ({label})  vars={vars_count}  {row_str}  parent={parent}")
    return "\n".join(lines)


@mcp.tool()
async def search_variables(hospital_code: str, query: str, limit: int = 20) -> str:
    """Search for variables/columns in the stroke registry by name or description.
    Supports English and Korean search terms.

    Args:
        hospital_code: Hospital code (e.g., 'YSU') or hidx
        query: Search query (e.g., 'NIHSS', 'hypertension', 'blood pressure')
        limit: Max results to return (default 20)
    """
    _require_auth()
    result = api_client.get(
        f"/schema/search/{hospital_code}",
        params={"q": query, "limit": limit},
    )
    if not result:
        return f"No variables matching '{query}' found for hospital '{hospital_code}'."
    lines = [f"Search results for '{query}' in {hospital_code} ({len(result)} found)", ""]
    for i, v in enumerate(result, 1):
        lines.append(
            f"  {i:>3}. {v['key']:<35s}  table={v['table']:<8s}  "
            f"type={v.get('type_label', '?'):<12s}  label={v.get('label', '')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_variable_info(hospital_code: str, variable_name: str) -> str:
    """Get detailed information about a specific variable/column.
    Returns key, column name, table, label, type, options, and value mapping.

    Args:
        hospital_code: Hospital code or hidx
        variable_name: Exact variable key name (e.g., 'pt_sex', 'hypertension')
    """
    _require_auth()
    result = api_client.get(f"/schema/variable/{hospital_code}/{variable_name}")
    lines = [
        f"Variable: {result['key']}  (hospital {hospital_code})",
        f"  Column:   {result.get('col', '')}",
        f"  Table:    {result.get('table', '')}",
        f"  Label:    {result.get('label', '')}",
        f"  Type:     {result.get('type_label', '')} (code {result.get('type', '')})",
    ]
    if result.get("options"):
        lines.append(f"  Options:  {result['options']}")
    if result.get("value_map"):
        lines.append("  Value Map:")
        for db_val, label in result["value_map"].items():
            lines.append(f"    {db_val} = {label}")
    return "\n".join(lines)


@mcp.tool()
async def get_table_variables(hospital_code: str, table_name: str) -> str:
    """List all variables in a specific table.

    Args:
        hospital_code: Hospital code or hidx
        table_name: Table name (e.g., 'db_1', 'db_11')
    """
    _require_auth()
    result = api_client.get(f"/schema/table-vars/{hospital_code}/{table_name}")
    if not result:
        return f"No variables found in table '{table_name}' for hospital '{hospital_code}'."
    lines = [f"Variables in {table_name} ({hospital_code}) — {len(result)} total", ""]
    for i, v in enumerate(result, 1):
        lines.append(
            f"  {i:>3}. {v['key']:<35s}  type={v.get('type_label', '?'):<12s}  "
            f"label={v.get('label', '')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def describe_registry(hospital_code: str) -> str:
    """Get a comprehensive overview of a hospital's registry structure.
    Shows the table hierarchy, variable distribution, and key clinical domains.

    Args:
        hospital_code: Hospital code or hidx
    """
    _require_auth()
    result = api_client.get(f"/schema/describe/{hospital_code}")
    return json.dumps(result, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# Query Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def query_data(
    hospital_code: str,
    variables: list[str],
    filters: str = "",
    limit: int = 100,
) -> str:
    """Query patient data from the stroke registry.

    Returns tabular data for the requested variables.

    NOTE: Do NOT use this tool for mRS outcome data. Use get_followup_mrs() instead,
    which queries the authoritative cohort table (db_5) with death imputation.

    Args:
        hospital_code: Hospital code (e.g., 'YSU') or hidx
        variables: List of variable names to retrieve
                   (e.g., ['pt_sex', 'pt_age', 'hypertension'])
        filters: JSON string of filters, e.g.,
                 '[{"variable": "stroke_type", "operator": "=", "value": "LAA"}]'
                 Supported operators: =, !=, IN, NOT IN, >, <, >=, <=,
                 IS NULL, IS NOT NULL, LIKE
        limit: Max rows to return (default 100, max 5000)
    """
    _require_auth()
    filter_list = _parse_filters(filters)
    body = {
        "hospital": hospital_code,
        "variables": variables,
        "filters": filter_list,
        "limit": max(1, min(limit, 5000)),
    }
    result = api_client.post("/query/data", json_body=body)
    columns = result["columns"]
    rows = result["rows"]
    summary = result.get("summary", {})

    lines = [
        f"Hospital: {result.get('hospital', hospital_code)} (hidx={result.get('hidx', '')})",
        f"Variables: {', '.join(variables)}",
        f"Rows: {result['row_count']} (limit: {result['limit']})",
        "",
        _format_table(rows, columns),
    ]

    if summary:
        lines.append("\n--- Summary ---")
        for col, stats in summary.items():
            if stats.get("type") == "numeric":
                lines.append(
                    f"  {col}: n={stats['n']}, mean={stats['mean']:.2f}, "
                    f"median={stats['median']:.2f}, min={stats['min']}, max={stats['max']}"
                )
            elif stats.get("type") == "categorical":
                top = ", ".join(f"{t['value']}={t['count']}" for t in stats.get("top", []))
                lines.append(f"  {col}: n={stats['n']}, nulls={stats['nulls']}, unique={stats['unique']}, top: {top}")

    return "\n".join(lines)


@mcp.tool()
async def get_patient_count(hospital_code: str, filters: str = "") -> str:
    """Count patients matching given criteria.

    Args:
        hospital_code: Hospital code or hidx
        filters: JSON string of filters (same format as query_data)
    """
    _require_auth()
    filter_list = _parse_filters(filters)
    body = {"hospital": hospital_code, "filters": filter_list}
    result = api_client.post("/query/count", json_body=body)
    return f"Hospital: {result['hospital']} (hidx={result.get('hidx', '')})\nPatient count: {result['count']:,}"


@mcp.tool()
async def run_sql(query: str) -> str:
    """Execute a read-only SQL query against the ysr3 database.

    SAFETY: Only SELECT queries are allowed. Any INSERT/UPDATE/DELETE/DROP/ALTER
    will be rejected. A LIMIT 1000 is auto-added if no LIMIT is present.

    Args:
        query: SQL SELECT query to execute
    """
    _require_auth()
    result = api_client.post("/query/sql", json_body={"query": query})
    columns = result["columns"]
    rows = result["rows"]
    lines = [
        f"Rows: {result['row_count']}",
        f"Columns: {', '.join(columns)}",
        "",
        _format_table(rows, columns),
    ]
    return "\n".join(lines)


@mcp.tool()
async def get_sample_data(
    hospital_code: str,
    table_name: str,
    num_rows: int = 5,
) -> str:
    """Get sample rows from a specific table to understand data format.

    Args:
        hospital_code: Hospital code or hidx
        table_name: Table name (e.g., 'db_11')
        num_rows: Number of sample rows (default 5, max 20)
    """
    _require_auth()
    body = {
        "hospital": hospital_code,
        "table": table_name,
        "rows": max(1, min(num_rows, 20)),
    }
    result = api_client.post("/query/sample", json_body=body)
    columns = result["columns"]
    rows = result["rows"]

    lines = [
        f"Hospital: {result.get('hospital', hospital_code)} | Table: {result.get('table', table_name)}",
        f"Sample rows: {len(rows)} | Total columns: {len(columns)}",
    ]

    reg_vars = result.get("registered_variables", [])
    if reg_vars:
        var_names = [v["key"] for v in reg_vars[:20]]
        lines.append(f"Registered variables ({len(reg_vars)}): {', '.join(var_names)}")
        if len(reg_vars) > 20:
            lines.append(f"  ... and {len(reg_vars) - 20} more")

    lines.append("")
    for i, row in enumerate(rows, 1):
        lines.append(f"--- Row {i} ---")
        for col in columns:
            lines.append(f"  {col}: {row.get(col)}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_followup_mrs(
    hospital_code: str,
    period: str = "3m",
    additional_variables: list[str] | None = None,
    filters: str = "",
    limit: int = 5000,
) -> str:
    """Get mRS scores at a specific follow-up period for stroke patients.

    THIS IS THE CORRECT TOOL for mRS outcome data. It queries the cohort table
    (db_5, mRS_calculated) with death imputation (mRS=6 for patients who died
    before the follow-up period but have no cohort row).

    DO NOT use query_data() with 'admission_mrs_3month' — that is a quick-note
    field, NOT the authoritative outcome.

    Available periods: 3m, 6m, 9m, 12m, 2y, 3y, 4y, 5y, 6y, 7y, 8y, 9y, 10y

    For date filtering, use 'adm_date' (admission date), NOT 'onset_hospital_arrival'.

    Args:
        hospital_code: Hospital code (e.g., 'YSU')
        period: Follow-up period code (default '3m')
        additional_variables: Optional list of other variables to include
                              (e.g., ['pt_sex', 'pt_age', 'Thr_mechanical'])
        filters: JSON string of filters on the patient/admission variables,
                 e.g., '[{"variable":"Thr_mechanical","operator":"=","value":"1"}]'
        limit: Max rows (default 5000)
    """
    _require_auth()
    filter_list = _parse_filters(filters)
    body = {
        "hospital": hospital_code,
        "period": period,
        "variables": additional_variables or [],
        "filters": filter_list,
        "limit": max(1, min(limit, 20000)),
    }
    result = api_client.post("/query/followup", json_body=body)

    columns = result["columns"]
    rows = result["rows"]
    stats = result.get("stats", {})
    period_label = result.get("period_label", period)

    lines = [
        f"Follow-up mRS at {period_label}",
        f"Hospital: {result.get('hospital', hospital_code)}",
        f"Period: {result.get('period', period)}",
        f"Total patients: {result['row_count']}",
    ]

    if result.get("note"):
        lines.append(f"Note: {result['note']}")

    if stats:
        lines.append(f"  From cohort table: {stats.get('from_cohort', 0)}")
        imputed = stats.get("imputed_death", 0)
        if imputed:
            lines.append(f"  Imputed mRS=6 (died, no cohort row): {imputed}")

    lines.append("")
    lines.append(_format_table(rows, columns))

    if stats and stats.get("mrs_distribution"):
        lines.append(f"\n--- mRS Distribution ({period_label}) ---")
        mrs_dist = stats["mrs_distribution"]
        total = sum(mrs_dist.values())
        for score in sorted(mrs_dist.keys()):
            n = mrs_dist[score]
            pct = n / max(total, 1) * 100
            bar = "#" * int(pct / 2)
            lines.append(f"  mRS {score}: {n:>5} ({pct:5.1f}%) {bar}")
        lines.append(f"  Total: {total}")

        if stats.get("good_outcome_0_2") is not None:
            lines.append(f"  Good outcome (mRS 0-2): {stats['good_outcome_0_2']} ({stats['good_outcome_pct']:.1f}%)")
            lines.append(f"  Poor outcome (mRS 3-6): {stats['poor_outcome_3_6']} ({stats['poor_outcome_pct']:.1f}%)")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Export Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def export_xlsx(
    hospital_code: str,
    variables: list[str],
    filters: str = "",
    filename: str = "",
    limit: int = 20000,
) -> str:
    """Export patient data to an XLSX file.

    Creates an Excel file with the requested variables as columns.
    The file is saved to the current working directory.

    For mRS outcome exports, use export_followup_xlsx() instead.

    Args:
        hospital_code: Hospital code (e.g., 'YSU')
        variables: List of variable names to include as columns
        filters: JSON string of filters (same as query_data)
        filename: Output filename (auto-generated if empty)
        limit: Max rows (default 20000)
    """
    _require_auth()
    filter_list = _parse_filters(filters)
    body = {
        "hospital": hospital_code,
        "variables": variables,
        "filters": filter_list,
        "filename": filename,
        "limit": max(1, min(limit, 50000)),
    }
    content, fname = api_client.download("/export/xlsx", json_body=body)
    fname = os.path.basename(fname)
    if not fname or fname.startswith('.'):
        fname = "download.xlsx"
    save_path = os.path.join(os.getcwd(), fname)
    with open(save_path, "wb") as f:
        f.write(content)
    size_kb = len(content) / 1024
    return (
        f"Export complete!\n"
        f"  File: {save_path}\n"
        f"  Size: {size_kb:.1f} KB\n"
        f"  Hospital: {hospital_code}\n"
        f"  Variables: {', '.join(variables)}"
    )


@mcp.tool()
async def export_followup_xlsx(
    hospital_code: str,
    period: str = "3m",
    additional_variables: list[str] | None = None,
    filters: str = "",
    filename: str = "",
    limit: int = 20000,
) -> str:
    """Export mRS follow-up outcomes from the COHORT TABLE to an XLSX file.

    THIS IS THE CORRECT WAY to export patient outcomes. Uses the cohort table
    (db_5, mRS_calculated) with death imputation.

    The file is saved to the current working directory.

    Args:
        hospital_code: Hospital code (e.g., 'YSU')
        period: Follow-up period (3m, 6m, 12m, 2y, etc.)
        additional_variables: Extra variables to include (e.g., ['pt_sex', 'pt_age'])
        filters: JSON string of filters
        filename: Output filename (auto-generated if empty)
        limit: Max rows (default 20000)
    """
    _require_auth()
    filter_list = _parse_filters(filters)
    body = {
        "hospital": hospital_code,
        "period": period,
        "variables": additional_variables or [],
        "filters": filter_list,
        "limit": max(1, min(limit, 50000)),
    }
    result = api_client.post("/query/followup", json_body=body)

    columns = result.get("columns", [])
    rows = result.get("rows", [])
    stats = result.get("stats", {})
    period_label = result.get("period_label", period)

    if not rows:
        return f"No patients found with {period_label} follow-up mRS data."

    # Write XLSX
    import csv
    import io

    if not filename:
        import datetime
        code = result.get("hospital", hospital_code)
        period_key = result.get("period", period)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{code}_followup_mRS_{period_key}_{ts}.csv"

    # Use CSV since we don't want pandas as a dependency
    if filename.endswith(".csv"):
        save_path = os.path.join(os.getcwd(), filename)
        with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    else:
        # Try xlsx via openpyxl if available
        try:
            from openpyxl import Workbook
            save_path = os.path.join(os.getcwd(), filename)
            wb = Workbook()
            ws = wb.active
            ws.append(columns)
            for row in rows:
                ws.append([row.get(c) for c in columns])
            wb.save(save_path)
        except ImportError:
            # Fallback to CSV
            filename = filename.rsplit(".", 1)[0] + ".csv"
            save_path = os.path.join(os.getcwd(), filename)
            with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)

    size_kb = os.path.getsize(save_path) / 1024

    lines = [
        "Follow-up export complete!",
        f"  File: {save_path}",
        f"  Size: {size_kb:.1f} KB",
        f"  Hospital: {result.get('hospital', hospital_code)}",
        f"  Period: {period_label}",
        f"  Total rows: {len(rows)}",
    ]
    if stats:
        lines.append(f"  From cohort: {stats.get('from_cohort', 0)}")
        imputed = stats.get("imputed_death", 0)
        if imputed:
            lines.append(f"  Death imputed: {imputed} (mRS=6)")

    if stats and stats.get("mrs_distribution"):
        lines.append(f"\n--- mRS Distribution ({period_label}) ---")
        mrs_dist = stats["mrs_distribution"]
        total = sum(mrs_dist.values())
        for score in sorted(mrs_dist.keys()):
            n = mrs_dist[score]
            pct = n / max(total, 1) * 100
            lines.append(f"  mRS {score}: {n:>5} ({pct:5.1f}%)")
        if stats.get("good_outcome_0_2") is not None:
            lines.append(f"  Good (mRS 0-2): {stats['good_outcome_0_2']} ({stats['good_outcome_pct']:.1f}%)")
            lines.append(f"  Poor (mRS 3-6): {stats['poor_outcome_3_6']} ({stats['poor_outcome_pct']:.1f}%)")

    return "\n".join(lines)


@mcp.tool()
async def list_exports() -> str:
    """List all previously exported XLSX files on the server."""
    _require_auth()
    result = api_client.get("/export/list")
    if not result:
        return "No exported files found on the server."
    lines = [f"Exported files ({len(result)}):", ""]
    for i, f in enumerate(result, 1):
        lines.append(f"  {i}. {f['filename']}  {f.get('size_human', '')}  {f.get('modified', '')}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Anonymization Lookup Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def list_anonymized_tables(hospital_code: str) -> str:
    """List tables that have anonymization enabled for a hospital.
    These tables store patient identity (chart number, name) in a separate
    anonymization table rather than in the data tables themselves.

    Args:
        hospital_code: Hospital code (e.g., 'KMU') or hidx number
    """
    _require_auth()
    result = api_client.get(f"/anon/tables/{hospital_code}")
    if not result:
        return f"No anonymized tables found for hospital '{hospital_code}'."
    lines = [f"Anonymized tables for {hospital_code} ({len(result)} found)", ""]
    for t in result:
        lines.append(
            f"  {t['table_name']:<10s}  dbidx={t['dbidx']:<5}  {t.get('dbname', '')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def lookup_patient(
    hospital_code: str,
    query: str,
    field: str = "chart",
    table: str = "",
) -> str:
    """Look up a patient's real identity (chart number, name) from the
    anonymization table. Requires Manager or Super Admin access.

    Use this when you need to find a patient by their hospital chart number,
    name, or anonymized registry ID.

    Args:
        hospital_code: Hospital code (e.g., 'KMU') or hidx number
        query: Search value (chart number, name, or reg_num)
        field: Which field to search: 'chart' (chart number, default),
               'name' (patient name), 'id' (anonymized reg_num)
        table: Optional table filter (e.g., 'db_113') to restrict search
    """
    _require_auth()
    field_map = {"chart": "data1", "name": "data2", "id": "reg_num"}
    api_field = field_map.get(field, "data1")

    body = {
        "hospital": hospital_code,
        "query": query,
        "field": api_field,
        "table": table,
        "limit": 20,
    }
    result = api_client.post("/anon/lookup", json_body=body)

    if not result:
        return f"No matches found for '{query}' (field={field}) in hospital '{hospital_code}'."

    lines = [
        f"Anonymization lookup: '{query}' (field={field}) in {hospital_code}",
        f"Matches: {len(result)}",
        "",
    ]

    columns = ["table", "reg_num", "chart#", "name", "sex", "age"]
    lines.append(" | ".join(f"{c:<12s}" for c in columns))
    lines.append("-+-".join("-" * 12 for _ in columns))

    for r in result:
        pd = r.get("patient_data") or {}
        vals = [
            r.get("table_name", ""),
            str(r.get("reg_num", "")),
            str(r.get("data1", "")),
            str(r.get("data2", "")),
            str(pd.get("pt_sex", "")),
            str(pd.get("pt_age", "")),
        ]
        lines.append(" | ".join(f"{v:<12s}" for v in vals))

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Clot Composition Tools (ARIA)
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def get_clot_composition(hospital_code: str, thrombus_code: str) -> str:
    """Get thrombus/clot composition (stain ratios) for a specific thrombus sample.
    Shows what the blood clot retrieved during thrombectomy is made of.

    Each stain targets different components:
    - CD42b: Platelets
    - Fibrinogen: Fibrin
    - GlycophorinA: Red blood cells (RBC)
    - MPO: Neutrophils
    - TissueFactor: Tissue factor
    - HisH3: NETs (Neutrophil Extracellular Traps)
    - CD68: Macrophages
    - H&E: General histology

    Args:
        hospital_code: Hospital code (e.g., 'YSU')
        thrombus_code: Thrombus code (e.g., 'YSU001' or just '001')
    """
    _require_auth()
    result = api_client.get(f"/clot/composition/{hospital_code}/{thrombus_code}")

    if not result:
        return f"No clot composition data found for thrombus '{thrombus_code}' in hospital '{hospital_code}'."

    thrombus = result.get("thrombus_code", thrombus_code)
    patient = result.get("patient_code", "")
    stains = result.get("stains", [])

    lines = [
        f"Clot Composition — Thrombus: {thrombus}",
        f"  Patient: {patient}" if patient else "",
        "",
    ]
    lines = [l for l in lines if l or l == ""]

    if not stains:
        lines.append("  (no stain data available)")
    else:
        for s in stains:
            name = s.get("stain", "")
            ratio = s.get("ratio")
            if ratio is not None:
                lines.append(f"  {name:<20s}  {ratio}")
            else:
                lines.append(f"  {name:<20s}  (no data)")

    return "\n".join(lines)


@mcp.tool()
async def search_clot_data(hospital_code: str, query: str, field: str = "patient_code") -> str:
    """Search for thrombus/clot data by patient chart number or thrombus code.

    Args:
        hospital_code: Hospital code (e.g., 'YSU')
        query: Search value (patient chart number or thrombus code)
        field: Field to search: 'patient_code' (default) or 'thrombus_code'
    """
    _require_auth()
    body = {
        "hospital": hospital_code,
        "query": query,
        "field": field,
        "limit": 20,
    }
    result = api_client.post("/clot/search", json_body=body)

    if not result:
        return f"No clot data found for '{query}' (field={field}) in hospital '{hospital_code}'."

    lines = [
        f"Clot search: '{query}' (field={field}) in {hospital_code}",
        f"Matches: {len(result)}",
        "",
    ]

    columns = ["thrombus_code", "patient_code"]
    lines.append(_format_table(result, columns))

    return "\n".join(lines)


@mcp.tool()
async def list_clot_patients(hospital_code: str) -> str:
    """List all thrombus/clot patients for a hospital.
    Shows patients who had clot samples collected during endovascular thrombectomy.

    Args:
        hospital_code: Hospital code (e.g., 'YSU', 'KMU')
    """
    _require_auth()
    result = api_client.get(f"/clot/patients/{hospital_code}")

    if not result:
        return f"No clot patients found for hospital '{hospital_code}'."

    lines = [
        f"Clot patients for {hospital_code} ({len(result)} found)",
        "",
    ]

    columns = ["thrombus_code", "patient_code"]
    lines.append(_format_table(result, columns))

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _parse_filters(filters_json: str) -> list[dict]:
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


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    mcp.run()


if __name__ == "__main__":
    main()
