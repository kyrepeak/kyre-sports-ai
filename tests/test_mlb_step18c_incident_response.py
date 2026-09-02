import pytest

from sports_api.tools.mlb_step18c_incident_response import (
    CERTIFIED_RENDER_ROLLBACK_REVISION,
    MLBStep18CIncidentResponseError,
    build_incident_response_plan,
)


def _report(*incidents, state=None, healthy=None):
    critical = sum(item["severity"] == "critical" for item in incidents)
    warning = sum(item["severity"] == "warning" for item in incidents)
    if state is None:
        state = "critical" if critical else "degraded" if warning else "healthy"
    if healthy is None:
        healthy = critical == 0
    return {
        "data_type": "mlb_step18b_production_observability",
        "state": state,
        "healthy": healthy,
        "critical_incident_count": critical,
        "warning_incident_count": warning,
        "incidents": list(incidents),
        "ages_seconds": {"heartbeat": 23.0, "last_completed_cycle": 23.0, "process_uptime": 600.0},
        "thresholds_seconds": {"heartbeat_stale": 150, "completed_cycle_stale": 240, "startup_grace": 120, "configured_loop": 60},
        "report_sha256": "a" * 64,
    }


def _incident(code, severity="critical", detail="test incident"):
    return {"code": code, "severity": severity, "detail": detail}


def test_healthy_report_requires_no_action_and_never_mutates():
    plan = build_incident_response_plan(_report())
    assert plan["response_state"] == "healthy"
    assert plan["disposition"] == "no_action"
    assert plan["page_operator"] is False
    assert plan["rollback_recommended"] is False
    assert plan["automatic_rollback_performed"] is False
    assert plan["semantics"]["render_mutation_performed"] is False
    assert plan["semantics"]["github_mutation_performed"] is False
    assert plan["semantics"]["database_write_performed"] is False
    assert plan["semantics"]["provider_network_called"] is False
    assert plan["semantics"]["sportsbook_network_called"] is False
    assert len(plan["plan_sha256"]) == 64


def test_warning_only_report_is_degraded_and_observed_not_rolled_back():
    plan = build_incident_response_plan(_report(_incident("historical_runtime_failures", "warning")))
    assert plan["response_state"] == "degraded"
    assert plan["disposition"] == "observe_and_collect_evidence"
    assert plan["page_operator"] is False
    assert plan["rollback_recommended"] is False


def test_safety_boundary_breach_recommends_manual_rollback():
    plan = build_incident_response_plan(_report(_incident("sportsbook_boundary_crossed")))
    assert plan["response_state"] == "critical"
    assert plan["page_operator"] is True
    assert plan["rollback_recommended"] is True
    assert plan["disposition"] == "manual_rollback_recommended"
    assert plan["rollback_target"]["revision"] == CERTIFIED_RENDER_ROLLBACK_REVISION
    assert plan["rollback_target"]["execution_mode"] == "manual_only"
    assert "sportsbook_boundary_crossed" in plan["safety_boundary_codes"]
    assert plan["automatic_rollback_performed"] is False


def test_actionable_output_or_wagering_breach_recommends_manual_rollback():
    report = _report(
        _incident("actionable_output_enabled"),
        _incident("wagering_enabled"),
    )
    plan = build_incident_response_plan(report)
    assert plan["rollback_recommended"] is True
    assert set(plan["safety_boundary_codes"]) == {"actionable_output_enabled", "wagering_enabled"}


def test_stale_heartbeat_requires_manual_investigation_before_rollback():
    plan = build_incident_response_plan(_report(_incident("heartbeat_stale")))
    assert plan["response_state"] == "critical"
    assert plan["disposition"] == "manual_investigation_required"
    assert plan["rollback_recommended"] is False
    assert "heartbeat_stale" in plan["investigate_first_codes"]


def test_lost_restart_recovery_recommends_manual_rollback():
    plan = build_incident_response_plan(_report(_incident("restart_recovery_not_proven")))
    assert plan["rollback_recommended"] is True
    assert plan["rollback_target"]["requires_post_recovery_step18a"] is True
    assert plan["rollback_target"]["requires_post_recovery_step18b"] is True


def test_shared_wnba_safety_drift_is_treated_as_shared_host_safety_breach():
    plan = build_incident_response_plan(_report(_incident("wnba_read_only_safety_drift")))
    assert plan["rollback_recommended"] is True
    assert "wnba_read_only_safety_drift" in plan["safety_boundary_codes"]


def test_unknown_critical_incident_fails_closed_to_operator_review_not_auto_rollback():
    plan = build_incident_response_plan(_report(_incident("future_unknown_critical")))
    assert plan["response_state"] == "critical"
    assert plan["page_operator"] is True
    assert plan["rollback_recommended"] is False
    assert plan["automatic_rollback_performed"] is False
    assert plan["disposition"] == "manual_investigation_required"


def test_malformed_incident_contract_is_rejected():
    report = _report()
    report["incidents"] = [{"code": "x", "severity": "panic", "detail": "bad"}]
    with pytest.raises(MLBStep18CIncidentResponseError, match="malformed"):
        build_incident_response_plan(report)


def test_wrong_observability_contract_is_rejected():
    report = _report()
    report["data_type"] = "something_else"
    with pytest.raises(MLBStep18CIncidentResponseError, match="unsupported"):
        build_incident_response_plan(report)
