from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "devsystem" / "failure_triage_v1.py"
    spec = importlib.util.spec_from_file_location("failure_triage_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_green_needs_report_no_failures():
    module = _load()
    report = module.triage({
        "classify": {"result": "success"},
        "browser-qa": {"result": "skipped"},
        "cfb-critical": {"result": "success"},
    })
    assert report["status"] == "GREEN"
    assert report["failure_count"] == 0
    assert report["primary"] is None


def test_regression_shield_failure_points_to_invariant_layer():
    module = _load()
    report = module.triage({
        "classify": {"result": "success"},
        "regression-shield": {"result": "failure"},
        "cfb-critical": {"result": "skipped"},
    })
    assert report["status"] == "FAILURES_FOUND"
    assert report["primary"]["job"] == "regression-shield"
    assert report["primary"]["layer"] == "regression-shield"
    assert "first failing invariant" in report["primary"]["inspect_first"]


def test_cfb_failure_preserves_frozen_contract_guidance():
    module = _load()
    report = module.triage({"cfb-critical": {"result": "failure"}})
    text = module.render_summary(report)
    assert "layer=cfb" in text
    assert "official-ID contracts" in text


def test_unknown_job_fails_safe_to_action_logs():
    module = _load()
    report = module.triage({"mystery-lane": {"result": "cancelled"}})
    assert report["primary"]["layer"] == "unknown"
    assert "GitHub Actions logs" in report["primary"]["inspect_first"]


def test_production_failure_routes_to_identity_and_health_evidence():
    module = _load()
    report = module.triage({"production-verification": {"result": "failure"}})
    assert report["primary"]["layer"] == "production"
    assert "Render health/details" in report["primary"]["inspect_first"]
