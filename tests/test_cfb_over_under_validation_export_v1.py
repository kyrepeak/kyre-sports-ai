from __future__ import annotations

import json

import pytest

import cfb_over_under_validation_export_v1 as export_mod


def _safe_report():
    return {
        "version": "CFB O/U VALIDATION REPORT V1 • STEP 7C",
        "record_count": 2,
        "validation": {
            "overall": {"brier_score": 0.21, "mean_clv_points": 1.5, "mean_edge_decay": 0.4},
            "calibration_curve": [],
            "by_conference": {},
            "by_market_type": {},
        },
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


def test_build_validation_export_preserves_safety(monkeypatch):
    monkeypatch.setattr(export_mod, "build_history_validation_report", lambda _: _safe_report())
    payload = export_mod.build_validation_export("history.jsonl")
    assert payload["record_count"] == 2
    assert payload["diagnostics"]["stable_json_export"] is True
    assert payload["diagnostics"]["schema_version"] == 1
    assert payload["diagnostics"]["projection_weight"] == 0.0
    assert payload["diagnostics"]["may_modify_projection"] is False


def test_export_validation_json_is_deterministic(monkeypatch, tmp_path):
    monkeypatch.setattr(export_mod, "build_history_validation_report", lambda _: _safe_report())
    output = tmp_path / "report.json"
    first = export_mod.export_validation_json("history.jsonl", output)
    text_first = output.read_text(encoding="utf-8")
    second = export_mod.export_validation_json("history.jsonl", output)
    text_second = output.read_text(encoding="utf-8")
    assert first == second
    assert text_first == text_second
    assert json.loads(text_second)["version"] == export_mod.EXPORT_VERSION


@pytest.mark.parametrize(
    ("key", "unsafe_value"),
    [
        ("read_only", False),
        ("live_shadow_only", False),
        ("official_event_id_only", False),
        ("core_model_frozen", False),
        ("fuzzy_matching", True),
        ("synthetic_official_ids", True),
        ("projection_weight", 0.1),
        ("may_modify_projection", True),
    ],
)
def test_build_validation_export_fails_closed(monkeypatch, key, unsafe_value):
    report = _safe_report()
    report["diagnostics"][key] = unsafe_value
    monkeypatch.setattr(export_mod, "build_history_validation_report", lambda _: report)
    with pytest.raises(export_mod.ValidationExportError):
        export_mod.build_validation_export("history.jsonl")
