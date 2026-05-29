# SmartDB Tools

CLI and MCP server for the **SmartDB Stroke Registry** — query 16,000+ stroke patients across 27 Korean hospitals from your terminal or AI IDE.

## Quick Install

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/jnheo-md/smartdb-tools/master/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/jnheo-md/smartdb-tools/master/install.ps1 | iex
```

## What's Included

| Component | Description |
|-----------|-------------|
| **smartdb CLI** | Command-line tool for querying schemas, patient data, and exporting to XLSX |
| **MCP Server** | Model Context Protocol server for AI IDEs (Claude Code, Claude Desktop, Codex, Cursor, Windsurf, Pi Coding Agent) |

## Features

- **Schema exploration** — browse hospitals, tables, and 3,000+ clinical variables
- **Patient queries** — filter and retrieve data with auto-JOINs across tables
- **mRS outcome analysis** — cohort-based follow-up outcomes with death imputation
- **Clot composition** — thrombus histology data from the ARIA study
- **Excel export** — export filtered cohorts to XLSX
- **AI-powered** — natural language queries via MCP in supported IDEs

## Usage

```bash
# Log in
smartdb login

# Explore the schema
smartdb schema hospitals
smartdb schema tables YSU
smartdb schema search YSU "NIHSS"

# Query patient data
smartdb query data YSU --vars "pt_sex,pt_age,admission_NIH_day_0" --limit 50

# Get follow-up outcomes (the correct way)
smartdb query followup YSU --period 3m

# Export to Excel
smartdb export xlsx YSU --vars "pt_sex,pt_age" --filters '[{"variable":"Thr_mechanical","operator":"=","value":"1"}]'
```

## AI Integration

### MCP-based tools (Claude, Codex, Cursor, Windsurf, Pi Coding Agent)

The installer can auto-configure the MCP server with built-in safety rules, layout-first workflows, per-hospital variable validation before raw exports, and dedicated tools for NIHSS and mRS outcomes. You can rerun AI setup at any time:

```bash
smartdb ai setup --tools auto
smartdb ai setup --tools claude-code,claude-desktop,codex,cursor,windsurf,pi-agent
```

To manually configure another MCP client, add this to its MCP settings:

macOS/Linux:
```json
{
  "smartdb": {
    "command": "~/.smartdb/venv/bin/python",
    "args": ["~/.smartdb/mcp-server/server.py"]
  }
}
```

Windows:
```json
{
  "smartdb": {
    "command": "%USERPROFILE%\\.smartdb\\venv\\Scripts\\python.exe",
    "args": ["%USERPROFILE%\\.smartdb\\mcp-server\\server.py"]
  }
}
```

### CLI-based tools (Copilot, Aider, etc.)

Any AI agent that can run shell commands on your machine can use the SmartDB CLI directly. See [AGENTS.md](AGENTS.md) for structured instructions that AI agents can follow.

For a comprehensive cross-platform reference, see [docs/SMARTDB_AI_GUIDE.md](docs/SMARTDB_AI_GUIDE.md).

## Optional User Preprocessing Preferences

Some users have legacy Excel macro workflows or personal preferences for how exported data should be cleaned, deduplicated, or formatted. SmartDB keeps these preferences **optional, local, and opt-in** so they do not affect other users or default exports.

### Safety model

- **Free-text memory is advisory only** — it can help an AI assistant understand your preferences, but it cannot directly modify data.
- **Structured profiles are deterministic** — actual preprocessing rules must be written in `preprocess.toml`.
- **No silent transformations** — MCP should summarize the profile and ask for confirmation before applying it.
- **No patient data in memory** — store workflow preferences only, not chart numbers, names, or clinical values.
- **SmartDB safety rules still apply** — do not use `NIHSS_total_*` or direct 3-month mRS macro logic; use the dedicated NIHSS and follow-up tools.

### Create your personal preprocessing files

```bash
smartdb preprocess init --scope user
```

This creates:

| File | Purpose |
|------|---------|
| `~/.smartdb/memory/preprocess.md` | Free-text notes about how you prefer data to be processed |
| `~/.smartdb/preprocess.toml` | Deterministic profiles that can be validated and audited |

You can add memory from the terminal:

```bash
smartdb preprocess memory add "For EVT exports, identify duplicates by uniq_id + thrombolysis_count_during_adm and keep the most complete row."
smartdb preprocess memory show
```

### Create project-level profiles

If a team wants a shared profile in a repository, create a project config:

```bash
smartdb preprocess init --scope project
```

This creates `.smartdb/preprocess.toml` in the current project. Commit it only if the rules are intended to be shared. Personal project notes in `.smartdb/preprocess.md` are ignored by Git by default.

### Review and validate profiles

```bash
smartdb preprocess list-profiles
smartdb preprocess explain example_evt
smartdb preprocess validate example_evt
smartdb preprocess context
```

Profile precedence is:

1. Explicit file passed with `--config`
2. User profile at `~/.smartdb/preprocess.toml`
3. Project profile at `.smartdb/preprocess.toml`
4. Built-in safe defaults

Use an explicit file when you want fully reproducible behavior:

```bash
smartdb preprocess validate example_evt --config ./my_rules/preprocess.toml
```

### How MCP should use this

MCP tools can read your preferences with `get_preprocess_preferences()` and one profile with `get_preprocess_profile(profile_name)`. The intended flow is:

1. Read free-text memory and available profiles.
2. Propose a deterministic profile or explain an existing one.
3. Validate every source field and saved-value encoding per hospital.
4. Ask for user confirmation.
5. Run preprocessing only after confirmation, writing an audit trail.

At this stage, these commands manage memory and profiles. They do **not** yet transform exported XLSX files. That separation is intentional so the profile design can be reviewed before any data-changing command is added.

### Roll back this feature branch

The current stable branch remains `master`. This optional preprocessing system is developed on a separate branch so it can be reviewed or discarded:

```bash
git switch master
git branch -D codex/user-preprocess-profiles
```

If the branch has already been pushed and should be removed from GitHub:

```bash
git push origin --delete codex/user-preprocess-profiles
```

### Cross-hospital field reference

To maintain a GitHub-hosted reference of column presence, table locations, saved-value encodings, and data-presence differences across hospitals:

```bash
python scripts/build_hospital_field_reference.py --privacy public
```

Commit the generated files in `reference/hospital-field-reference/`. MCP can refresh the local cache from the raw GitHub JSON with `refresh_field_reference_cache()`, then use `lookup_field_reference()` or `list_field_reference_differences()` before final live validation.

## Requirements

- Python 3.10+
- macOS, Linux, or Windows 10/11
- SmartDB registry account (contact your hospital administrator)

## Security

- All communication over HTTPS — no direct database access
- JWT tokens stored with restricted file permissions (`0600` on macOS/Linux)
- Role-based access control enforced server-side
- See [SECURITY.md](SECURITY.md) for details

## License

[MIT](LICENSE) — Copyright (c) 2025 SmartStroke / Yonsei University
