# SmartDB CLI — AI Agent Guide

> **Purpose**: This document is a comprehensive reference for AI agents that use the `smartdb` CLI to query, analyze, and export data from the SmartDB stroke registry database.

## Architecture

The SmartDB system uses a **client-server architecture**:

- **SmartDB API Server** (`smartdb-api`): A FastAPI backend that holds all database credentials server-side and enforces authentication + permissions. Deployed behind nginx.
- **SmartDB CLI** (`smartdb-cli`): A thin HTTP client (Typer + httpx) that communicates with the API server. No database credentials are stored on the client.

```
CLI (httpx) ──► API Server (FastAPI) ──► MySQL Database
   JWT auth        permissions check       cloud-managed
```

---

## Quick Start

```bash
# Run from the project directory
cd /Volumes/eDrive/LocalDev/ai-researcher/agent/smartdb-cli

# Step 0: Configure the API server URL (only needed once, or if server changes)
python -m smartdb_cli.main config set-url http://your-api-server:8000

# Step 1: Log in (required for all commands)
python -m smartdb_cli.main login

# Step 2: Use any command
python -m smartdb_cli.main <group> <command> [ARGS] [OPTIONS]

# Top-level commands:
python -m smartdb_cli.main login         # Log in with email/password
python -m smartdb_cli.main logout        # Log out
python -m smartdb_cli.main whoami        # Show current user info + token status
python -m smartdb_cli.main config show   # Show current configuration
python -m smartdb_cli.main config set-url URL  # Set API server URL

# Three command groups:
python -m smartdb_cli.main schema ...    # Explore hospitals, tables, variables
python -m smartdb_cli.main query ...     # Query patient data
python -m smartdb_cli.main export ...    # Export to XLSX files
```

> **Authentication required**: All `schema`, `query`, and `export` commands require login. Run `smartdb login` first.

---

## Configuration

The CLI stores configuration in `~/.smartdb/`:

| File | Purpose |
|------|---------|
| `~/.smartdb/config.json` | API URL and other settings |
| `~/.smartdb/session.json` | JWT token and user info (restricted permissions) |

### API URL Resolution Order

1. `SMARTDB_API_URL` environment variable
2. `~/.smartdb/config.json` → `api_url` field
3. Default: `http://localhost:8000`

```bash
# Set via CLI
python -m smartdb_cli.main config set-url http://smartdb-api.example.com

# Or via environment variable
export SMARTDB_API_URL=http://smartdb-api.example.com
```

---

## Authentication & Access Control

### How Auth Works

1. `smartdb login` prompts for email/password
2. CLI sends credentials to `POST /auth/login` on the API server
3. Server verifies against the `users` table (MD5 password hashing)
4. Server returns a JWT token
5. CLI stores the token in `~/.smartdb/session.json`
6. All subsequent requests include the token in `Authorization: Bearer <token>` headers
7. Server validates the token and enforces permissions on every request

### User Levels

| Level | Role | Hospital Access | Data Access |
|-------|------|----------------|-------------|
| **3** | Super Admin | All hospitals | Full access to everything |
| **2** | Manager | Own hospital only | Full read/write/export for their hospital |
| **1** | User | Own hospital only | Per-registry permissions (read/write/export controlled individually) |

### Login / Logout / Session

```bash
# Log in (prompts for email and password)
python -m smartdb_cli.main login

# Check who you're logged in as (also validates token with server)
python -m smartdb_cli.main whoami

# Log out (deletes local session)
python -m smartdb_cli.main logout
```

### Token Expiration

Tokens expire after a server-configured duration (default: 24 hours). If your token expires:
- Commands will return a "session expired" error
- Run `smartdb login` again to get a new token
- `smartdb whoami` shows token validity status

### Access Control Behavior

- **Level 3 users**: See all 27 hospitals, can query any hospital
- **Level 1/2 users**: Only see their own hospital in `schema hospitals`, get "Access denied" if they try to query another hospital
- **Level 1 users**: Per-registry permissions from the `user_permissions` table control read/export access to specific databases

### Example: Access Denied

```bash
# Level 1 user at hospital H17 tries to access YSU:
$ python -m smartdb_cli.main schema tables YSU
Error: Access denied to hospital 'YSU'. Your allowed hospitals: H17
```

---

## What This Database Contains

The SmartDB database is a **multi-hospital clinical registry for stroke patients** in South Korea.

- **27 hospitals** (identified by hospital code like `YSU` or numeric `hidx` like `1`)
- **~16,000+ patients** (at the largest hospital, YSU)
- **~3,000 clinical variables** covering: demographics, risk factors, imaging, lab results, treatment details, outcomes, and follow-up
- **MySQL database** with hierarchical table structure

---

## Recommended Workflow

When you need to answer a clinical research question, follow this workflow:

### Step 1: Identify the hospital

```bash
python -m smartdb_cli.main schema hospitals
```

This lists all 27 hospitals with their codes, names, and variable counts. Most research targets **YSU** (Yonsei Severance, hidx=1) as it has the richest data (~16,000 patients, ~1,956 variables).

### Step 2: Find relevant variables

```bash
# Search by keyword (supports Korean and English)
python -m smartdb_cli.main schema search YSU "hypertension"
python -m smartdb_cli.main schema search YSU "NIHSS"
python -m smartdb_cli.main schema search YSU "sex"
python -m smartdb_cli.main schema search YSU "age"
```

The search uses fuzzy matching with scoring. Results include the variable key, label, table, type, and match score.

### Step 3: Understand variable details

```bash
# Get exact variable info including value mappings
python -m smartdb_cli.main schema variable YSU pt_sex
python -m smartdb_cli.main schema variable YSU Hypertension_existence
```

This shows the variable type, which table it lives in, and — critically for SELECT/RADIO/CHECKBOX types — the **value map** showing what DB-stored values mean (e.g., DB value `1` = "Yes", DB value `0` = "No").

### Step 4: Query the data

```bash
# Count patients matching criteria
python -m smartdb_cli.main query count YSU --filters '[{"variable":"pt_sex","operator":"=","value":"M"}]'

# Query data with specific variables
python -m smartdb_cli.main query data YSU --vars "pt_sex,pt_age,NIHSS_total" --limit 500

# Query with filters
python -m smartdb_cli.main query data YSU \
  --vars "pt_sex,pt_age,NIHSS_total,stroke_type" \
  --filters '[{"variable":"pt_sex","operator":"=","value":"M"},{"variable":"pt_age","operator":">","value":"65"}]' \
  --limit 1000
```

### Step 5: Export for analysis

```bash
# Export to Excel
python -m smartdb_cli.main export xlsx YSU \
  --vars "pt_sex,pt_age,NIHSS_total,stroke_type,Hypertension_existence" \
  --filename "my_analysis" \
  --limit 20000
```

---

## All Commands Reference

### Auth Commands

#### `login`

Log in to the SmartDB registry. Prompts for email and password interactively.

```bash
python -m smartdb_cli.main login
```

**Output on success**: Welcome message with user name, level, hospital.
**Output on failure**: "Invalid email or password."

---

#### `logout`

Clear the current session.

```bash
python -m smartdb_cli.main logout
```

---

#### `whoami`

Show the currently logged-in user's details and validate the token with the server.

```bash
python -m smartdb_cli.main whoami
```

**Output**: Panel showing name, email, level (User/Manager/Super Admin), hospital hidx, description, login time, and token validity status.

---

### Config Commands

#### `config set-url URL`

Set the API server URL.

```bash
python -m smartdb_cli.main config set-url http://smartdb-api.example.com:8000
```

---

#### `config show`

Show current configuration (API URL, config/session file paths, export directory, login status).

```bash
python -m smartdb_cli.main config show
```

---

### Schema Commands

#### `schema hospitals`

List all hospitals in the registry.

```bash
python -m smartdb_cli.main schema hospitals
```

**Output columns**: Code, Name, HIDX, Variables, Root Tables

---

#### `schema tables HOSPITAL`

List all tables for a hospital with hierarchy.

```bash
python -m smartdb_cli.main schema tables YSU
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `HOSPITAL` | string | Yes | Hospital code (e.g., `YSU`) or hidx number (e.g., `1`) |

**Output columns**: Table (with tree-like indentation), dbidx, Variables, Rows, Parent

---

#### `schema search HOSPITAL QUERY`

Fuzzy-search for variables by name or label.

```bash
python -m smartdb_cli.main schema search YSU "stroke" --limit 10
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `HOSPITAL` | string | Yes | — | Hospital code or hidx |
| `QUERY` | string | Yes | — | Search keyword (English or Korean) |
| `--limit`, `-n` | int | No | 20 | Max results |

**Scoring**: Exact key match = 100pts, substring in key = ~50pts, substring in label = ~40pts.

**Output columns**: #, Key, Column, Label, Table, Type, Score

---

#### `schema variable HOSPITAL VARIABLE`

Get detailed info for a specific variable.

```bash
python -m smartdb_cli.main schema variable YSU pt_sex
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `HOSPITAL` | string | Yes | Hospital code or hidx |
| `VARIABLE` | string | Yes | Exact variable key (e.g., `pt_sex`, `NIHSS_total`) |

**Output**: Panel showing key, column, table, label, type, options. For SELECT/RADIO/CHECKBOX types, also shows a value map table (DB Value → Label).

**If not found**: Performs fuzzy search and suggests up to 5 alternatives.

---

#### `schema table-vars HOSPITAL TABLE`

List all variables in a specific table.

```bash
python -m smartdb_cli.main schema table-vars YSU db_11 --limit 100
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `HOSPITAL` | string | Yes | — | Hospital code or hidx |
| `TABLE` | string | Yes | — | Table name (e.g., `db_1`, `db_11`) |
| `--limit`, `-n` | int | No | 50 | Max variables to show |

**Output columns**: #, Key, Column, Type, Label

---

#### `schema describe HOSPITAL`

Full registry overview with hierarchy tree and statistics.

```bash
python -m smartdb_cli.main schema describe YSU
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `HOSPITAL` | string | Yes | Hospital code or hidx |

**Output**: Hospital summary panel, table hierarchy tree, variable distribution table, variable types breakdown.

---

### Query Commands

#### `query data HOSPITAL`

Query patient data with automatic table JOINs.

```bash
python -m smartdb_cli.main query data YSU \
  --vars "pt_sex,pt_age,NIHSS_total" \
  --filters '[{"variable":"pt_sex","operator":"=","value":"M"}]' \
  --limit 500
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `HOSPITAL` | string | Yes | — | Hospital code or hidx |
| `--vars`, `-v` | string | **Yes** | — | Comma-separated variable names |
| `--filters`, `-f` | string | No | `""` | JSON filter string (see Filter Format) |
| `--limit`, `-n` | int | No | 100 | Max rows (max 5,000) |

**Output**: Data table with all queried variables, plus summary statistics per column (mean/median/min/max for numeric; unique counts for categorical).

**Important**: The first column is always `patient_id` (the root table's `db_idx`).

---

#### `query count HOSPITAL`

Count patients matching criteria.

```bash
python -m smartdb_cli.main query count YSU
python -m smartdb_cli.main query count YSU --filters '[{"variable":"pt_sex","operator":"=","value":"F"}]'
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `HOSPITAL` | string | Yes | — | Hospital code or hidx |
| `--filters`, `-f` | string | No | `""` | JSON filter string |

**Output**: Patient count (formatted with commas).

---

#### `query sql QUERY`

Execute raw read-only SQL.

```bash
python -m smartdb_cli.main query sql "SELECT pt_sex, COUNT(*) as cnt FROM smartdb.db_1 WHERE hidx=1 GROUP BY pt_sex"
```

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `QUERY` | string | Yes | SQL SELECT query |

**Restrictions**:
- Only `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN` allowed
- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE` etc. are blocked
- Auto-adds `LIMIT 1000` if no LIMIT clause present
- Server enforces hospital-level access based on user permissions

**Output**: Rich table of results.

---

#### `query sample HOSPITAL TABLE`

Get sample rows to understand a table's data format.

```bash
python -m smartdb_cli.main query sample YSU db_11 --rows 3
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `HOSPITAL` | string | Yes | — | Hospital code or hidx |
| `TABLE` | string | Yes | — | Table name (must be `db_N` format) |
| `--rows`, `-n` | int | No | 5 | Number of rows (max 20) |

**Output**: Lists registered variables for the table, then shows sample data rows with all columns.

---

#### `query followup HOSPITAL`

Get follow-up mRS scores with death imputation.

```bash
python -m smartdb_cli.main query followup YSU --period 3m --vars "pt_age,pt_sex" --limit 5000
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `HOSPITAL` | string | Yes | — | Hospital code |
| `--period`, `-p` | string | No | `3m` | Follow-up period (see table below) |
| `--vars`, `-v` | string | No | — | Additional variables to include |
| `--filters`, `-f` | string | No | `""` | JSON filter string |
| `--limit`, `-n` | int | No | 5000 | Max rows (max 20,000) |

**Valid periods**: `3m`, `6m`, `9m`, `12m`, `2y`, `3y`, `4y`, `5y`, `6y`, `7y`, `8y`, `9y`, `10y`

**Death imputation**: Patients who died before the follow-up period but have no recorded follow-up visit get **mRS=6** (dead). The `source` column shows `"cohort"` for actual visits and `"imputed_death"` for imputed records.

**Output**: Data table with patient_id, mRS score, follow-up date, source, additional variables. Includes mRS distribution statistics with counts and percentages per score.

---

### Export Commands

#### `export xlsx HOSPITAL`

Export queried data to an XLSX file.

```bash
python -m smartdb_cli.main export xlsx YSU \
  --vars "pt_sex,pt_age,NIHSS_total,stroke_type" \
  --filename "stroke_analysis" \
  --limit 20000
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `HOSPITAL` | string | Yes | — | Hospital code |
| `--vars`, `-v` | string | **Yes** | — | Comma-separated variable names |
| `--filters`, `-f` | string | No | `""` | JSON filter string |
| `--filename`, `-o` | string | No | auto-generated | Output filename |
| `--limit`, `-n` | int | No | 20,000 | Max rows (max 50,000) |

**Default filename**: `export_{hospital}_{YYYYMMDD_HHMMSS}.xlsx`

**Save location**: `{project}/exports/` directory

**Output**: File path, size, row/column count, per-column statistics.

---

#### `export merge EXISTING_FILE HOSPITAL`

Add new database columns to an existing XLSX file.

```bash
python -m smartdb_cli.main export merge exports/export_YSU_20240101.xlsx YSU \
  --vars "Hypertension_existence,DM_existence" \
  --match-column "patient_id"
```

| Argument/Option | Type | Required | Default | Description |
|----------------|------|----------|---------|-------------|
| `EXISTING_FILE` | string | Yes | — | Path to XLSX (relative to exports/ or absolute) |
| `HOSPITAL` | string | Yes | — | Hospital code |
| `--vars`, `-v` | string | **Yes** | — | New variables to add |
| `--match-column`, `-m` | string | No | `patient_id` | Column in XLSX to match on |
| `--db-match-variable` | string | No | `""` | DB variable to match against (default: db_idx) |

**Output filename**: `{original}_merged_{timestamp}.xlsx`

**Output**: Matched/unmatched row counts, new columns added, file path.

---

#### `export list`

List previously exported XLSX files.

```bash
python -m smartdb_cli.main export list
```

**Output columns**: #, Filename, Size, Modified. Sorted newest first.

---

## Filter Format

Filters are JSON strings passed to `--filters` / `-f`. They can be a single object or an array.

### Single filter

```bash
--filters '{"variable":"pt_sex","operator":"=","value":"M"}'
```

### Multiple filters (AND logic)

```bash
--filters '[
  {"variable":"pt_sex","operator":"=","value":"M"},
  {"variable":"pt_age","operator":">","value":"65"},
  {"variable":"stroke_type","operator":"IN","value":["LAA","CE"]}
]'
```

### Supported operators

| Operator | Value Type | Example |
|----------|-----------|---------|
| `=` | string/number | `{"variable":"pt_sex","operator":"=","value":"M"}` |
| `!=` | string/number | `{"variable":"pt_sex","operator":"!=","value":"F"}` |
| `>` | number | `{"variable":"pt_age","operator":">","value":"65"}` |
| `<` | number | `{"variable":"pt_age","operator":"<","value":"50"}` |
| `>=` | number | `{"variable":"NIHSS_total","operator":">=","value":"15"}` |
| `<=` | number | `{"variable":"NIHSS_total","operator":"<=","value":"5"}` |
| `LIKE` | string | `{"variable":"diagnosis","operator":"LIKE","value":"%infarct%"}` |
| `IN` | array | `{"variable":"stroke_type","operator":"IN","value":["LAA","CE"]}` |
| `NOT IN` | array | `{"variable":"stroke_type","operator":"NOT IN","value":["UND"]}` |
| `IS NULL` | (none) | `{"variable":"pt_age","operator":"IS NULL"}` |
| `IS NOT NULL` | (none) | `{"variable":"pt_age","operator":"IS NOT NULL"}` |

### Important notes on filter values

- **For SELECT/RADIO/CHECKBOX variables**: Use the **DB-stored value** (from `option2`), NOT the display label. Check with `schema variable` first.
  - Example: If `Hypertension_existence` has value_map `{1: "Yes", 0: "No"}`, filter with `"value":"1"`, not `"value":"Yes"`.
- **For IN/NOT IN**: Value can be a JSON array or comma-separated string.
- **All values are converted to strings** in the SQL query.

---

## Database Structure — Key Concepts

### Table hierarchy

Tables are organized in parent-child trees. Each hospital has one or more **root tables** (patient-level, one row per patient). Child tables link via `child.parent = parent.db_idx`.

```
db_1 (Patient — root)            ← Demographics, baseline info
├── db_5 (Cohort)                 ← Follow-up data (one row per visit)
├── db_11 (Admission)             ← Main clinical data (779 variables!)
│   └── db_12 (Thrombolysis)      ← Acute treatment details
└── db_19 (Stent)                 ← Stent procedures
```

**The CLI handles JOINs automatically.** When you query variables from different tables, the API server builds the correct LEFT JOIN chain.

### Key tables for YSU (the main hospital)

| Table | Name | Rows | Variables | Use for |
|-------|------|------|-----------|---------|
| `db_1` | Patient | 16,830 | 32 | **Demographics**: age, sex, death date |
| `db_5` | Cohort | 32,949 | 200 | **Follow-up only**: mRS scores, follow-up dates. DO NOT use for baseline. |
| `db_11` | Admission | 17,889 | 779 | **PRIMARY**: risk factors, labs, imaging, treatment, NIHSS, classification |
| `db_12` | Thrombolysis | 2,412 | 166 | Acute treatment: tPA, thrombectomy time logs |
| `db_19` | Stent | 1,236 | 334 | Stent procedure details |

### Hospital codes

Not all hospitals use the same tables. The main ones:

| Code | Name | HIDX | Root Table |
|------|------|------|------------|
| YSU | Yonsei Severance | 1 | db_1 |
| GNH | Gangnam Severance | 2 | db_206 |
| KMU | Keimyung | 3 | db_113 |
| KBS | Kangbuk Samsung | 6 | db_159 |
| ISH | NIHS Ilsan | 13 | db_93 |
| CSU | Chosun | 16 | db_212 |
| KUA | Korea Univ Anam | 18 | db_131 |
| EWU, ESH, YIH, BSU, etc. | Various | varies | db_28 (shared) |

### Variable naming

Variables have machine-readable keys (e.g., `pt_sex`, `NIHSS_total`, `Hypertension_existence`) and Korean/English labels. Use `schema search` to find variables by keyword, then `schema variable` to get exact details.

### Value mappings (CRITICAL)

For SELECT, RADIO, and CHECKBOX variables, the database stores **coded values** (from `option2`), not display labels.

**Example**: `Hypertension_existence`
- `option1` (display labels): `"Yes|No"`
- `option2` (DB values): `"1|0"`
- **DB value `1` means "Yes"**, DB value `0` means "No"

**NEVER assume** index-based mapping. Always check with `schema variable` to see the exact value_map.

For NUMBER/TEXT variables, the `option1` field is a subtype hint (`"1"` = text, `"2"` = number, `"3"` = date), NOT a choice list.

---

## Common Research Patterns

### Basic demographics

```bash
# Count total patients
python -m smartdb_cli.main query count YSU

# Get sex/age distribution
python -m smartdb_cli.main query data YSU --vars "pt_sex,pt_age" --limit 5000
```

### Stroke subtype analysis

```bash
# Find the stroke type variable
python -m smartdb_cli.main schema search YSU "stroke_type"

# Check its value map
python -m smartdb_cli.main schema variable YSU stroke_type

# Query by subtype
python -m smartdb_cli.main query data YSU \
  --vars "stroke_type,pt_age,pt_sex,NIHSS_total" \
  --filters '[{"variable":"stroke_type","operator":"=","value":"LAA"}]' \
  --limit 5000
```

### Outcome analysis (mRS follow-up)

```bash
# 3-month mRS with death imputation
python -m smartdb_cli.main query followup YSU --period 3m --vars "pt_age,pt_sex,NIHSS_total"

# 1-year mRS
python -m smartdb_cli.main query followup YSU --period 12m --vars "stroke_type"
```

### Risk factor exploration

```bash
# Search for risk factor variables
python -m smartdb_cli.main schema search YSU "hypertension"
python -m smartdb_cli.main schema search YSU "diabetes"
python -m smartdb_cli.main schema search YSU "smoking"
python -m smartdb_cli.main schema search YSU "atrial fibrillation"

# Query multiple risk factors together
python -m smartdb_cli.main query data YSU \
  --vars "Hypertension_existence,DM_existence,Smoking_existence,AF_existence" \
  --limit 5000
```

### Treatment analysis

```bash
# Find treatment variables
python -m smartdb_cli.main schema search YSU "thrombolysis"
python -m smartdb_cli.main schema search YSU "thrombectomy"

# Look at thrombolysis table variables
python -m smartdb_cli.main schema table-vars YSU db_12 --limit 100
```

### Raw SQL for complex queries

```bash
# Custom aggregation
python -m smartdb_cli.main query sql "
  SELECT pt_sex, COUNT(*) as n, AVG(CAST(pt_age AS DECIMAL)) as mean_age
  FROM smartdb.db_1
  WHERE hidx = 1
  GROUP BY pt_sex
"

# Cross-table query (manual JOIN)
python -m smartdb_cli.main query sql "
  SELECT db_1.pt_sex, db_11.stroke_type, COUNT(*) as n
  FROM smartdb.db_1
  LEFT JOIN smartdb.db_11 ON db_11.parent = db_1.db_idx AND db_11.hidx = 1
  WHERE db_1.hidx = 1
  GROUP BY db_1.pt_sex, db_11.stroke_type
"
```

### Large data export

```bash
# Export full dataset
python -m smartdb_cli.main export xlsx YSU \
  --vars "pt_sex,pt_age,NIHSS_total,stroke_type,Hypertension_existence,DM_existence" \
  --filename "full_cohort" \
  --limit 50000

# Later, add more columns to the same file
python -m smartdb_cli.main export merge exports/full_cohort.xlsx YSU \
  --vars "AF_existence,Smoking_existence" \
  --match-column "patient_id"

# List all exports
python -m smartdb_cli.main export list
```

---

## Limits and Constraints

| Resource | Limit |
|----------|-------|
| `query data` rows | max 5,000 |
| `query sample` rows | max 20 |
| `query followup` rows | max 20,000 |
| `query sql` rows | auto-LIMIT 1,000 |
| `export xlsx` rows | max 50,000 |
| Database | Read-only (no writes) |
| Token expiry | Server-configured (default 24h) |

---

## Error Handling

| Error | Meaning | Fix |
|-------|---------|-----|
| "Not logged in" | No session file found | Run `smartdb login` |
| "Session expired" | JWT token has expired | Run `smartdb login` again |
| "Access denied" | User lacks permission for this hospital | Contact admin for access |
| "Connection error" | Cannot reach the API server | Check API URL with `smartdb config show`, verify server is running |
| "Hospital not found" | Invalid hospital code | Run `schema hospitals` to see valid codes |
| "Variable not found" | Invalid variable key | Use `schema search` to find correct key |

---

## Troubleshooting

### "Connection error: Could not connect"
- Verify the API server is running
- Check the configured URL: `python -m smartdb_cli.main config show`
- Try setting it explicitly: `python -m smartdb_cli.main config set-url http://correct-url:8000`

### "Hospital not found"
- Use exact hospital codes (case-insensitive). Run `schema hospitals` to see all codes.
- You can also use the numeric `hidx` (e.g., `1` instead of `YSU`).

### "Variable not found"
- Variable keys are case-sensitive. Use `schema search` to find the exact key.
- The CLI suggests alternatives using fuzzy search when a variable is not found.

### "No data found"
- The variable might exist in the schema but have no data for that hospital.
- Try `query sample HOSPITAL TABLE` to check if the table has data.
- Check if filters are too restrictive.

### Unexpected values in results
- Always check the value map with `schema variable` before interpreting coded data.
- DB stores option2 values, not option1 labels.

### Need variables from a specific table?
- Use `schema table-vars HOSPITAL TABLE` to see all variables in that table.
- For YSU, most clinical variables are in `db_11` (Admission, 779 variables).
