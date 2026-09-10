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
                "mean_clv_points": 0.0,
                "mean_signal_edge": 2.1,
                "mean_closing_edge": 1.4,
                "mean_edge_decay": 0.7,
            },
            "calibration_curve": [{}, {}, {}],
            "by_conference": {"ACC": {}, "SEC": {}, "UNKNOWN": {}},
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


def _rows():
    return [
        {"game_id": "401858213", "conference": "ACC", "market_type": "over", "market_total_at_signal": 50, "market_total_at_close": 52},
        {"game_id": "401858214", "conference": "SEC", "market_type": "under", "market_total_at_signal": 50, "market_total_at_close": 48},
        {"game_id": "401858214", "conference": "SEC", "market_type": "under", "market_total_at_signal": 50, "market_total_at_close": 48},
        {"game_id": "401858215", "conference": "UNKNOWN", "market_type": "game_total", "market_total_at_signal": 44, "market_total_at_close": 45},
    ]


def _patch(monkeypatch):
    monkeypatch.setattr(evidence_mod, "build_validation_export", lambda _: _safe_export())
    monkeypatch.setattr(evidence_mod, "load_history_records", lambda _: _rows())


def test_summary_requires_policy_for_go(monkeypatch):
    _patch(monkeypatch)
    summary = evidence_mod.build_evidence_summary("history.jsonl")
    assert summary["decision"] == "POLICY_REQUIRED"
    assert summary["scaling_allowed"] is False
    assert summary["unique_game_count"] == 3
    assert summary["coverage"]["conference_count"] == 2
    assert summary["metrics"]["mean_directional_clv_points"] == 2.0
    assert summary["diagnostics"]["thresholds_invented"] is False


def test_explicit_policy_can_go(monkeypatch):
    _patch(monkeypatch)
    result = evidence_mod.evaluate_with_policy(
        "history.jsonl",
        {"min_record_count": 3, "max_brier_score": 0.25, "max_abs_calibration_gap": 0.03, "min_mean_clv_points": 1.0, "min_conference_count": 2},
    )
    assert result["decision"] == "GO"
    assert result["scaling_allowed"] is True
    assert all(result["checks"].values())


def test_duplicate_rows_do_not_inflate_sample_gate(monkeypatch):
    _patch(monkeypatch)
    result = evidence_mod.evaluate_with_policy("history.jsonl", {"min_record_count": 4})
    assert result["decision"] == "NO_GO"
    assert result["checks"]["min_record_count"] is False


def test_under_clv_is_directionally_normalized(monkeypatch):
    _patch(monkeypatch)
    result = evidence_mod.evaluate_with_policy("history.jsonl", {"min_mean_clv_points": 1.5})
    assert result["decision"] == "GO"
    assert result["metrics"]["mean_directional_clv_points"] == 2.0


def test_unknown_conference_does_not_count(monkeypatch):
    _patch(monkeypatch)
    result = evidence_mod.evaluate_with_policy("history.jsonl", {"min_conference_count": 3})
    assert result["decision"] == "NO_GO"
    assert result["coverage"]["conference_count"] == 2


def test_empty_policy_fails_closed(monkeypatch):
    _patch(monkeypatch)
    with pytest.raises(evidence_mod.EvidenceSufficiencyError, match="explicit_policy_required"):
        evidence_mod.evaluate_with_policy("history.jsonl", {})


def test_unknown_policy_key_fails_closed(monkeypatch):
    _patch(monkeypatch)
    with pytest.raises(evidence_mod.EvidenceSufficiencyError, match="unsupported_policy_key"):
        evidence_mod.evaluate_with_policy("history.jsonl", {"magic_threshold": 1})


@pytest.mark.parametrize(
    ("key", "unsafe_value"),
    [("read_only", False), ("live_shadow_only", False), ("official_event_id_only", False), ("core_model_frozen", False), ("stable_json_export", False), ("fuzzy_matching", True), ("synthetic_official_ids", True), ("projection_weight", 0.1), ("may_modify_projection", True)],
)
def test_unsafe_export_fails_closed(monkeypatch, key, unsafe_value):
    payload = _safe_export()
    payload["diagnostics"][key] = unsafe_value
    monkeypatch.setattr(evidence_mod, "build_validation_export", lambda _: payload)
    monkeypatch.setattr(evidence_mod, "load_history_records", lambda _: _rows())
    with pytest.raises(evidence_mod.EvidenceSufficiencyError):
        evidence_mod.build_evidence_summary("history.jsonl")
