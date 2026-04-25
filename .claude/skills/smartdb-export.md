# SmartDB Export

Guided safe export of patient data from the SmartDB Stroke Registry.

## When to use

When the user wants to export data to XLSX/CSV for analysis — whether for a single hospital or across multiple hospitals.

## Workflow

### Step 1: Clarify what they need

Ask (if not already clear):
- Which hospital(s)?
- What clinical domain? (demographics, treatment, outcomes, imaging, labs, etc.)
- Any filters? (date range, treatment type, stroke subtype, etc.)
- Is this for mRS outcomes? (If yes, skip to the mRS path below.)

### Step 2: Explore variables (layout-first)

For each hospital:
1. Call `get_layout_fields(hospital, table)` to see what the hospital actually collects
2. Present the variables to the user and let them pick
3. For any variable with unclear encoding, check with `get_variable_info()`

This step prevents querying variables that don't exist for a hospital.

### Step 3: Validate and export

- For **regular data**: use `export_xlsx()` with the selected variables and filters
- For **mRS outcomes (ALL hospitals)**: ALWAYS use `export_followup_xlsx()`. It handles hospital differences automatically — cohort table (db_5) for YSU, `secret_mrs_3month` fallback for others. Never query `admission_mrs_3month` or `secret_mrs_3month` directly.
- For **NIHSS**: use `admission_NIH_day_0`, `admission_NIH_day_1`, `admission_NIH_day_dc` — never `NIHSS_total_*`

### Step 4: Report results

After export, tell the user:
- File path and size
- Number of rows
- Any warnings from the safety checks
- Summary statistics if relevant

## mRS Outcome Export Path

ALWAYS use `export_followup_xlsx()` for ALL hospitals. It handles the differences automatically:
- **YSU**: queries the cohort table (db_5) with `mRS_calculated` + death imputation
- **Other hospitals**: falls back to `secret_mrs_3month` automatically

Never query `admission_mrs_3month` or `secret_mrs_3month` directly via `export_xlsx()`.

Steps:
1. Use `export_followup_xlsx()` with the desired period: 3m, 6m, 9m, 12m, 2y, 3y, etc.
2. Add any additional variables they want alongside the mRS (e.g., pt_sex, pt_age)
3. Apply filters if needed (e.g., thrombectomy patients only: `Thr_mechanical=1`)

## Multi-Hospital Export

When exporting across multiple hospitals:
1. Check `get_layout_fields()` for EACH hospital — they may have different variables
2. Find the common set of variables available across all target hospitals
3. Export each hospital separately (the API queries one hospital at a time)
4. Inform the user which variables were available in which hospitals

## Safety rules

- The `query_data()` and `export_xlsx()` tools will automatically warn if dangerous variables are used (NIHSS_total_*, admission_mrs_3month, etc.)
- Always use the layout to verify variables exist before exporting
- Use `adm_date` for date filtering, NOT `onset_hospital_arrival`
- SELECT/CHECKBOX variables use coded values (1/0), not labels (Yes/No)
