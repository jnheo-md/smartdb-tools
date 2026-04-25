# SmartDB Tools — AI Agent Instructions

This file provides instructions for AI coding agents (Codex, Copilot, Aider, etc.) that can execute shell commands in the user's terminal.

## Setup

The SmartDB CLI must be installed and authenticated:
```bash
smartdb whoami  # verify you're logged in
```

If not installed, run:
```bash
curl -fsSL https://raw.githubusercontent.com/jnheo-md/smartdb-tools/master/install.sh | bash
```

## Before querying data

**Always run `smartdb guide` first** and follow its rules. This prints critical domain rules that prevent data corruption.

The two most important rules:

1. **NIHSS scores**: Never use `NIHSS_total_*` variables — they produce false zeros. Use `admission_NIH_day_0`, `admission_NIH_day_1`, `admission_NIH_day_dc` instead.
2. **mRS outcomes**: Always use `smartdb query followup` or `smartdb export followup` — never query `admission_mrs_3month` or `secret_mrs_3month` directly.

## Common commands

```bash
# Read the full domain guide (DO THIS FIRST)
smartdb guide

# Explore available data
smartdb schema hospitals
smartdb schema tables YSU
smartdb schema sections YSU db_11
smartdb schema section-vars YSU db_11 3

# Query patient data
smartdb query data YSU --vars "pt_sex,pt_age,admission_NIH_day_0" --limit 50

# Get mRS outcomes (the ONLY correct way)
smartdb query followup YSU --period 3m

# Export to Excel
smartdb export xlsx YSU --vars "pt_sex,pt_age,admission_NIH_day_0"
smartdb export followup YSU --period 3m -v "pt_sex,pt_age"
```

## Key rules

- **Check the layout first**: Different hospitals have different variables. Always explore what a hospital collects before querying.
- **Variable encoding**: SELECT/CHECKBOX variables store coded values (1/0), not labels (Yes/No). Run `smartdb schema variable <hospital> <var>` to check.
- **Date filtering**: Use `adm_date` for admission date, not `onset_hospital_arrival`.
- **Table locations differ**: The same variable name may be in different table numbers across hospitals (e.g., db_11 at YSU vs db_29 at EWU).

## Reference

For the complete AI reference guide, see [docs/SMARTDB_AI_GUIDE.md](docs/SMARTDB_AI_GUIDE.md).
