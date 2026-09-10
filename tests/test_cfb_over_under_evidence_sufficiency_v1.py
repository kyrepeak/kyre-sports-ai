from __future__ import annotations

import pytest

import cfb_over_under_evidence_sufficiency_v1 as evidence_mod


def _safe_export():
    return {
        "version": "CFB O/U VALIDATION EXPORT V1 • STEP 7D",
        "record_count": 120,
        "validation": {
            "overall": {
                "brier_score": 0.20,
                "mean_predicted_probability": 0.57,
                "actual_rate": 0.55,
                "calibration_gap": 0.02,
                "mean_clv_points": 1.2,
                "mean_signal_edge": 2.1,
                "mean_closing_edge": 1.4,
                "mean_edge_decay": 0.7,
            },
            "calibration_curve": [{}, {}, {}],
            "by_conference": {"ACC": {}, "SEC": {}},
            "by_market_type": {"over": {}, "under": {}},
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
            "stable_json_export": True,
        },
    }


def test_summary_requires_policy_for_go(monkeypatch):
    monkeypatch.setattr(evidence_mod, "build_validation_export", lambda _: _safe_export())
    summary = evidence_mod.build_evidence_summary("history.jsonl")
    assert summary["decision"] == "POLICY_REQUIRED"
    assert summary["scaling_allowed"] is False
    assert summary["diagnostics"]["thresholds_invented"] is False
    assert summary["record_count"] == 120
    assert summary["coverage"]["conference_count"] == 2


def test_explicit_policy_can_go(monkeypatch):
    monkeypatch.setattr(evidence_mod, "build_validation_export", lambda _: _safe_export())
    result = evidence_mod.evaluate_with_policy(
        "history.jsonl",
        {
            "min_record_count": 100,
            "max_brier_score": 0.25,
            "max_abs_calibration_gap": 0.03,
            "min_mean_clv_points": 1.0,
        },
    )
    assert result["decision"] == "GO"
    assert result["scaling_allowed"] is True
    assert all(result["checks"].values())


def test_explicit_policy_can_no_go(monkeypatch):
    monkeypatch.setattr(evidence_mod, "build_validation_export", lambda _: _safe_export())
    result = evidence_mod.evaluate_with_policy(
        "history.jsonl",
        {"min_record_count": 200, "min_mean_clv_points": 2.0},
    )
    assert result["decision"] == "NO_GO"
    assert result["scaling_allowed"] is False
    assert not all(result["checks"].values())


def test_empty_policy_fails_closed(monkeypatch):
    monkeypatch.setattr(evidence_mod, "build_validation_export", lambda _: _safe_export())
    with pytest.raises(evidence_mod.EvidenceSufficiencyError, match="explicit_policy_required"):
        evidence_mod.evaluate_with_policy("history.jsonl", {})


def test_unknown_policy_key_fails_closed(monkeypatch):
    monkeypatch.setattr(evidence_mod, "build_validation_export", lambda _: _safe_export())
    with pytest.raises(evidence_mod.EvidenceSufficiencyError, match="unsupported_policy_key"):
        evidence_mod.evaluate_with_policy("history.jsonl", {"magic_threshold": 1})


@pytest.mark.parametrize(
    ("key", "unsafe_value"),
    [
        ("read_only", False),
        ("live_shadow_only", False),
        ("official_event_id_only", False),
        ("core_model_frozen", False),
        ("stable_json_export", False),
        ("fuzzy_matching", True),
        ("synthetic_official_ids", True),
        ("projection_weight", 0.1),
        ("may_modify_projection", True),
    ],
)
def test_unsafe_export_fails_closed(monkeypatch, key, unsafe_value):
    payload = _safe_export()
    payload["diagnostics"][key] = unsafe_value
    monkeypatch.setattr(evidence_mod, "build_validation_export", lambda _: payload)
    with pytest.raises(evidence_mod.EvidenceSufficiencyError):
        evidence_mod.build_evidence_summary("history.jsonl")
