"""CFB Over/Under Step 7D stable validation export layer.

Read-only exporter for Step 7C history validation reports. Produces a deterministic
JSON artifact for archival and comparison without modifying projections, routing,
market attachment, or wager-selection logic.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cfb_over_under_validation_report_v1 import build_history_validation_report

EXPORT_VERSION = "CFB O/U VALIDATION EXPORT V1 • STEP 7D"


class ValidationExportError(ValueError):
    """Raised when Step 7D cannot safely export a validation report."""


def build_validation_export(history_path: str | Path) -> dict[str, Any]:
    report = build_history_validation_report(history_path)
    diagnostics = dict(report.get("diagnostics") or {})
    required_true = (
        "read_only",
        "live_shadow_only",
        "official_event_id_only",
        "core_model_frozen",
    )
    if any(diagnostics.get(key) is not True for key in required_true):
        raise ValidationExportError("unsafe_report_diagnostics")
    if diagnostics.get("fuzzy_matching") is not False:
        raise ValidationExportError("unsafe_fuzzy_matching")
    if diagnostics.get("synthetic_official_ids") is not False:
        raise ValidationExportError("unsafe_synthetic_ids")
    if float(diagnostics.get("projection_weight", 0.0)) != 0.0:
        raise ValidationExportError("unsafe_nonzero_projection_weight")
    if diagnostics.get("may_modify_projection") is not False:
        raise ValidationExportError("unsafe_projection_mutation")

    return {
        "version": EXPORT_VERSION,
        "record_count": report["record_count"],
        "validation": report["validation"],
        "diagnostics": {
            **diagnostics,
            "stable_json_export": True,
            "schema_version": 1,
        },
    }


def export_validation_json(history_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    payload = build_validation_export(history_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


__all__ = ["EXPORT_VERSION", "ValidationExportError", "build_validation_export", "export_validation_json"]
