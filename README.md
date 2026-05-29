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
