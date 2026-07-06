# SmartDB Hospital Field Reference

Generated cross-hospital field reference artifacts for MCP and AI workflows.

Files:
- `smartdb_field_reference.json` — canonical machine-readable cache used by MCP.
- `smartdb_field_reference.xlsx` — human review workbook with field presence and differences.

Safety:
- No patient-level rows are exported.
- Default `public` privacy stores only data-presence buckets, not exact non-null counts.
- Use `--privacy internal` only for private repositories or local-only caches.

Regenerate:
```bash
python scripts/build_hospital_field_reference.py --privacy public
```

Generated at: `2026-07-06T08:26:25.001023+00:00`
Privacy mode: `public`
Excluded test hospitals: `SMU`
Hospitals: `27`
Fields: `19884`
Differences: `3899`
