"""Regression checks for CFB O/U Upgrade Step 12 final certification."""
from __future__ import annotations

import copy

import cfb_over_under_certification_v1 as cert
import cfb_over_under_final_v1 as rules


def _result():
    raw = {
        "ready": True,
        "projected_away_points": 20.0,
        "projected_home_points": 27.0,
        "projected_total": 47.0,
        "structural_total_sigma": 14.2,
        "analysis_line": 50.5,
        "over_probability": 0.401,
        "under_probability": 0.599,
        "push_probability": 0.0,
        "reliability": 0.73,
        "feature_coverage": {"score": 0.81},
        "analysis_line_projection_weight": 0.0,
        "analysis_line_form_weight": 0.0,
        "upgrade_step11_applied": False,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }
    final = {
        "ready": True,
        "selection": "PASS",
        "selection_ready": False,
        "rank_eligible": False,
        "projected_away_points": 20.0,
        "projected_home_points": 27.0,
        "projected_total": 47.0,
        "analysis_line": 50.5,
        "over_probability": 0.401,
        "under_probability": 0.599,
        "reliability": 0.73,
        "feature_coverage": 0.81,
        "analysis_line_projection_weight": 0.0,
        "game_identity": "g1",
        "selection_rule": {
            "minimum_probability": rules.MIN_SELECTION_PROBABILITY,
            "minimum_reliability": rules.MIN_SELECTION_RELIABILITY,
            "minimum_feature_coverage": rules.MIN_SELECTION_COVERAGE,
        },
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }
    return {
        "game": {
            "identity_key": "g1",
            "identity_verified": True,
            "date_matches_query": True,
        },
        "raw": raw,
        "final": final,
        "step10_raw": copy.deepcopy(raw),
        "form_strength_engine": {
            "model_ready": False,
            "reason": "home current-season sample below 2 games",
        },
    }


def test_certifies_safe_step11_gate():
    out = cert.certify_result(_result())
    assert out["status"] == "CERTIFIED"
    assert out["certified"] is True
    assert out["integrity_passed"] is True
    assert out["checks_failed"] == 0
    assert out["completed_upgrade_count"] == 12
    assert out["certified_upgrade_steps"] == list(range(1, 13))
    assert len(out["projection_fingerprint"]) == 16


def test_probability_mass_failure_is_blocking():
    row = _result()
    row["raw"]["over_probability"] = 0.60
    row["raw"]["under_probability"] = 0.60
    out = cert.certify_result(row)
    assert out["status"] == "INTEGRITY_FAIL"
    assert out["integrity_passed"] is False
    assert any(x["name"] == "probability mass equals 1" for x in out["blocking_failures"])


def test_market_contamination_failure_is_blocking():
    row = _result()
    row["raw"]["sportsbook_input_used"] = True
    out = cert.certify_result(row)
    assert out["status"] == "INTEGRITY_FAIL"
    assert any("sportsbook/market/EV/Monte Carlo firewall" == x["name"] for x in out["blocking_failures"])


def test_nonzero_analysis_line_weight_is_blocking():
    row = _result()
    row["raw"]["analysis_line_form_weight"] = 0.1
    out = cert.certify_result(row)
    assert out["status"] == "INTEGRITY_FAIL"
    assert any(x["name"] == "analysis-line projection firewall" for x in out["blocking_failures"])


def test_step11_gate_apply_mismatch_is_blocking():
    row = _result()
    row["raw"]["upgrade_step11_applied"] = True
    out = cert.certify_result(row)
    assert out["status"] == "INTEGRITY_FAIL"
    assert any(x["name"] == "Step 11 gate/apply coherence" for x in out["blocking_failures"])


def test_step11_gated_projection_change_is_blocking():
    row = _result()
    row["raw"]["projected_total"] = 47.5
    out = cert.certify_result(row)
    assert out["status"] == "INTEGRITY_FAIL"
    assert any(x["name"] == "Step 11 gated output preserves Step 10" for x in out["blocking_failures"])


def test_frozen_selection_threshold_change_is_blocking():
    row = _result()
    row["final"]["selection_rule"]["minimum_probability"] = 0.50
    out = cert.certify_result(row)
    assert out["status"] == "INTEGRITY_FAIL"
    assert any(x["name"] == "frozen selection thresholds" for x in out["blocking_failures"])


def test_data_gated_pipeline_can_pass_integrity():
    row = _result()
    row["raw"] = {
        "ready": False,
        "upgrade_step11_applied": False,
        "analysis_line_projection_weight": 0.0,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }
    row["final"] = {
        "ready": False,
        "selection_ready": False,
        "rank_eligible": False,
        "analysis_line_projection_weight": 0.0,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }
    row["step10_raw"] = {}
    out = cert.certify_result(row)
    assert out["status"] == "DATA_GATED"
    assert out["integrity_passed"] is True
    assert out["safe_to_display"] is True
    assert out["checks_skipped"] > 0


def test_applied_step11_caps_are_certified():
    row = _result()
    row["form_strength_engine"]["model_ready"] = True
    row["raw"]["upgrade_step11_applied"] = True
    row["raw"]["components"] = {
        "step11_away_form_adjustment": 1.25,
        "step11_home_form_adjustment": 0.75,
        "step11_total_form_adjustment": 2.0,
    }
    out = cert.certify_result(row)
    assert out["status"] == "CERTIFIED"
    assert out["checks_failed"] == 0


def test_applied_step11_cap_violation_fails():
    row = _result()
    row["form_strength_engine"]["model_ready"] = True
    row["raw"]["upgrade_step11_applied"] = True
    row["raw"]["components"] = {
        "step11_away_form_adjustment": 1.50,
        "step11_home_form_adjustment": 0.50,
        "step11_total_form_adjustment": 2.0,
    }
    out = cert.certify_result(row)
    assert out["status"] == "INTEGRITY_FAIL"
    assert any(x["name"] == "Step 11 applied adjustment caps" for x in out["blocking_failures"])
