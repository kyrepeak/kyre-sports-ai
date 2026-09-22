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
    assert report["primary"]["confidence"] == "lane-only"
    assert report["primary"]["retry_policy"] == "investigate-first"
    assert "first failing invariant" in report["primary"]["inspect_first"]


def test_cfb_failure_preserves_frozen_contract_guidance_without_evidence():
    module = _load()
    report = module.triage({"cfb-critical": {"result": "failure"}})
    text = module.render_summary(report)
    assert "layer=cfb" in text
    assert "official-ID contracts" in text


def test_unknown_job_fails_safe_to_action_logs():
    module = _load()
    report = module.triage({"mystery-lane": {"result": "cancelled"}})
    assert report["primary"]["layer"] == "unknown"
    assert report["primary"]["retry_policy"] == "investigate-first"
    assert "GitHub Actions logs" in report["primary"]["inspect_first"]


def test_production_failure_routes_to_identity_and_health_evidence():
    module = _load()
    report = module.triage({"production-verification": {"result": "failure"}})
    assert report["primary"]["layer"] == "production"
    assert "Render health/details" in report["primary"]["inspect_first"]


def test_browser_locator_timeout_gets_specific_high_confidence_diagnosis():
    module = _load()
    report = module.triage({
        "browser-qa": {
            "result": "failure",
            "evidence": "Playwright Timeout 30000ms exceeded waiting for locator combobox",
        }
    })
    primary = report["primary"]
    assert primary["layer"] == "ui-browser"
    assert primary["evidence_signal"] == "browser-selector-race"
    assert primary["confidence"] == "high"
    assert primary["remediation_class"] == "transient-capable"
    assert primary["retry_policy"] == "retry-once-after-inspection"
    assert "readiness" in primary["inspect_first"]


def test_assertion_failure_points_to_first_protected_invariant():
    module = _load()
    report = module.triage({
        "cfb-critical": {
            "result": "failure",
            "log_excerpt": "AssertionError: expected official ESPN event ID\nshort test summary info",
        }
    })
    primary = report["primary"]
    assert primary["evidence_signal"] == "test-assertion"
    assert primary["confidence"] == "high"
    assert primary["remediation_class"] == "deterministic-regression"
    assert primary["retry_policy"] == "do-not-retry"
    assert "protected invariant" in primary["inspect_first"]
    assert primary["layer"] == "cfb"


def test_import_error_identifies_dependency_surface():
    module = _load()
    report = module.triage({
        "mlb-critical": {
            "result": "failure",
            "evidence": "ModuleNotFoundError: No module named 'pandas'",
        }
    })
    primary = report["primary"]
    assert primary["evidence_signal"] == "python-import"
    assert primary["remediation_class"] == "deterministic-regression"
    assert primary["retry_policy"] == "do-not-retry"
    assert "requirements/cache key" in primary["inspect_first"]


def test_unknown_evidence_is_low_confidence_and_does_not_guess():
    module = _load()
    report = module.triage({
        "wnba-critical": {
            "result": "failure",
            "evidence": "something novel happened with no known signature",
        }
    })
    primary = report["primary"]
    assert primary["evidence_signal"] == "unclassified-evidence"
    assert primary["confidence"] == "low"
    assert primary["remediation_class"] == "unknown"
    assert primary["retry_policy"] == "investigate-first"
    assert "first error/traceback line" in primary["inspect_first"]


def test_specific_browser_signature_wins_over_generic_timeout():
    module = _load()
    diagnosis = module.diagnose_evidence(
        "Playwright TimeoutError while waiting for locator get_by_role('combobox')"
    )
    assert diagnosis is not None
    assert diagnosis["evidence_signal"] == "browser-selector-race"
    assert diagnosis["retry_policy"] == "retry-once-after-inspection"


def test_network_upstream_allows_only_one_controlled_retry():
    module = _load()
    diagnosis = module.diagnose_evidence("503 Service Unavailable from upstream API")
    assert diagnosis is not None
    assert diagnosis["evidence_signal"] == "network-upstream"
    assert diagnosis["remediation_class"] == "transient-capable"
    assert diagnosis["retry_policy"] == "retry-once-after-inspection"
    assert "one controlled retry" in diagnosis["retry_reason"]


def test_syntax_error_is_never_retried_as_flake():
    module = _load()
    diagnosis = module.diagnose_evidence("SyntaxError: invalid syntax at app.py line 12")
    assert diagnosis is not None
    assert diagnosis["evidence_signal"] == "syntax-compile"
    assert diagnosis["remediation_class"] == "deterministic-regression"
    assert diagnosis["retry_policy"] == "do-not-retry"


def test_summary_exposes_signal_confidence_diagnosis_and_retry_policy():
    module = _load()
    report = module.triage({
        "core-smoke": {
            "result": "failure",
            "evidence": "SyntaxError: invalid syntax at app.py line 12",
        }
    })
    text = module.render_summary(report)
    assert "signal=syntax-compile" in text
    assert "confidence=high" in text
    assert "remediation=deterministic-regression" in text
    assert "retry_policy=do-not-retry" in text
    assert "diagnosis=Python syntax/compile failure" in text
