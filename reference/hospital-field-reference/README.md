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

Generated at: `2026-07-06T08:11:52.751074+00:00`
Privacy mode: `public`
Hospitals: `28`
Fields: `22481`
Differences: `4515`
