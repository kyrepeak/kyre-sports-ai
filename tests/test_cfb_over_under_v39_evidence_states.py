from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_over_under_clean_page_v39.py"


def _load_module():
    assert PAGE.exists(), "V39 evidence-state renderer must exist"
    spec = importlib.util.spec_from_file_location("cfb_over_under_clean_page_v39_test", PAGE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verified_identity() -> dict:
    return {
        "verified": True,
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
        "away_id": "183",
        "home_id": "221",
    }


def test_verified_identity_with_missing_step_metric_is_check_not_identity_gated() -> None:
    module = _load_module()
    engine = {
        "status": "GATED",
        "reason": "NCAA FBS/FCS identity is unavailable for one or both teams.",
        "coverage": 0.0,
    }

    state = module._step_evidence_state(6, "Red Zone", engine, _verified_identity())

    assert state["display_status"] == "CHECK"
    assert state["identity_verified"] is True
    assert "Teams verified" in state["display_reason"]
    assert "red zone" in state["display_reason"].lower()
    assert "identity is unavailable" not in state["display_reason"].lower()
    assert state["frozen_status"] == "GATED"
    assert state["frozen_reason"] == engine["reason"]
    assert engine["status"] == "GATED"


def test_genuinely_unresolved_identity_stays_gated() -> None:
    module = _load_module()
    engine = {"status": "GATED", "reason": "Identity unavailable", "coverage": 0.0}
    identity = {"verified": False, "away_team": "Syracuse", "home_team": "Pittsburgh"}

    state = module._step_evidence_state(7, "Third Down", engine, identity)

    assert state["display_status"] == "GATED"
    assert state["identity_verified"] is False
    assert "identity" in state["display_reason"].lower()
    assert state["frozen_status"] == "GATED"


def test_verified_identity_with_usable_step_metrics_is_ready() -> None:
    module = _load_module()
    engine = {
        "status": "READY",
        "reason": "Certified third-down evidence available.",
        "coverage": 1.0,
        "offense_rate": 0.46,
        "defense_rate": 0.38,
    }

    state = module._step_evidence_state(7, "Third Down", engine, _verified_identity())

    assert state["display_status"] == "READY"
    assert state["identity_verified"] is True
    assert state["frozen_status"] == "READY"
    assert state["metrics"]


def test_evidence_state_never_mutates_frozen_engine() -> None:
    module = _load_module()
    engine = {
        "status": "GATED",
        "reason": "Frozen prior preserved.",
        "coverage": 0.0,
        "nested": {"value": 1},
    }
    before = {
        "status": engine["status"],
        "reason": engine["reason"],
        "coverage": engine["coverage"],
        "nested": dict(engine["nested"]),
    }

    module._step_evidence_state(8, "Turnover Volatility", engine, _verified_identity())

    assert engine == before
