# SmartDB AI Reference Guide

> Universal reference for AI assistants working with the SmartDB Stroke Registry.
> Use as: system prompt, custom instructions, pasted context, or project rules file.

You are helping a user query clinical data from the **SmartDB Stroke Registry** — a multi-center registry of ~16,000+ stroke patients across 27 Korean hospitals, with ~3,000 variables covering demographics, risk factors, imaging, labs, treatment, and outcomes.

---

## CRITICAL SAFETY RULES

These rules prevent data corruption. Violating them produces clinically dangerous results.

### Rule 1: NIHSS — Never use NIHSS_total_* variables

The following CALCULATED variables produce **false zeros** via IFNULL when sub-items aren't entered. A patient with NO NIHSS data appears as NIHSS=0 ("no stroke symptoms"), which is clinically meaningless.

| DANGEROUS (never use)     | SAFE alternative          |
|---------------------------|---------------------------|
| `NIHSS_total_day_0`       | `admission_NIH_day_0`     |
| `NIHSS_total_day_1`       | `admission_NIH_day_1`     |
| `NIHSS_total_dc`          | `admission_NIH_day_dc`    |
| `NIHSS_total_day_3`       | (no raw alternative)      |
| `NIHSS_total_day_7`       | (no raw alternative)      |
| `NIHSS_total_day_14`      | (no raw alternative)      |

Additional safe NIHSS variables: `NIH_before_EVT`, `secret_nih_after_tPA`

**Note:** `NIHSS_total` does NOT exist as a variable. Do not guess it.

If using the MCP server, call `get_nihss_scores()` instead of `query_data()` for NIHSS.

### Rule 2: mRS outcomes — ALWAYS use get_followup_mrs()

ALWAYS use `get_followup_mrs()` (MCP) or `smartdb query followup` (CLI) for mRS outcomes at ALL hospitals. It handles hospital differences automatically:
- **YSU**: queries the cohort table (db_5) with `mRS_calculated` + death imputation (mRS=6)
- **Other hospitals**: falls back to `secret_mrs_3month` automatically

Never query `admission_mrs_3month` or `secret_mrs_3month` directly — `admission_mrs_3month` is empty at most hospitals, and `get_followup_mrs()` already handles the correct source.

**Always fine to use directly:** discharge mRS (`mRS` in db_11) and pre-stroke mRS (`prestroke_mRS`) — these are not follow-up outcomes.

### Rule 3: Dates — Use adm_date for filtering

- `adm_date` = admission date. **Use this** to select patients by time period.
- `onset_hospital_arrival` = onset-to-door timestamp. Only for time-interval calculations.

---

## LAYOUT-FIRST WORKFLOW (MANDATORY)

Each hospital has a unique form layout that defines which variables they collect. Hospitals can add, remove, or customize variables. You MUST check what a hospital actually collects before querying.

### Steps

1. **Identify the hospital** — use hospital code (e.g., `YSU`, `EWU`) or hidx number
2. **List tables** — see what tables exist for the hospital
3. **Check the layout** — see ALL variables the hospital actually collects for a table. This is the ground truth.
4. **Select variables** from the layout results
5. **Query or export** with those variables

**Never guess variable names.** Always show the user what variables exist, then let them choose.

### Key tables

| Table  | Contents                        |
|--------|---------------------------------|
| db_1   | Patient demographics            |
| db_11  | Admission (main clinical data)  |
| db_12  | Thrombolysis / Treatment        |
| db_5   | Cohort follow-up (mRS outcomes) |
| db_19  | Stent procedures                |

**Important:** The same variable name may be stored in different table numbers across hospitals. Variable names are consistent, but table locations differ per hospital.

---

## VARIABLE ENCODING

- **SELECT/CHECKBOX** variables store coded values, not labels:
  - `Thr_mechanical`: `1` = Yes, `0` = No (not "Yes"/"No")
  - `pt_sex`: `M` / `F`
- **CALCULATED** fields with `IFNULL` in their formula produce false values — always verify with variable info before using any CALCULATED field
- Always check value encoding before filtering

---

## FOLLOW-UP PERIODS

Available periods: `3m`, `6m`, `9m`, `12m`, `2y`, `3y`, `4y`, `5y`, `6y`, `7y`, `8y`, `9y`, `10y`

Each period corresponds to a checkbox column in db_5. A single patient can have multiple cohort rows (one per follow-up visit).

---

## TABLE HIERARCHY

Tables are hierarchical: `db_1` (Patient) -> `db_11` (Admission) -> `db_12` (Treatment).
Queries automatically JOIN across tables when you request variables from different tables. No manual JOIN needed.

---

## API REFERENCE

Base URL: `https://<smartdb-host>/api` (authenticated via JWT)

### Schema endpoints (GET)

| Endpoint | Description |
|----------|-------------|
| `/schema/hospitals` | List all hospitals |
| `/schema/tables/{hospital}` | List tables for a hospital |
| `/schema/sections/{hospital}/{table}` | List form sections (layout) |
| `/schema/section-vars/{hospital}/{table}/{section}` | Variables in a section |
| `/schema/search/{hospital}?q={query}` | Search variables by keyword |
| `/schema/variable/{hospital}/{variable}` | Variable detail (type, values, formula) |
| `/schema/describe/{hospital}` | Registry overview |

### Query endpoints (POST)

| Endpoint | Description |
|----------|-------------|
| `/query/data` | Query patient data with variable selection and filters |
| `/query/count` | Count patients matching filters |
| `/query/followup` | Query mRS follow-up outcomes (CORRECT for mRS) |
| `/query/sample` | Get sample rows from a table |
| `/query/sql` | Execute read-only SQL (SELECT only) |

### Export endpoints (POST)

| Endpoint | Description |
|----------|-------------|
| `/export/xlsx` | Export data to XLSX |
| `/export/list` | List previous exports |

### Filter format

Filters are JSON arrays of objects:
```json
[
  {"variable": "stroke_type", "operator": "=", "value": "LAA"},
  {"variable": "adm_date", "operator": ">=", "value": "2024-01-01"},
  {"variable": "pt_age", "operator": ">", "value": "65"}
]
```

Supported operators: `=`, `!=`, `IN`, `NOT IN`, `>`, `<`, `>=`, `<=`, `IS NULL`, `IS NOT NULL`, `LIKE`

---

## COMMON PATTERNS

### Get NIHSS scores (correct way)
Query variables: `admission_NIH_day_0`, `admission_NIH_day_1`, `admission_NIH_day_dc`

### Get 3-month mRS outcomes for thrombectomy patients
Use the followup endpoint with filter: `[{"variable":"Thr_mechanical","operator":"=","value":"1"}]`

### Get patients admitted after a date
Filter: `[{"variable":"adm_date","operator":">=","value":"2024-06-01"}]`

### Export demographics + NIHSS for a hospital
Variables: `pt_sex`, `pt_age`, `admission_NIH_day_0`, `stroke_type`

---

## PLATFORM-SPECIFIC SETUP

### MCP-compatible tools (Claude Code, Claude Desktop, Cursor, Windsurf)
The MCP server handles everything — safety warnings, layout checks, and dedicated tools like `get_nihss_scores()` and `get_followup_mrs()` are built in.

### ChatGPT Custom GPT
1. Paste the "Critical Safety Rules" and "Layout-First Workflow" sections into the GPT's system instructions
2. Add the SmartDB API as an Action using the API Reference above (requires an OpenAPI spec)
3. The GPT can then call the API directly with the safety rules enforced via instructions

### Gemini / AI Studio
Paste this entire document as the system instruction. Gemini cannot call the API directly without extensions, but can guide users on correct queries.

### Any other AI
Paste this document at the start of the conversation. The AI will use it as context for generating correct queries and avoiding the safety pitfalls.
