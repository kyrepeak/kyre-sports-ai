from datetime import datetime, timezone

from sports_api import wnba_step17c_production_reliability as s17c


NOW = datetime(2026, 8, 28, 23, 30, 0, tzinfo=timezone.utc)


def _env():
    return {
        s17c.STEP17C_ENABLED_ENV: "true",
        "WNBA_STEP17B_LOOP_SECONDS": "60",
        "WNBA_STEP17B_EXPECTED_REVISION": "a" * 40,
        "WNBA_DEPLOYMENT_REVISION": "a" * 40,
    }


def _status(**overrides):
    base = {
        "enabled": True,
        "running": True,
        "role": "leader",
        "leadership_acquired": True,
        "started_at_utc": "2026-08-28T23:20:00+00:00",
        "heartbeat_at_utc": "2026-08-28T23:29:45+00:00",
        "next_cycle_due_at_utc": "2026-08-28T23:30:30+00:00",
        "cycle_count": 8,
        "success_count": 8,
        "failure_count": 0,
        "leadership_miss_count": 0,
        "duplicate_lease_skip_count": 0,
        "last_cycle_started_at_utc": "2026-08-28T23:29:20+00:00",
        "last_cycle_finished_at_utc": "2026-08-28T23:29:30+00:00",
        "last_slate_date": "2026-08-28",
        "last_status": "cycle_completed",
        "last_error_class": None,
        "last_checkpoint_version": 8,
        "recovered_from_checkpoint": True,
        "database_secret_exposed": False,
        "legacy_production_switches_enabled": False,
        "new_render_service_created": False,
        "owner_id": "render-step17b:123",
        "leadership_lock_key": 12345,
    }
    base.update(overrides)
    return base


def _report(status, env=None):
    return s17c.build_step17c_production_reliability(
        now_utc=NOW,
        env=_env() if env is None else env,
        status_getter=lambda: status,
    )


def test_healthy_single_leader_runtime_is_healthy_and_read_only():
    report = _report(_status())
    assert report["state"] == "healthy"
    assert report["healthy"] is True
    assert report["incident_active"] is False
    assert report["incidents"] == []
    assert report["step17b"]["last_checkpoint_version"] == 8
    assert report["semantics"]["read_only"] is True
    assert report["semantics"]["database_connection_opened"] is False
    assert report["semantics"]["scheduler_cycle_triggered"] is False
    assert "owner_id" not in report["step17b"]
    assert "leadership_lock_key" not in report["step17b"]


def test_startup_window_is_degraded_not_falsely_critical():
    status = _status(
        role="candidate",
        leadership_acquired=False,
        started_at_utc="2026-08-28T23:29:30+00:00",
        heartbeat_at_utc="2026-08-28T23:29:55+00:00",
        cycle_count=0,
        success_count=0,
        last_cycle_finished_at_utc=None,
        last_checkpoint_version=None,
        recovered_from_checkpoint=None,
    )
    report = _report(status)
    assert report["state"] == "degraded"
    codes = {item["code"] for item in report["incidents"]}
    assert codes == {"leadership_starting", "awaiting_first_success"}


def test_stale_heartbeat_and_stale_cycle_are_critical():
    status = _status(
        heartbeat_at_utc="2026-08-28T23:20:00+00:00",
        last_cycle_finished_at_utc="2026-08-28T23:20:00+00:00",
    )
    report = _report(status)
    assert report["state"] == "critical"
    codes = {item["code"] for item in report["incidents"]}
    assert "heartbeat_stale" in codes
    assert "cycle_stale" in codes


def test_active_runtime_error_is_critical_but_historical_failure_is_warning():
    active = _report(_status(failure_count=1, last_error_class="WNBAStep13ReliabilityFatalError", last_status="cycle_failed"))
    assert active["state"] == "critical"
    assert "active_runtime_error" in {item["code"] for item in active["incidents"]}

    recovered = _report(_status(failure_count=1, last_error_class=None, last_status="cycle_completed"))
    assert recovered["state"] == "degraded"
    assert "historical_runtime_failures" in {item["code"] for item in recovered["incidents"]}


def test_success_without_checkpoint_and_revision_mismatch_fail_closed():
    env = _env()
    env["WNBA_DEPLOYMENT_REVISION"] = "b" * 40
    report = _report(_status(last_checkpoint_version=None), env=env)
    assert report["state"] == "critical"
    codes = {item["code"] for item in report["incidents"]}
    assert "checkpoint_missing" in codes
    assert "revision_mismatch" in codes


def test_disabled_monitor_is_explicit_and_does_not_run_work():
    env = _env()
    env[s17c.STEP17C_ENABLED_ENV] = "false"
    report = _report(_status(), env=env)
    assert report["state"] == "disabled"
    assert report["healthy"] is False
    assert report["incident_active"] is False
    assert report["semantics"]["database_write_performed"] is False
    assert report["semantics"]["sportsbook_network_called"] is False


if __name__ == "__main__":
    test_healthy_single_leader_runtime_is_healthy_and_read_only()
    test_startup_window_is_degraded_not_falsely_critical()
    test_stale_heartbeat_and_stale_cycle_are_critical()
    test_active_runtime_error_is_critical_but_historical_failure_is_warning()
    test_success_without_checkpoint_and_revision_mismatch_fail_closed()
    test_disabled_monitor_is_explicit_and_does_not_run_work()
    print("STEP17C_PRODUCTION_RELIABILITY_TESTS_OK")
