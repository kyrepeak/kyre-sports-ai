import json

import pytest

from sports_api.tools.mlb_step18a_production_baseline import (
    MLBStep18ABaselineError,
    STEP17B_CERTIFIED_DEPLOYED_SHA,
    validate_production_baseline,
)


def _service():
    return {
        "id": "srv-da84q6ifngtc73bdbm6g",
        "name": "kyre-sports-api",
        "branch": "mlb-step17b-shared-host-cert",
        "autoDeploy": "no",
        "serviceDetails": {"runtime": "docker", "plan": "free"},
    }


def _env():
    return {
        "MLB_STEP17B_ALWAYS_ON_ENABLED": "true",
        "MLB_STEP17B_LOOP_SECONDS": "60",
        "MLB_STEP17B_EXPECTED_REVISION": STEP17B_CERTIFIED_DEPLOYED_SHA,
        "MLB_DEPLOYMENT_MODE": "container",
        "WEB_CONCURRENCY": "1",
        "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED": "true",
        "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED": "true",
        "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED": "true",
        "MLB_STEP14B_DATABASE_READ_ENABLED": "true",
        "MLB_STEP14B_DATABASE_WRITE_ENABLED": "true",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
        "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED": "false",
        "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED": "false",
        "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED": "false",
        "KYRE_DATABASE_URL": "postgresql://user:secret@example.test/kyre",
    }


def _health():
    return {"status": "ok"}


def _wnba():
    return {
        "data_type": "wnba_deployment_and_smoke_readiness",
        "deployment_ready": True,
        "semantics": {
            "deployment_gate_does_not_call_sportsbook": True,
            "deployment_gate_does_not_run_monte_carlo": True,
            "live_smoke_is_read_only": True,
        },
    }


def _mlb():
    return {
        "data_type": "mlb_step17b_runtime_status_v1",
        "enabled": True,
        "running": True,
        "role": "leader",
        "leadership_acquired": True,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "provider_workload_cycle_count": 0,
        "sportsbook_workload_cycle_count": 0,
        "production_scheduler_started": False,
        "legacy_production_runtime_started": False,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "database_secret_exposed": False,
        "new_render_service_created": False,
        "last_error_class": None,
        "success_count": 7,
        "failure_count": 0,
        "last_checkpoint_version": 9,
        "recovered_from_checkpoint": True,
    }


def _validate(**overrides):
    payload = {
        "service": _service(),
        "env": _env(),
        "health": _health(),
        "wnba": _wnba(),
        "mlb": _mlb(),
        "captured_at_utc": "2026-09-02T01:55:00+00:00",
    }
    payload.update(overrides)
    return validate_production_baseline(**payload)


def test_green_baseline_is_read_only_sanitized_and_rollback_ready():
    evidence = _validate()
    assert evidence["state"] == "green"
    assert evidence["mutation_performed"] is False
    assert evidence["rollback_target"]["deployed_revision"] == STEP17B_CERTIFIED_DEPLOYED_SHA
    assert evidence["rollback_target"]["safe_config"]["database_url_configured"] is True
    assert evidence["rollback_target"]["safe_config"]["database_url_exposed"] is False
    assert evidence["safety"]["provider_calls"] == 0
    assert evidence["safety"]["sportsbook_calls"] == 0
    serialized = json.dumps(evidence, sort_keys=True).casefold()
    assert "postgresql://" not in serialized
    assert "user:secret" not in serialized
    assert "authorization" not in serialized
    assert len(evidence["rollback_target"]["safe_config_sha256"]) == 64
    assert len(evidence["evidence_sha256"]) == 64


def test_fails_closed_if_frozen_actionable_gate_is_enabled():
    env = _env()
    env["MLB_ACTIONABLE_OUTPUT_ENABLED"] = "true"
    with pytest.raises(MLBStep18ABaselineError, match="frozen safety gate"):
        _validate(env=env)


def test_fails_closed_on_deployed_revision_drift():
    env = _env()
    env["MLB_STEP17B_EXPECTED_REVISION"] = "0" * 40
    with pytest.raises(MLBStep18ABaselineError, match="revision drift"):
        _validate(env=env)


def test_fails_closed_if_provider_boundary_was_crossed():
    mlb = _mlb()
    mlb["provider_calls"] = 1
    with pytest.raises(MLBStep18ABaselineError, match="provider-call boundary"):
        _validate(mlb=mlb)


def test_fails_closed_if_runtime_is_not_leader():
    mlb = _mlb()
    mlb["role"] = "standby"
    mlb["leadership_acquired"] = False
    with pytest.raises(MLBStep18ABaselineError, match="not the active leader"):
        _validate(mlb=mlb)


def test_fails_closed_without_proven_restart_recovery():
    mlb = _mlb()
    mlb["recovered_from_checkpoint"] = False
    with pytest.raises(MLBStep18ABaselineError, match="restart recovery"):
        _validate(mlb=mlb)
