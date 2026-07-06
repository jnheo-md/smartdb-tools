"""Client-side hospital visibility rules for SmartDB tools."""

from __future__ import annotations

import os
from typing import Any


EXCLUDED_TEST_HOSPITAL_CODES = frozenset({"SMU"})
EXCLUDED_TEST_HOSPITAL_HIDXS = frozenset({"4"})
EXCLUDED_TEST_HOSPITAL_NAMES = frozenset({"스마트 병원"})


def include_test_hospitals() -> bool:
    """Return True when test hospitals should be visible to maintenance users."""
    return os.environ.get("SMARTDB_INCLUDE_TEST_HOSPITALS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_excluded_test_hospital(value: Any) -> bool:
    """Return True if a value identifies a SmartDB test hospital."""
    if include_test_hospitals() or value is None:
        return False
    normalized = str(value).strip()
    return (
        normalized.upper() in EXCLUDED_TEST_HOSPITAL_CODES
        or normalized in EXCLUDED_TEST_HOSPITAL_HIDXS
        or normalized in EXCLUDED_TEST_HOSPITAL_NAMES
    )


def filter_visible_hospitals(hospitals: list[dict]) -> list[dict]:
    """Remove test hospitals from a /schema/hospitals response."""
    if include_test_hospitals():
        return hospitals
    return [
        hospital
        for hospital in hospitals
        if not (
            is_excluded_test_hospital(hospital.get("code"))
            or is_excluded_test_hospital(hospital.get("hidx"))
            or is_excluded_test_hospital(hospital.get("name"))
        )
    ]


def excluded_hospital_message(value: Any) -> str:
    return (
        f"Hospital '{value}' is a SmartDB test hospital and is hidden by "
        "smartdb-tools. Set SMARTDB_INCLUDE_TEST_HOSPITALS=1 to access it "
        "for maintenance."
    )
