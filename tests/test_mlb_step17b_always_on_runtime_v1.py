import asyncio
import threading
from datetime import datetime, timezone

import pytest

from sports_api import mlb_step17b_always_on_runtime_v1 as s17b


def _env():
    sha = "a" * 40
    return {
        s17b.STEP17B_ENABLED_ENV: "true",
        s17b.STEP17B_LOOP_SECONDS_ENV: "30",
        s17b.STEP17B_EXPECTED_REVISION_ENV: sha,
        s17b.DEPLOYMENT_MODE_ENV: "container",
        "WEB_CONCURRENCY": "1",
        "KYRE_DATABASE_URL": "postgresql://user:secret@example.invalid/kyre",
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
    }


def test_step17b_default_is_fail_closed():
    assert s17b.step17b_enabled({}) is False
    with pytest.raises(s17b.MLBStep17BDisabledError):
        s17b.validate_step17b_startup({})


def test_step17b_startup_requires_single_worker_and_container():
    report = s17b.validate_step17b_startup(_env())
    assert report["web_concurrency"] == 1
    assert report["provider_workload_enabled"] is False
    assert report["database_secret_exposed"] is False

    bad = _env()
    bad["WEB_CONCURRENCY"] = "2"
    with pytest.raises(s17b.MLBStep17BIntegrityError):
        s17b.validate_step17b_startup(bad)

    bad = _env()
    bad[s17b.DEPLOYMENT_MODE_ENV] = "local"
    with pytest.raises(s17b.MLBStep17BIntegrityError):
        s17b.validate_step17b_startup(bad)


def test_step17b_refuses_legacy_runtime_scheduler_actionability_and_wagering():
    for key in (
        "MLB_PRODUCTION_RUNTIME_ENABLED",
        "MLB_PRODUCTION_SCHEDULER_ENABLED",
        "MLB_ACTIONABLE_OUTPUT_ENABLED",
        "MLB_WAGERING_ENABLED",
        "MLB_SUPABASE_REST_WRITE_ENABLED",
    ):
        bad = _env()
        bad[key] = "true"
        with pytest.raises(s17b.MLBStep17BIntegrityError):
            s17b.validate_step17b_startup(bad)


def test_step17b_requires_all_durable_gates():
    for key in (
        "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED",
        "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
        "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
        "MLB_STEP14B_DATABASE_READ_ENABLED",
        "MLB_STEP14B_DATABASE_WRITE_ENABLED",
    ):
        bad = _env()
        bad[key] = "false"
        with pytest.raises(s17b.MLBStep17BIntegrityError):
            s17b.validate_step17b_startup(bad)


def test_step17b_requires_secret_postgres_url_but_never_returns_it():
    report = s17b.validate_step17b_startup(_env())
    assert report["database_secret_configured"] is True
    rendered = str(report).lower()
    assert "user:secret@example.invalid" not in rendered
    assert "postgresql://" not in rendered

    bad = _env()
    bad["KYRE_DATABASE_URL"] = "https://example.invalid/db"
    with pytest.raises(s17b.MLBStep17BIntegrityError):
        s17b.validate_step17b_startup(bad)


def test_step17b_requires_exact_revision_and_matches_render_when_present():
    env = _env()
    env["RENDER_GIT_COMMIT"] = env[s17b.STEP17B_EXPECTED_REVISION_ENV]
    report = s17b.validate_step17b_startup(env)
    assert report["expected_revision"] == "a" * 40

    bad = _env()
    bad[s17b.STEP17B_EXPECTED_REVISION_ENV] = "abc"
    with pytest.raises(s17b.MLBStep17BIntegrityError):
        s17b.validate_step17b_startup(bad)

    bad = _env()
    bad["RENDER_GIT_COMMIT"] = "b" * 40
    with pytest.raises(s17b.MLBStep17BIntegrityError):
        s17b.validate_step17b_startup(bad)


def test_runtime_env_only_enables_durable_inner_gates_and_keeps_frozen_switches_off():
    runtime = s17b.build_runtime_env(_env())
    assert runtime["MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED"] == "true"
    assert runtime["MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED"] == "true"
    assert runtime["MLB_STEP14B_DATABASE_WRITE_ENABLED"] == "true"
    assert runtime["MLB_PRODUCTION_RUNTIME_ENABLED"] == "false"
    assert runtime["MLB_PRODUCTION_SCHEDULER_ENABLED"] == "false"
    assert runtime["MLB_ACTIONABLE_OUTPUT_ENABLED"] == "false"
    assert runtime["MLB_WAGERING_ENABLED"] == "false"


def test_control_cycle_builds_valid_checkpoint_and_releases_lease():
    calls = []
    lease = {
        "lease_key": "fake",
        "owner_id": "owner",
        "lease_token": "00000000-0000-0000-0000-000000000001",
        "fencing_generation": 1,
    }

    def load(**kwargs):
        calls.append(("load", kwargs))
        return {
            "found": False,
            "expected_head_version": 0,
            "scheduler_state_for_restart": None,
            "recovery_state_for_restart": None,
            "lease": lease,
        }

    def persist(**kwargs):
        calls.append(("persist", kwargs))
        envelope = kwargs["checkpoint_envelope"]
        assert envelope["slate_date"] == "2026-09-01"
        assert envelope["cycle_id"] is None
        assert envelope["scheduler_state"]["active_cycle_id"] is None
        return {
            "previous_checkpoint_version": 0,
            "saved_checkpoint_version": 1,
            "lease": lease,
        }

    def release(**kwargs):
        calls.append(("release", kwargs))
        return True

    result = s17b.run_one_control_cycle(
        env=_env(),
        owner_id="owner",
        slate_date="2026-09-01",
        now=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        load_restart_context=load,
        persist_checkpoint=persist,
        release_lease=release,
    )
    assert result["status"] == "completed"
    assert result["saved_checkpoint_version"] == 1
    assert result["recovered_from_durable_checkpoint"] is False
    assert result["scheduler_permit_granted"] is False
    assert result["provider_calls"] == 0
    assert result["sportsbook_calls"] == 0
    assert [row[0] for row in calls] == ["load", "persist", "release"]


def test_control_cycle_proves_recovery_version_advances_without_provider_workload():
    lease = {
        "lease_key": "fake",
        "owner_id": "owner",
        "lease_token": "00000000-0000-0000-0000-000000000001",
        "fencing_generation": 2,
    }
    prior_state = {
        "last_granted_slot_utc": None,
        "active_cycle_id": None,
        "active_cycle_slot_utc": None,
    }

    def load(**_kwargs):
        return {
            "found": True,
            "expected_head_version": 7,
            "scheduler_state_for_restart": prior_state,
            "recovery_state_for_restart": None,
            "lease": lease,
        }

    def persist(**kwargs):
        assert kwargs["checkpoint_envelope"]["scheduler_state"] == prior_state
        return {
            "previous_checkpoint_version": 7,
            "saved_checkpoint_version": 8,
            "lease": lease,
        }

    result = s17b.run_one_control_cycle(
        env=_env(),
        owner_id="owner",
        slate_date="2026-09-01",
        now=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        load_restart_context=load,
        persist_checkpoint=persist,
        release_lease=lambda **_kwargs: True,
    )
    assert result["previous_checkpoint_version"] == 7
    assert result["saved_checkpoint_version"] == 8
    assert result["recovered_from_durable_checkpoint"] is True
    assert result["provider_workload_executed"] is False


def test_control_cycle_releases_lease_best_effort_on_failure():
    released = []
    lease = {
        "lease_key": "fake",
        "owner_id": "owner",
        "lease_token": "00000000-0000-0000-0000-000000000001",
        "fencing_generation": 1,
    }

    def load(**_kwargs):
        return {
            "found": False,
            "expected_head_version": 0,
            "scheduler_state_for_restart": None,
            "recovery_state_for_restart": None,
            "lease": lease,
        }

    with pytest.raises(RuntimeError):
        s17b.run_one_control_cycle(
            env=_env(),
            owner_id="owner",
            slate_date="2026-09-01",
            now=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
            load_restart_context=load,
            persist_checkpoint=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
            release_lease=lambda **kwargs: released.append(kwargs) or True,
        )
    assert len(released) == 1


def test_always_on_loop_runs_one_leader_control_cycle_only():
    class FakeLeadership:
        acquired = True

        def check(self):
            return True

        def close(self):
            self.acquired = False

    def cycle_runner(*, env, owner_id, slate_date):
        assert env["MLB_PRODUCTION_RUNTIME_ENABLED"] == "false"
        assert env["MLB_PRODUCTION_SCHEDULER_ENABLED"] == "false"
        assert owner_id.startswith("render-mlb-step17b:")
        assert slate_date.startswith("2026-")
        return {
            "status": "completed",
            "saved_checkpoint_version": 3,
            "recovered_from_durable_checkpoint": True,
            "provider_calls": 0,
            "sportsbook_calls": 0,
        }

    async def scenario():
        stop = threading.Event()
        await s17b.run_always_on_loop(
            stop,
            env=_env(),
            leadership_acquirer=lambda _env: FakeLeadership(),
            cycle_runner=cycle_runner,
            max_iterations_for_test=1,
        )

    asyncio.run(scenario())
    status = s17b.get_step17b_status()
    assert status["control_cycle_count"] == 1
    assert status["success_count"] == 1
    assert status["failure_count"] == 0
    assert status["last_checkpoint_version"] == 3
    assert status["recovered_from_checkpoint"] is True
    assert status["provider_workload_cycle_count"] == 0
    assert status["provider_calls"] == 0
    assert status["running"] is False


def test_always_on_loop_stands_by_when_another_process_holds_leadership():
    async def scenario():
        stop = threading.Event()
        await s17b.run_always_on_loop(
            stop,
            env=_env(),
            leadership_acquirer=lambda _env: None,
            cycle_runner=lambda **_kwargs: pytest.fail("standby must not execute cycle"),
            max_iterations_for_test=1,
        )

    asyncio.run(scenario())
    status = s17b.get_step17b_status()
    assert status["leadership_miss_count"] == 1
    assert status["success_count"] == 0


def test_manifest_keeps_network_actionability_and_legacy_switches_false():
    manifest = s17b.controlled_always_on_manifest()
    assert manifest["background_control_task_allowed"] is True
    assert manifest["durable_restart_recovery_required"] is True
    assert manifest["legacy_production_runtime_allowed"] is False
    assert manifest["legacy_production_scheduler_allowed"] is False
    assert manifest["provider_workload_allowed"] is False
    assert manifest["sportsbook_workload_allowed"] is False
    assert manifest["actionable_output_allowed"] is False
    assert manifest["wagering_allowed"] is False


def test_status_is_sanitized_and_defensive_copy():
    first = s17b.get_step17b_status()
    first["role"] = "tampered"
    second = s17b.get_step17b_status()
    assert second["role"] != "tampered"
    assert "KYRE_DATABASE_URL" not in second
    rendered = str(second).lower()
    assert "user:secret@example.invalid" not in rendered
    assert "postgresql://" not in rendered
