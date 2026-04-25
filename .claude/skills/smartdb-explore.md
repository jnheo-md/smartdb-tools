# SmartDB Explore

Guided layout-first exploration of a hospital's data in the SmartDB Stroke Registry.

## When to use

When the user wants to see what data a hospital has, find variables, or understand what's available before querying.

## Workflow

1. **Ask which hospital** if not specified. If unsure, start with YSU (Yonsei Severance, richest data). Call `list_hospitals()` if they need to see options.

2. **List tables** for the hospital using `list_tables()`. Briefly describe the key ones:
   - db_1: Patient demographics
   - db_11: Admission (main clinical data)
   - db_12: Thrombolysis/Treatment
   - db_5: Cohort follow-up (mRS outcomes)
   - db_19: Stent procedures
   - Note: table numbers vary by hospital.

3. **Show the layout** for the table they're interested in using `get_layout_fields()`. This is the GROUND TRUTH for what the hospital actually collects. Present the section breakdown and let the user browse.

4. **Drill into sections** if they want detail — use `get_section_variables()` to show individual variables with labels and types.

5. **Check encoding** before they commit — use `get_variable_info()` for any variable where the value encoding matters (SELECT, CHECKBOX types store coded values like 1/0, not Yes/No).

## Safety rules to enforce

- If the user asks about NIHSS, steer them to `admission_NIH_day_0`, `admission_NIH_day_1`, `admission_NIH_day_dc`. NEVER suggest any `NIHSS_total_*` variable — these are CALCULATED fields that produce false zeros.
- If the user asks about mRS outcomes (3-month, 6-month, etc.), ALWAYS use `get_followup_mrs()` for ALL hospitals. It handles differences automatically — cohort table for YSU, `secret_mrs_3month` fallback for others. Never query `admission_mrs_3month` or `secret_mrs_3month` directly. The discharge mRS (`mRS` in db_11) and pre-stroke mRS (`prestroke_mRS`) are fine to query directly — those are not follow-up outcomes.
- NEVER guess variable names. Always show what exists first.
- Different hospitals have different variables — always check the layout for the specific hospital being queried.
