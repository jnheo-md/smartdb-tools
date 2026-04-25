"""
Variable Safety Module
=======================
Maps known dangerous variables to safe alternatives.
Prevents false-zero data incidents from IFNULL-based computed fields
and incorrect mRS outcome queries.
"""

from __future__ import annotations

DANGEROUS_VARIABLES: dict[str, dict] = {
    # --- NIHSS CALCULATED fields (false zeros via IFNULL) ---
    "NIHSS_total_day_0": {
        "safe": "admission_NIH_day_0",
        "reason": "CALCULATED field uses IFNULL — produces false zeros when sub-items aren't entered",
        "tool": "get_nihss_scores()",
    },
    "NIHSS_total_day_1": {
        "safe": "admission_NIH_day_1",
        "reason": "CALCULATED field uses IFNULL — produces false zeros when sub-items aren't entered",
        "tool": "get_nihss_scores()",
    },
    "NIHSS_total_day_3": {
        "safe": None,
        "reason": "CALCULATED field uses IFNULL — produces false zeros. No raw alternative for Day 3",
        "tool": "get_nihss_scores()",
    },
    "NIHSS_total_day_7": {
        "safe": None,
        "reason": "CALCULATED field uses IFNULL — produces false zeros. No raw alternative for Day 7",
        "tool": "get_nihss_scores()",
    },
    "NIHSS_total_day_14": {
        "safe": None,
        "reason": "CALCULATED field uses IFNULL — produces false zeros. No raw alternative for Day 14",
        "tool": "get_nihss_scores()",
    },
    "NIHSS_total_dc": {
        "safe": "admission_NIH_day_dc",
        "reason": "CALCULATED field uses IFNULL — produces false zeros when sub-items aren't entered",
        "tool": "get_nihss_scores()",
    },
    # --- mRS outcome variables that should NOT be queried directly ---
    # Always use get_followup_mrs() which handles hospital differences:
    #   YSU: cohort table (db_5) with mRS_calculated + death imputation
    #   Other hospitals: falls back to secret_mrs_3month automatically
    "admission_mrs_3month": {
        "safe": None,
        "reason": "Do not query mRS outcomes directly. Use get_followup_mrs(period='3m') which handles hospital differences automatically (cohort table for YSU, secret_mrs_3month for others)",
        "tool": "get_followup_mrs()",
    },
    "admission_mrs_3month_assume": {
        "safe": None,
        "reason": "Do not query mRS outcomes directly. Use get_followup_mrs(period='3m')",
        "tool": "get_followup_mrs()",
    },
    "secret_mrs_3month": {
        "safe": None,
        "reason": "Do not query mRS outcomes directly. Use get_followup_mrs(period='3m') which handles hospital differences and adds death imputation where available",
        "tool": "get_followup_mrs()",
    },
}


def check_dangerous_variables(
    variables: list[str], hospital_code: str = "",
) -> list[dict]:
    """Returns warnings for any dangerous variables in the list."""
    warnings = []
    for var in variables:
        entry = DANGEROUS_VARIABLES.get(var)
        if entry is not None:
            warnings.append({
                "variable": var,
                "reason": entry["reason"],
                "safe": entry.get("safe"),
                "tool": entry.get("tool"),
            })
    return warnings
