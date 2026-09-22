import json

import pytest

from sports_api.tools.mlb_step18d_final_production_freeze import (
    CERTIFIED_RENDER_REVISION,
    FINAL_MARKER,
    MLBStep18DFinalFreezeError,
    build_final_production_freeze,
)


def _h(char: str) -> str:
    return char * 64


def _baseline():
    return {
        "data_type": "mlb_step18a_production_baseline_evidence",
        "schema_version": "mlb_step18a_production_baseline_v1",
        "state": "green",
        "mutation_performed": False,
        "evidence_sha256": _h("a"),
        "rollback_target": {
            "deployed_revision": CERTIFIED_RENDER_REVISION,
            "merged_main_sha": "911e917d9d1552289bab5f8c74604103c056982f",
            "safe_config_sha256": _h("b"),
        },
        "safety": {
            "render_mutation_performed": False,
            "provider_calls": 0,
            "sportsbook_calls": 0,
            "actionable_output_enabled": False,
            "wagering_enabled": False,
        },
    }


def _observability():
    return {
        "data_type": "mlb_step18b_production_observability",
        "schema_version": "mlb_step18b_production_observability_v1",
        "state": "healthy",
        "healthy": True,
        "incident_active": False,
        "critical_incident_count": 0,
        "warning_incident_count": 0,
        "incidents": [],
        "report_sha256": _h("c"),
        "lineage": {
            "step18a_merged_main_sha": "60f8917e4f963f733759f60b82d7dcf468f776cf",
            "step17b_certified_deployed_sha": CERTIFIED_RENDER_REVISION,
        },
        "mlb_step17b": {
            "enabled": True,
            "running": True,
            "role": "leader",
            "leadership_acquired": True,
            "success_count": 25,
            "failure_count": 0,
            "last_checkpoint_version": 26,
            "recovered_from_checkpoint": True,
            "provider_calls": 0,
            "sportsbook_calls": 0,
            "actionable_output_enabled": False,
            "wagering_enabled": False,
        },
        "semantics": {
            "read_only": True,
            "render_mutation_performed": False,
            "database_connection_opened": False,
            "database_read_performed": False,
            "database_write_performed": False,
            "scheduler_started": False,
            "scheduler_cycle_triggered": False,
            "provider_network_called": False,
            "sportsbook_network_called": False,
            "model_run": False,
            "projection_run": False,
            "monte_carlo_run": False,
            "actionable_output_enabled": False,
            "wager_action_performed": False,
            "database_secret_exposed": False,
            "new_render_service_created": False,
        },
    }


def _plan(report_hash=None):
    return {
        "data_type": "mlb_step18c_incident_response_plan",
        "schema_version": "mlb_step18c_incident_response_v1",
        "response_state": "healthy",
        "disposition": "no_action",
        "page_operator": False,
        "rollback_recommended": False,
        "automatic_rollback_performed": False,
        "plan_sha256": _h("d"),
        "rollback_target": {
            "revision": CERTIFIED_RENDER_REVISION,
            "execution_mode": "manual_only",
            "requires_post_recovery_step18a": True,
            "requires_post_recovery_step18b": True,
        },
        "lineage": {
            "step18b_merged_main_sha": "ae66134026297516aac4e6936b8ac9d8e2302481",
            "certified_render_rollback_revision": CERTIFIED_RENDER_REVISION,
        },
        "source_observability": {
            "state": "healthy",
            "report_sha256": report_hash or _h("c"),
        },
        "semantics": {
            "advisory_only": True,
            "render_mutation_performed": False,
            "github_mutation_performed": False,
            "database_connection_opened": False,
            "database_read_performed": False,
            "database_write_performed": False,
            "scheduler_started": False,
            "provider_network_called": False,
            "sportsbook_network_called": False,
            "model_run": False,
            "projection_run": False,
            "monte_carlo_run": False,
            "actionable_output_enabled": False,
            "wager_action_performed": False,
        },
    }


def _cert(**overrides):
    payload = {
        "baseline": _baseline(),
        "observability": _observability(),
        "response_plan": _plan(),
        "certified_at_utc": "2026-09-02T02:30:00+00:00",
    }
    payload.update(overrides)
    return build_final_production_freeze(**payload)


def test_green_final_freeze_completes_step18_without_mutation():
    cert = _cert()
    assert cert["state"] == "green"
    assert cert["step18_complete"] is True
    assert cert["final_marker"] == FINAL_MARKER
    assert cert["live_state"]["response_disposition"] == "no_action"
    assert cert["recovery_policy"]["rollback_execution_mode"] == "manual_only"
    assert cert["frozen_invariants"]["render_mutation_performed"] is False
    assert cert["frozen_invariants"]["provider_network_called"] is False
    assert cert["frozen_invariants"]["sportsbook_network_called"] is False
    assert cert["frozen_invariants"]["wager_action_performed"] is False
    assert len(cert["certificate_sha256"]) == 64


def test_final_freeze_rejects_even_warning_only_observability():
    obs = _observability()
    obs.update({"state": "degraded", "incident_active": True, "warning_incident_count": 1})
    with pytest.raises(MLBStep18DFinalFreezeError, match="not healthy|incident is active|warnings"):
        _cert(observability=obs)


def test_final_freeze_rejects_provider_boundary_crossing():
    obs = _observability()
    obs["mlb_step17b"]["provider_calls"] = 1
    with pytest.raises(MLBStep18DFinalFreezeError, match="network safety boundary"):
        _cert(observability=obs)


def test_final_freeze_rejects_automatic_rollback():
    plan = _plan()
    plan["automatic_rollback_performed"] = True
    with pytest.raises(MLBStep18DFinalFreezeError, match="automatic rollback"):
        _cert(response_plan=plan)


def test_final_freeze_rejects_18b_18c_evidence_linkage_mismatch():
    plan = _plan(report_hash=_h("e"))
    with pytest.raises(MLBStep18DFinalFreezeError, match="evidence linkage"):
        _cert(response_plan=plan)


def test_final_freeze_rejects_rollback_revision_drift():
    baseline = _baseline()
    baseline["rollback_target"]["deployed_revision"] = "0" * 40
    with pytest.raises(MLBStep18DFinalFreezeError, match="rollback revision drift"):
        _cert(baseline=baseline)


def test_final_certificate_contains_no_credentials_or_network_urls():
    cert = _cert()
    text = json.dumps(cert, sort_keys=True).casefold()
    assert "postgresql://" not in text
    assert "authorization" not in text
    assert "render_api_key" not in text
    assert "user:secret" not in text
