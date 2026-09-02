import json

from sports_api.tools.mlb_step18b_production_observability import (
    FINAL_MARKER,
    build_production_observability,
)

NOW = "2026-09-02T02:00:00+00:00"


def _status():
    return {
        "data_type": "mlb_step17b_runtime_status_v1",
        "schema_version": 1,
        "runtime_version": "mlb_step17b_render_single_leader_durable_control_loop_2026_v1",
        "contract_id": "mlb_step17b_controlled_always_on_2026_v1",
        "runtime_mode": "SHADOW_ONLY",
        "enabled": True,
        "running": True,
        "role": "leader",
        "leadership_acquired": True,
        "started_at_utc": "2026-09-02T01:50:00Z",
        "heartbeat_at_utc": "2026-09-02T01:59:45Z",
        "next_cycle_due_at_utc": "2026-09-02T02:00:45Z",
        "control_cycle_count": 10,
        "success_count": 10,
        "failure_count": 0,
        "leadership_miss_count": 1,
        "duplicate_lease_skip_count": 0,
        "last_cycle_started_at_utc": "2026-09-02T01:59:20Z",
        "last_cycle_finished_at_utc": "2026-09-02T01:59:30Z",
        "last_slate_date": "2026-09-01",
        "last_status": "control_cycle_completed",
        "last_error_class": None,
        "last_checkpoint_version": 11,
        "recovered_from_checkpoint": True,
        "provider_workload_cycle_count": 0,
        "sportsbook_workload_cycle_count": 0,
        "production_scheduler_started": False,
        "legacy_production_runtime_started": False,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "database_secret_exposed": False,
        "new_render_service_created": False,
    }


def _health():
    return {"status": "ok"}


def _wnba():
    return {
        "data_type": "wnba_deployment_and_smoke_readiness",
        "semantics": {
            "deployment_gate_does_not_call_sportsbook": True,
            "deployment_gate_does_not_run_monte_carlo": True,
            "live_smoke_is_read_only": True,
        },
    }


def _report(status=None, health=None, wnba=None):
    return build_production_observability(
        status=_status() if status is None else status,
        health=_health() if health is None else health,
        wnba=_wnba() if wnba is None else wnba,
        now_utc=NOW,
        configured_loop_seconds=60,
    )


def test_healthy_runtime_has_no_incidents_and_is_read_only():
    report = _report()
    assert report["state"] == "healthy"
    assert report["healthy"] is True
    assert report["incident_active"] is False
    assert report["critical_incident_count"] == 0
    assert report["warning_incident_count"] == 0
    assert report["thresholds_seconds"]["heartbeat_stale"] == 150
    assert report["thresholds_seconds"]["completed_cycle_stale"] == 240
    assert report["semantics"]["read_only"] is True
    assert report["semantics"]["render_mutation_performed"] is False
    assert report["semantics"]["provider_network_called"] is False
    assert report["semantics"]["sportsbook_network_called"] is False
    assert report["semantics"]["database_write_performed"] is False
    assert len(report["report_sha256"]) == 64


def test_stale_heartbeat_is_critical():
    status = _status()
    status["heartbeat_at_utc"] = "2026-09-02T01:56:00Z"
    report = _report(status=status)
    assert report["state"] == "critical"
    assert report["healthy"] is False
    assert any(item["code"] == "heartbeat_stale" for item in report["incidents"])


def test_stale_completed_cycle_is_critical():
    status = _status()
    status["last_cycle_finished_at_utc"] = "2026-09-02T01:55:00Z"
    report = _report(status=status)
    assert report["healthy"] is False
    assert any(item["code"] == "cycle_stale" for item in report["incidents"])


def test_current_runtime_error_is_critical():
    status = _status()
    status["last_error_class"] = "RuntimeError"
    status["failure_count"] = 1
    report = _report(status=status)
    assert report["healthy"] is False
    assert any(item["code"] == "active_runtime_error" for item in report["incidents"])


def test_historical_failure_without_current_error_is_warning_only():
    status = _status()
    status["failure_count"] = 2
    report = _report(status=status)
    assert report["state"] == "degraded"
    assert report["healthy"] is True
    assert report["critical_incident_count"] == 0
    assert any(item["code"] == "historical_runtime_failures" for item in report["incidents"])


def test_provider_or_sportsbook_boundary_crossing_is_critical():
    status = _status()
    status["provider_calls"] = 1
    status["sportsbook_workload_cycle_count"] = 1
    report = _report(status=status)
    assert report["healthy"] is False
    codes = {item["code"] for item in report["incidents"]}
    assert "provider_boundary_crossed" in codes
    assert "sportsbook_boundary_crossed" in codes


def test_leadership_loss_is_critical_after_startup_grace():
    status = _status()
    status["role"] = "standby"
    status["leadership_acquired"] = False
    report = _report(status=status)
    assert report["healthy"] is False
    assert any(item["code"] == "leadership_not_held" for item in report["incidents"])


def test_starting_inside_grace_is_warning_not_critical():
    status = _status()
    status.update(
        {
            "started_at_utc": "2026-09-02T01:59:20Z",
            "heartbeat_at_utc": "2026-09-02T01:59:50Z",
            "role": "candidate",
            "leadership_acquired": False,
            "success_count": 0,
            "control_cycle_count": 0,
            "last_cycle_finished_at_utc": None,
            "last_checkpoint_version": None,
            "recovered_from_checkpoint": None,
        }
    )
    report = _report(status=status)
    assert report["state"] == "degraded"
    assert report["healthy"] is True
    codes = {item["code"] for item in report["incidents"]}
    assert "leadership_starting" in codes
    assert "awaiting_first_success" in codes
    assert report["critical_incident_count"] == 0


def test_restart_recovery_loss_is_critical():
    status = _status()
    status["recovered_from_checkpoint"] = False
    report = _report(status=status)
    assert report["healthy"] is False
    assert any(item["code"] == "restart_recovery_not_proven" for item in report["incidents"])


def test_shared_wnba_contract_drift_is_critical():
    wnba = _wnba()
    wnba["semantics"]["live_smoke_is_read_only"] = False
    report = _report(wnba=wnba)
    assert report["healthy"] is False
    assert report["shared_host"]["wnba_continuity_ok"] is False
    assert any(item["code"] == "wnba_read_only_safety_drift" for item in report["incidents"])


def test_report_never_contains_database_credentials():
    status = _status()
    status["owner_id"] = "postgresql://user:secret@example.test/db"
    report = _report(status=status)
    text = json.dumps(report, sort_keys=True).casefold()
    assert "postgresql://" not in text
    assert "user:secret" not in text
    assert FINAL_MARKER == "MLB_STEP18B_PRODUCTION_OBSERVABILITY_GREEN"
