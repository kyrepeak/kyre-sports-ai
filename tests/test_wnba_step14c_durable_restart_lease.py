from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14b_database_checkpoint_adapter as step14b
from sports_api import wnba_step14c_durable_restart_lease as s14c

TOKEN = "11111111-1111-4111-8111-111111111111"


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


def safe_env():
    return {
        "WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED": "true",
        "WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED": "true",
        "WNBA_STEP14B_DATABASE_READ_ENABLED": "true",
        "WNBA_STEP14B_DATABASE_WRITE_ENABLED": "true",
        "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED": "true",
        "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED": "true",
        "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED": "true",
        "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED": "true",
        "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED": "true",
        "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED": "true",
        "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED": "true",
        "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED": "true",
        "WNBA_STEP12A_SHADOW_RUNNER_ENABLED": "true",
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


def request(initial_state=None, slate="2026-08-28"):
    parent = step13b.build_step13b_request(
        season=2026,
        initial_slate_date=slate,
        max_supervisor_sessions=1,
        max_supervisor_runtime_seconds=1,
        max_total_intersession_sleep_seconds=0,
        initial_previous_state=initial_state,
    )
    return step13c.build_step13c_request(
        supervisor_request=parent,
        max_recovery_attempts=1,
        base_recovery_backoff_seconds=0,
        max_total_recovery_sleep_seconds=0,
    )


def source_response(cycle_index=8):
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": step13c.SCHEMA_VERSION,
        "generated_at_utc": "2026-08-28T18:20:00+00:00",
        "status": "completed",
        "health": "healthy",
        "lineage": {
            "step13b_frozen_sha": step14a.STEP13B_FROZEN_SHA,
            "latest_step13b_supervisor_content_sha256": "a" * 64,
            "step13a_frozen_sha": step14a.STEP13A_FROZEN_SHA,
            "step12d_frozen_sha": step14a.step13_release.STEP12D_FROZEN_SHA,
        },
        "final_controller_state_for_restart_handoff": {
            "season": 2026,
            "slate_date": "2026-08-28",
            "cycle_index": cycle_index,
            "next_refresh_due_at_utc": "2026-08-28T18:21:00+00:00",
            "circuit_state": "closed",
        },
    }
    response["reliability_content_sha256"] = canonical({k: deepcopy(v) for k, v in response.items() if k not in {"generated_at_utc", "reliability_content_sha256"}})
    return response


def lease_row(*, owner="worker-a", token=TOKEN, generation=1,
              acquired="2026-08-28T18:00:00+00:00",
              renewed="2026-08-28T18:00:00+00:00",
              expires="2026-08-28T19:00:00+00:00",
              slate="2026-08-28"):
    return (
        s14c.lease_key_for_slate(slate), owner, token, generation,
        acquired, renewed, expires,
    )


class FakeCursor:
    def __init__(self, script):
        self.script = list(script)
        self.current = None
        self.rowcount = -1
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None):
        if not self.script:
            raise AssertionError(f"unexpected SQL {sql}")
        step = self.script.pop(0)
        fragment = step.get("contains")
        if fragment and fragment not in sql:
            raise AssertionError(f"expected {fragment!r} in SQL")
        self.calls.append((sql, params))
        if step.get("raise") is not None:
            raise step["raise"]
        self.current = step
        self.rowcount = step.get("rowcount", -1)

    def fetchone(self):
        return None if self.current is None else self.current.get("fetchone")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, script):
        self.cursor_obj = FakeCursor(script)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self): return self.cursor_obj
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): self.closed = True


def factory_for(script):
    box = {}
    def factory():
        box["connection"] = FakeConnection(script)
        return box["connection"]
    return factory, box


class SequenceFactory:
    def __init__(self, scripts):
        self.scripts = [list(x) for x in scripts]
        self.connections = []

    def __call__(self):
        if not self.scripts:
            raise AssertionError("unexpected connection")
        conn = FakeConnection(self.scripts.pop(0))
        self.connections.append(conn)
        return conn


def schema_step(present=True):
    return {"contains": "to_regclass", "fetchone": (present,)}


def acquire_script(row=None):
    return [schema_step(), {"contains": "ON CONFLICT (lease_key)", "fetchone": row}]


def renew_script(row=None):
    return [schema_step(), {"contains": "fencing_generation = %s", "fetchone": row}]


def release_script(key=None):
    return [schema_step(), {"contains": "DELETE FROM kyre_runtime.wnba_runtime_leases", "fetchone": None if key is None else (key,)}]


def loaded_result(*, found=False, version=None, state=None):
    return {
        "found": found,
        "checkpoint_version": version,
        "checkpoint_key": step14a.checkpoint_key_for_slate("2026-08-28"),
        "controller_state_for_restart": deepcopy(state),
    }


def saved_result(envelope, *, version=1, status="created"):
    return {
        "checkpoint_version": version,
        "status": status,
        "envelope_content_sha256": envelope["envelope_content_sha256"],
        "controller_state_sha256": envelope["controller_state_sha256"],
    }


class Tests(unittest.TestCase):
    def test_01_default_off(self):
        self.assertFalse(s14c.step14c_durable_restart_lease_enabled({}))
        self.assertFalse(s14c.DEFAULT_ENABLED)

    def test_02_capability_boundary(self):
        for value in (s14c.DURABLE_RESTART_RECOVERY_ALLOWED, s14c.DURABLE_DISTRIBUTED_LEASE_ALLOWED, s14c.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED, s14c.FENCING_GENERATION_REQUIRED):
            self.assertTrue(value)
        for value in (s14c.PERSISTENCE_RUNTIME_ENABLED, s14c.PRODUCTION_ACTIVATION_ALLOWED, s14c.SUPABASE_REST_WRITE_ALLOWED, s14c.BACKGROUND_DAEMON_ALLOWED, s14c.BACKGROUND_THREAD_ALLOWED):
            self.assertFalse(value)

    def test_03_step14c_gate_required(self):
        env = safe_env(); env["WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED"] = "false"
        with self.assertRaises(s14c.WNBAStep14CDurableRuntimeDisabledError):
            s14c.verify_step14c_lease_schema(env=env, connection_factory=lambda: None)

    def test_04_parent_gates_required(self):
        for key in ("WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED", "WNBA_STEP14B_DATABASE_READ_ENABLED", "WNBA_STEP14B_DATABASE_WRITE_ENABLED", "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED", "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED"):
            env = safe_env(); env[key] = "false"
            with self.assertRaises(s14c.WNBAStep14CDurableRuntimeDisabledError):
                s14c.verify_step14c_lease_schema(env=env, connection_factory=lambda: None)

    def test_05_unsafe_global_switches_refused(self):
        for key in ("WNBA_PRODUCTION_RUNTIME_ENABLED", "WNBA_BOARD_SCHEDULER_ENABLED", "WNBA_PERSISTENCE_ENABLED", "WNBA_SUPABASE_WRITE_ENABLED", "WNBA_WAGERING_ENABLED"):
            env = safe_env(); env[key] = "true"
            with self.assertRaises(s14c.WNBAStep14CDurableRuntimeDisabledError):
                s14c.verify_step14c_lease_schema(env=env, connection_factory=lambda: None)

    def test_06_lease_sql_is_additive(self):
        text = Path(s14c.LEASE_SQL_SCHEMA_PATH).read_text()
        self.assertIn("wnba_runtime_leases", text)
        self.assertNotIn("ALTER TABLE kyre_runtime.wnba_runtime_checkpoints", text)
        self.assertNotIn("ALTER TABLE kyre_runtime.wnba_runtime_checkpoint_heads", text)

    def test_07_lease_sql_hash_exact(self):
        self.assertEqual(hashlib.sha256(Path(s14c.LEASE_SQL_SCHEMA_PATH).read_bytes()).hexdigest(), s14c.LEASE_SQL_SCHEMA_SHA256)

    def test_08_lease_key_is_slate_scoped(self):
        self.assertNotEqual(s14c.lease_key_for_slate("2026-08-28"), s14c.lease_key_for_slate("2026-08-29"))
        self.assertTrue(s14c.lease_key_for_slate("2026-08-28").endswith(":scheduler-lease"))

    def test_09_required_ttl_covers_bounded_runtime(self):
        self.assertEqual(s14c.required_lease_ttl_seconds(request()), 61)

    def test_10_orchestrator_rejects_undersized_ttl(self):
        with self.assertRaises(s14c.WNBAStep14CDurableRuntimeInputError):
            s14c.run_step14c_durable_restart_lease(request(), owner_id="worker-a", env=safe_env(), lease_ttl_seconds=60)

    def test_11_owner_id_validation(self):
        factory, _ = factory_for(acquire_script(lease_row()))
        with self.assertRaises(s14c.WNBAStep14CDurableRuntimeInputError):
            s14c.acquire_step14c_lease(slate_date="2026-08-28", owner_id="", lease_ttl_seconds=61, env=safe_env(), connection_factory=factory)

    def test_12_verify_schema_success_is_read_only(self):
        factory, box = factory_for([schema_step()])
        result = s14c.verify_step14c_lease_schema(env=safe_env(), connection_factory=factory)
        self.assertTrue(result["table_present"])
        self.assertEqual(box["connection"].commits, 0)
        self.assertGreaterEqual(box["connection"].rollbacks, 1)

    def test_13_verify_schema_missing_fails_closed(self):
        factory, _ = factory_for([schema_step(False)])
        with self.assertRaises(s14c.WNBAStep14CLeaseSchemaError):
            s14c.verify_step14c_lease_schema(env=safe_env(), connection_factory=factory)

    def test_14_acquire_success_commits_fenced_handle(self):
        factory, box = factory_for(acquire_script(lease_row()))
        handle = s14c.acquire_step14c_lease(slate_date="2026-08-28", owner_id="worker-a", lease_ttl_seconds=61, env=safe_env(), connection_factory=factory, token_factory=lambda: TOKEN)
        self.assertEqual(handle["fencing_generation"], 1)
        self.assertEqual(handle["lease_token"], TOKEN)
        self.assertEqual(box["connection"].commits, 1)

    def test_15_acquire_duplicate_unexpired_is_rejected(self):
        factory, box = factory_for(acquire_script(None))
        with self.assertRaises(s14c.WNBAStep14CLeaseUnavailableError):
            s14c.acquire_step14c_lease(slate_date="2026-08-28", owner_id="worker-b", lease_ttl_seconds=61, env=safe_env(), connection_factory=factory, token_factory=lambda: TOKEN)
        self.assertGreaterEqual(box["connection"].rollbacks, 1)

    def test_16_acquire_invalid_token_factory_fails_before_db(self):
        with self.assertRaises(s14c.WNBAStep14CDurableRuntimeInputError):
            s14c.acquire_step14c_lease(slate_date="2026-08-28", owner_id="worker-a", lease_ttl_seconds=61, env=safe_env(), connection_factory=lambda: None, token_factory=lambda: "bad")

    def test_17_acquire_database_error_is_wrapped_and_rolled_back(self):
        factory, box = factory_for([schema_step(), {"contains": "ON CONFLICT", "raise": RuntimeError("db") }])
        with self.assertRaises(s14c.WNBAStep14CDatabaseError):
            s14c.acquire_step14c_lease(slate_date="2026-08-28", owner_id="worker-a", lease_ttl_seconds=61, env=safe_env(), connection_factory=factory, token_factory=lambda: TOKEN)
        self.assertGreaterEqual(box["connection"].rollbacks, 1)

    def test_18_renew_success_keeps_same_fence(self):
        handle = s14c._normalize_lease_row(lease_row(), expected_key=s14c.lease_key_for_slate("2026-08-28"))
        row = lease_row(renewed="2026-08-28T18:01:00+00:00", expires="2026-08-28T19:01:00+00:00")
        factory, box = factory_for(renew_script(row))
        renewed = s14c.renew_step14c_lease(handle=handle, lease_ttl_seconds=61, env=safe_env(), connection_factory=factory)
        self.assertEqual(renewed["fencing_generation"], handle["fencing_generation"])
        self.assertEqual(box["connection"].commits, 1)

    def test_19_renew_stale_or_expired_handle_is_fenced(self):
        handle = s14c._normalize_lease_row(lease_row(), expected_key=s14c.lease_key_for_slate("2026-08-28"))
        factory, _ = factory_for(renew_script(None))
        with self.assertRaises(s14c.WNBAStep14CLeaseLostError):
            s14c.renew_step14c_lease(handle=handle, lease_ttl_seconds=61, env=safe_env(), connection_factory=factory)

    def test_20_release_success_requires_full_fence_identity(self):
        handle = s14c._normalize_lease_row(lease_row(), expected_key=s14c.lease_key_for_slate("2026-08-28"))
        factory, box = factory_for(release_script(handle["lease_key"]))
        self.assertTrue(s14c.release_step14c_lease(handle=handle, env=safe_env(), connection_factory=factory))
        params = box["connection"].cursor_obj.calls[-1][1]
        self.assertEqual(params, (handle["lease_key"], "worker-a", TOKEN, 1))

    def test_21_stale_release_cannot_delete_newer_lease(self):
        handle = s14c._normalize_lease_row(lease_row(), expected_key=s14c.lease_key_for_slate("2026-08-28"))
        factory, _ = factory_for(release_script(None))
        with self.assertRaises(s14c.WNBAStep14CLeaseLostError):
            s14c.release_step14c_lease(handle=handle, env=safe_env(), connection_factory=factory)

    def test_22_takeover_generation_can_advance(self):
        row = lease_row(owner="worker-b", generation=2)
        factory, _ = factory_for(acquire_script(row))
        handle = s14c.acquire_step14c_lease(slate_date="2026-08-28", owner_id="worker-b", lease_ttl_seconds=61, env=safe_env(), connection_factory=factory, token_factory=lambda: TOKEN)
        self.assertEqual(handle["fencing_generation"], 2)

    def test_23_recovered_request_injects_exact_state_and_rehashes(self):
        original = request()
        state = {"season": 2026, "slate_date": "2026-08-28", "cycle_index": 12}
        rebuilt = s14c.build_recovered_step13c_request(step13c_request=original, durable_controller_state=state)
        self.assertEqual(rebuilt["supervisor_request"]["initial_previous_state"], state)
        self.assertNotEqual(rebuilt["request_content_sha256"], original["request_content_sha256"])

    def test_24_cold_start_preserves_caller_supplied_state(self):
        state = {"season": 2026, "slate_date": "2026-08-28", "cycle_index": 3}
        rebuilt = s14c.build_recovered_step13c_request(step13c_request=request(state), durable_controller_state=None)
        self.assertEqual(rebuilt["supervisor_request"]["initial_previous_state"], state)

    def test_25_wrong_slate_durable_state_is_rejected(self):
        state = {"season": 2026, "slate_date": "2026-08-29", "cycle_index": 3}
        with self.assertRaises(s14c.WNBAStep14CDurableRuntimeIntegrityError):
            s14c.build_recovered_step13c_request(step13c_request=request(), durable_controller_state=state)

    def test_26_tampered_frozen_request_is_rejected(self):
        bad = request(); bad["supervisor_request"]["max_supervisor_sessions"] = 2
        with self.assertRaises(s14c.WNBAStep14CDurableRuntimeIntegrityError):
            s14c.build_recovered_step13c_request(step13c_request=bad, durable_controller_state=None)

    def test_27_load_restart_checkpoint_uses_verified_step14b_result(self):
        sentinel = {"found": False, "checkpoint_version": None, "checkpoint_key": "x", "controller_state_for_restart": None}
        with patch.object(s14c.step14b, "load_step14b_checkpoint", return_value=sentinel) as load, patch.object(s14c.step14b, "validate_step14b_adapter_result", return_value=sentinel) as validate:
            result = s14c.load_step14c_restart_checkpoint(slate_date="2026-08-28", env=safe_env(), checkpoint_connection_factory=lambda: None)
        self.assertIs(result, sentinel)
        load.assert_called_once()
        validate.assert_called_once_with(sentinel)

    def test_28_orchestrator_cold_start_persists_version_one_then_releases(self):
        key = s14c.lease_key_for_slate("2026-08-28")
        lease_factory = SequenceFactory([
            acquire_script(lease_row()),
            renew_script(lease_row(renewed="2026-08-28T18:01:00+00:00", expires="2026-08-28T19:01:00+00:00")),
            release_script(key),
        ])
        saved_calls = []
        def save(**kwargs):
            saved_calls.append(kwargs)
            return saved_result(kwargs["checkpoint_envelope"], version=1, status="created")
        with patch.object(s14c, "load_step14c_restart_checkpoint", return_value=loaded_result()), patch.object(s14c.step14b, "save_step14b_checkpoint", side_effect=save), patch.object(s14c.step14b, "validate_step14b_adapter_result", side_effect=lambda x: x):
            result = s14c.run_step14c_durable_restart_lease(request(), owner_id="worker-a", env=safe_env(), lease_ttl_seconds=61, lease_connection_factory=lease_factory, token_factory=lambda: TOKEN, step13c_runner=lambda req, **kw: source_response(8), generated_at_utc="2026-08-28T18:02:00+00:00")
        self.assertFalse(result["recovered_from_durable_checkpoint"])
        self.assertEqual(result["saved_checkpoint_version"], 1)
        self.assertEqual(saved_calls[0]["expected_head_version"], 0)
        self.assertEqual(len(lease_factory.connections), 3)

    def test_29_orchestrator_recovers_exact_state_and_uses_loaded_cas_version(self):
        state = {"season": 2026, "slate_date": "2026-08-28", "cycle_index": 44}
        key = s14c.lease_key_for_slate("2026-08-28")
        lease_factory = SequenceFactory([acquire_script(lease_row(generation=4)), renew_script(lease_row(generation=4, renewed="2026-08-28T18:01:00+00:00", expires="2026-08-28T19:01:00+00:00")), release_script(key)])
        observed = {}; saved_calls = []
        def runner(req, **kw):
            observed["state"] = deepcopy(req["supervisor_request"]["initial_previous_state"])
            return source_response(45)
        def save(**kwargs):
            saved_calls.append(kwargs)
            return saved_result(kwargs["checkpoint_envelope"], version=4, status="advanced")
        with patch.object(s14c, "load_step14c_restart_checkpoint", return_value=loaded_result(found=True, version=3, state=state)), patch.object(s14c.step14b, "save_step14b_checkpoint", side_effect=save), patch.object(s14c.step14b, "validate_step14b_adapter_result", side_effect=lambda x: x):
            result = s14c.run_step14c_durable_restart_lease(request(), owner_id="worker-a", env=safe_env(), lease_ttl_seconds=61, lease_connection_factory=lease_factory, token_factory=lambda: TOKEN, step13c_runner=runner, generated_at_utc="2026-08-28T18:02:00+00:00")
        self.assertTrue(result["recovered_from_durable_checkpoint"])
        self.assertEqual(observed["state"], state)
        self.assertEqual(saved_calls[0]["expected_head_version"], 3)
        self.assertEqual(result["lease_fencing_generation"], 4)

    def test_30_lease_unavailable_prevents_runtime_from_starting(self):
        lease_factory = SequenceFactory([acquire_script(None)])
        called = {"runner": False}
        def runner(*args, **kwargs): called["runner"] = True
        with self.assertRaises(s14c.WNBAStep14CLeaseUnavailableError):
            s14c.run_step14c_durable_restart_lease(request(), owner_id="worker-a", env=safe_env(), lease_ttl_seconds=61, lease_connection_factory=lease_factory, token_factory=lambda: TOKEN, step13c_runner=runner)
        self.assertFalse(called["runner"])

    def test_31_noncompleted_runtime_is_never_persisted_and_lease_is_released(self):
        key = s14c.lease_key_for_slate("2026-08-28")
        lease_factory = SequenceFactory([acquire_script(lease_row()), release_script(key)])
        bad_response = source_response(); bad_response["status"] = "recovery_exhausted"
        saved = {"called": False}
        def save(**kwargs): saved["called"] = True
        with patch.object(s14c, "load_step14c_restart_checkpoint", return_value=loaded_result()), patch.object(s14c.step14b, "save_step14b_checkpoint", side_effect=save):
            with self.assertRaises(s14c.WNBAStep14CDurableRuntimeIntegrityError):
                s14c.run_step14c_durable_restart_lease(request(), owner_id="worker-a", env=safe_env(), lease_ttl_seconds=61, lease_connection_factory=lease_factory, token_factory=lambda: TOKEN, step13c_runner=lambda req, **kw: bad_response)
        self.assertFalse(saved["called"])
        self.assertEqual(len(lease_factory.connections), 2)

    def test_32_lost_lease_before_save_fences_stale_writer(self):
        key = s14c.lease_key_for_slate("2026-08-28")
        lease_factory = SequenceFactory([acquire_script(lease_row()), renew_script(None), release_script(key)])
        saved = {"called": False}
        def save(**kwargs): saved["called"] = True
        with patch.object(s14c, "load_step14c_restart_checkpoint", return_value=loaded_result()), patch.object(s14c.step14b, "save_step14b_checkpoint", side_effect=save):
            with self.assertRaises(s14c.WNBAStep14CLeaseLostError):
                s14c.run_step14c_durable_restart_lease(request(), owner_id="worker-a", env=safe_env(), lease_ttl_seconds=61, lease_connection_factory=lease_factory, token_factory=lambda: TOKEN, step13c_runner=lambda req, **kw: source_response())
        self.assertFalse(saved["called"])

    def test_33_runtime_result_hash_tamper_fails_validation(self):
        result = {
            "data_type": "wnba_step14c_durable_restart_lease_result",
            "schema_version": s14c.SCHEMA_VERSION,
            "runtime_version": s14c.RUNTIME_VERSION,
            "guardrails": {"durable_restart_recovery": True, "durable_distributed_lease": True, "cross_process_duplicate_run_guard": True, "fencing_generation_enforced": True, "checkpoint_cas_enforced": True, "background_daemon_started": False, "background_thread_spawned": False, "supabase_rest_write": False, "production_activation": False, "public_fastapi_activation": False, "wager_action": False, "basketball_model_mutation": False, "ranking_mutation": False},
            "generated_at_utc": "2026-08-28T18:00:00+00:00",
        }
        result["runtime_content_sha256"] = canonical({k: deepcopy(v) for k, v in result.items() if k not in {"generated_at_utc", "runtime_content_sha256"}})
        result["schema_version"] = "tampered"
        with self.assertRaises(s14c.WNBAStep14CDurableRuntimeIntegrityError):
            s14c.validate_step14c_runtime_result(result)

    def test_34_no_background_thread_or_daemon_capability(self):
        self.assertFalse(s14c.BACKGROUND_DAEMON_ALLOWED)
        self.assertFalse(s14c.BACKGROUND_THREAD_ALLOWED)
        text = Path("sports_api/wnba_step14c_durable_restart_lease.py").read_text()
        self.assertNotIn("threading.Thread", text)
        self.assertNotIn("daemon=True", text)

    def test_35_frozen_parent_boundaries_remain_exact(self):
        self.assertEqual(s14c.STEP14B_FROZEN_SHA, "dfea123c0702331ecccf3ca285baf1d69b8f3c2e")
        self.assertFalse(step14b.DURABLE_RESTART_RECOVERY_ALLOWED)
        self.assertFalse(step14b.DURABLE_DISTRIBUTED_LEASE_ALLOWED)
        self.assertFalse(step14a.DURABLE_DISTRIBUTED_LEASE_ALLOWED)
        self.assertFalse(step13c.DURABLE_DISTRIBUTED_LEASE_ALLOWED)


if __name__ == "__main__":
    unittest.main()
