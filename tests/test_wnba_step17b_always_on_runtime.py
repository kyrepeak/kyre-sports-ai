import asyncio
import threading

from sports_api import wnba_step17b_always_on_runtime as s17b


def _env():
    return {
        s17b.STEP17B_ENABLED_ENV: "true",
        s17b.STEP17B_LOOP_SECONDS_ENV: "30",
        s17b.STEP17B_EXPECTED_REVISION_ENV: "a" * 40,
        "WEB_CONCURRENCY": "1",
        "KYRE_DATABASE_URL": "postgresql://user:secret@example.invalid/kyre",
        "WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
    }


def test_step17b_startup_requires_one_worker_and_frozen_switches_off():
    report = s17b.validate_step17b_startup(_env())
    assert report["web_concurrency"] == 1
    assert report["database_secret_exposed"] is False
    assert report["leadership_lock_key"] == s17b.LEADERSHIP_LOCK_KEY

    bad = _env()
    bad["WEB_CONCURRENCY"] = "2"
    try:
        s17b.validate_step17b_startup(bad)
    except s17b.WNBAStep17BIntegrityError:
        pass
    else:
        raise AssertionError("Step 17B must refuse multiple Uvicorn workers")

    bad = _env()
    bad["WNBA_BOARD_SCHEDULER_ENABLED"] = "true"
    try:
        s17b.validate_step17b_startup(bad)
    except s17b.WNBAStep17BIntegrityError:
        return
    raise AssertionError("Step 17B must keep the frozen legacy scheduler switch off")


def test_step17b_runtime_env_enables_only_frozen_inner_gates():
    runtime = s17b.build_runtime_env(_env())
    assert runtime["WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED"] == "true"
    assert runtime["WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED"] == "true"
    assert runtime["WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED"] == "true"
    assert runtime["WNBA_PRODUCTION_RUNTIME_ENABLED"] == "false"
    assert runtime["WNBA_BOARD_SCHEDULER_ENABLED"] == "false"
    assert runtime["WNBA_SUPABASE_WRITE_ENABLED"] == "false"


def test_step17b_request_is_one_bounded_session_and_tick():
    request = s17b.build_step17b_request("2026-08-28")
    parent = request["supervisor_request"]
    assert parent["season"] == 2026
    assert parent["initial_slate_date"] == "2026-08-28"
    assert parent["max_supervisor_sessions"] == 1
    assert parent["scheduler_cycles_per_session"] == 1
    assert parent["scheduler_sleep_budget_seconds_per_session"] == 0
    assert request["max_recovery_attempts"] == 2


def test_step17b_one_cycle_uses_durable_runner_without_secret_output():
    calls = []

    def fake_runner(request, *, owner_id, env):
        calls.append((request, owner_id, env))
        return {
            "status": "completed",
            "saved_checkpoint_version": 7,
            "recovered_from_durable_checkpoint": True,
        }

    result = s17b.run_one_cycle(
        env=_env(),
        owner_id="test-owner",
        slate_date="2026-08-28",
        runner=fake_runner,
    )
    assert result["saved_checkpoint_version"] == 7
    assert calls[0][1] == "test-owner"
    assert calls[0][2]["WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED"] == "true"
    assert "secret" not in str(result).lower()


def test_step17b_always_on_loop_runs_one_leader_cycle():
    class FakeLeadership:
        acquired = True

        def check(self):
            return True

        def close(self):
            self.acquired = False

    def acquire(_env):
        return FakeLeadership()

    def cycle_runner(*, env, owner_id, slate_date):
        assert env["WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED"] == "true"
        assert owner_id.startswith("render-step17b:")
        assert slate_date.startswith("2026-")
        return {
            "status": "completed",
            "saved_checkpoint_version": 3,
            "recovered_from_durable_checkpoint": True,
        }

    async def scenario():
        stop = threading.Event()
        await s17b.run_always_on_loop(
            stop,
            env=_env(),
            leadership_acquirer=acquire,
            cycle_runner=cycle_runner,
            max_iterations_for_test=1,
        )

    asyncio.run(scenario())
    status = s17b.get_step17b_status()
    assert status["cycle_count"] == 1
    assert status["success_count"] == 1
    assert status["failure_count"] == 0
    assert status["last_checkpoint_version"] == 3
    assert status["recovered_from_checkpoint"] is True
    assert status["running"] is False


if __name__ == "__main__":
    test_step17b_startup_requires_one_worker_and_frozen_switches_off()
    test_step17b_runtime_env_enables_only_frozen_inner_gates()
    test_step17b_request_is_one_bounded_session_and_tick()
    test_step17b_one_cycle_uses_durable_runner_without_secret_output()
    test_step17b_always_on_loop_runs_one_leader_cycle()
    print("STEP17B_ALWAYS_ON_RUNTIME_TESTS_OK")
