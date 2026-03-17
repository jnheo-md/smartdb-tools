# SmartDB Tools

CLI and MCP server for the **SmartDB Stroke Registry** — query 16,000+ stroke patients across 27 Korean hospitals from your terminal or AI IDE.

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/jnheo-md/smartdb-tools/master/install.sh | bash
```

## What's Included

| Component | Description |
|-----------|-------------|
| **smartdb CLI** | Command-line tool for querying schemas, patient data, and exporting to XLSX |
| **MCP Server** | Model Context Protocol server for AI IDEs (Claude Code, Claude Desktop, Cursor) |

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
smartdb query data YSU --vars "pt_sex,pt_age,NIHSS_total" --limit 50

# Get follow-up outcomes (the correct way)
smartdb query followup YSU --period 3m

# Export to Excel
smartdb export xlsx YSU --vars "pt_sex,pt_age" --filters '[{"variable":"Thr_mechanical","operator":"=","value":"1"}]'
```

## MCP Server (for AI IDEs)

The installer automatically configures the MCP server for detected AI tools. To manually configure, add to your MCP settings:

```json
{
  "smartdb": {
    "command": "~/.smartdb/venv/bin/python",
    "args": ["~/.smartdb/mcp-server/server.py"]
  }
}
```

## Requirements

- Python 3.10+
- macOS or Linux
- SmartDB registry account (contact your hospital administrator)

## Security

- All communication over HTTPS — no direct database access
- JWT tokens with 24-hour expiry, stored with `0600` permissions
- Role-based access control enforced server-side
- See [SECURITY.md](SECURITY.md) for details

## License

[MIT](LICENSE) — Copyright (c) 2025 SmartStroke / Yonsei University
