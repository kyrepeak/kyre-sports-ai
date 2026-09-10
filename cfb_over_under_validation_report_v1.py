"""CFB Over/Under Step 7C validation-report bridge.

Read-only adapter that loads certified Step 7B shadow-history JSONL and feeds it
into the frozen Step 7A validation engine. It never modifies projections,
market attachment, routing, or wager-selection logic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from cfb_over_under_shadow_history_v1 import load_history_records
from cfb_over_under_validation_v1 import build_validation_report

REPORT_VERSION = "CFB O/U VALIDATION REPORT V1 • STEP 7C"


class ValidationReportError(ValueError):
    """Raised when Step 7C cannot safely produce a report."""


def build_history_validation_report(path: str | Path) -> dict[str, Any]:
    """Load certified shadow history and return a read-only validation report."""
    records = load_history_records(path)
    if not records:
        raise ValidationReportError("unsafe_empty_shadow_history")

    report = build_validation_report(records)
    return {
        "version": REPORT_VERSION,
        "history_path": str(Path(path)),
        "record_count": len(records),
        "validation": report,
        "diagnostics": {
            "read_only": True,
            "live_shadow_only": True,
            "official_event_id_only": True,
            "fuzzy_matching": False,
            "synthetic_official_ids": False,
            "projection_weight": 0.0,
            "may_modify_projection": False,
            "core_model_frozen": True,
            "routing_changes": False,
            "wager_selection_changes": False,
        },
    }


__all__ = ["REPORT_VERSION", "ValidationReportError", "build_history_validation_report"]
