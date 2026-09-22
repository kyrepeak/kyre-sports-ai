from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step16b_production_lifecycle as step16b
from sports_api import wnba_step16c_live_postgres_canary as s16c

TOKEN = "11111111-1111-4111-8111-111111111111"
SLATE = "2026-01-16"


def canonical(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    ).hexdigest()


def safe_env():
    return {
        "WNBA_STEP16C_LIVE_POSTGRES_CANARY_ENABLED": "true",
        "WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED": "true",
        "KYRE_DATABASE_URL": "postgresql://canary:placeholder@db.example.invalid:5432/kyre",
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


def request():
    parent = step13b.build_step13b_request(
        season=2026,
        initial_slate_date=SLATE,
        max_supervisor_sessions=1,
        max_supervisor_runtime_seconds=1,
        max_total_intersession_sleep_seconds=0,
    )
    return step13c.build_step13c_request(
        supervisor_request=parent,
        max_recovery_attempts=1,
        base_recovery_backoff_seconds=0,
        max_total_recovery_sleep_seconds=0,
    )


def source_response(cycle_index=1):
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": step13c.SCHEMA_VERSION,
        "generated_at_utc": "2026-08-28T20:12:00+00:00",
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
            "slate_date": SLATE,
            "cycle_index": cycle_index,
            "next_refresh_due_at_utc": "2026-08-28T20:13:00+00:00",
            "circuit_state": "closed",
        },
    }
    response["reliability_content_sha256"] = canonical(
        {
            key: deepcopy(value)
            for key, value in response.items()
            if key not in {"generated_at_utc", "reliability_content_sha256"}
        }
    )
    return response


def lease_key():
    return s16c.step14c.lease_key_for_slate(SLATE)


def lease_row(*, renewed="2026-08-28T20:00:00+00:00", expires="2026-08-28T21:00:00+00:00"):
    return (
        lease_key(),
        "step16c-ci-owner",
        TOKEN,
        1,
        "2026-08-28T20:00:00+00:00",
        renewed,
        expires,
    )


class FakeCursor:
    def __init__(self, script):
        self.script = list(script)
        self.current = None
        self.closed = False

    def execute(self, sql, params=None):
        if not self.script:
            raise AssertionError(f"unexpected SQL: {sql}")
        step = self.script.pop(0)
        fragment = step.get("contains")
        if fragment and fragment not in sql:
            raise AssertionError(f"expected {fragment!r} in SQL")
        self.current = step

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

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class SequenceFactory:
    def __init__(self, scripts):
        self.scripts = [list(script) for script in scripts]
        self.connections = []

    def __call__(self):
        if not self.scripts:
            raise AssertionError("unexpected connection")
        connection = FakeConnection(self.scripts.pop(0))
        self.connections.append(connection)
        return connection


def schema_step():
    return {"contains": "to_regclass", "fetchone": (True,)}


def acquire_script():
    return [schema_step(), {"contains": "ON CONFLICT (lease_key)", "fetchone": lease_row()}]


def renew_script():
    return [
        schema_step(),
        {
            "contains": "fencing_generation = %s",
            "fetchone": lease_row(renewed="2026-08-28T20:01:00+00:00", expires="2026-08-28T21:01:00+00:00"),
        },
    ]


def release_script():
    return [
        schema_step(),
        {"contains": "DELETE FROM kyre_runtime.wnba_runtime_leases", "fetchone": (lease_key(),)},
    ]


def loaded_result():
    return {
        "found": False,
        "checkpoint_version": None,
        "checkpoint_key": step14a.checkpoint_key_for_slate(SLATE),
        "controller_state_for_restart": None,
    }


def saved_result(envelope):
    return {
        "checkpoint_version": 1,
        "status": "created",
        "envelope_content_sha256": envelope["envelope_content_sha256"],
        "controller_state_sha256": envelope["controller_state_sha256"],
    }


class Tests(unittest.TestCase):
    def test_01_default_off(self):
        self.assertFalse(s16c.DEFAULT_ENABLED)
        self.assertFalse(s16c.step16c_canary_enabled({}))

    def test_02_exact_step16b_parent_identity(self):
        self.assertEqual(s16c.STEP16B_CERTIFIED_SHA, "f898ca410c10db59f635888166d1666a952d8bd7")
        self.assertEqual(s16c.STEP16B_CONTRACT_ID, "wnba_step16b_production_packaging_lifecycle_2026_regular_v1")
        self.assertEqual(s16c.STEP16B_CONTRACT_CONTENT_SHA256, "bcc79487cacf86bfb65e94ad0de2b8906c2bca1546ec1afd76ddc413ad30dd1e")

    def test_03_live_evidence_hash_valid(self):
        evidence = s16c.load_step16c_live_evidence()
        self.assertEqual(evidence["evidence_content_sha256"], s16c.LIVE_EVIDENCE_CONTENT_SHA256)

    def test_04_live_project_identity_and_health(self):
        evidence = s16c.validate_step16c_live_evidence(s16c.load_step16c_live_evidence())
        project = evidence["supabase_project"]
        self.assertEqual(project["ref"], "jqajcdckalsfizbvngiu")
        self.assertEqual(project["status"], "ACTIVE_HEALTHY")
        self.assertEqual(project["postgres_engine"], "17")

    def test_05_live_canary_started_and_ended_clean(self):
        live = s16c.load_step16c_live_evidence()["live_results"]
        self.assertEqual((live["baseline_checkpoint_rows"], live["baseline_checkpoint_head_rows"], live["baseline_lease_rows"]), (0, 0, 0))
        self.assertEqual((live["post_rollback_checkpoint_rows"], live["post_rollback_checkpoint_head_rows"], live["post_rollback_lease_rows"]), (0, 0, 0))
        self.assertTrue(live["transaction_rolled_back"])

    def test_06_live_lease_fencing_semantics(self):
        live = s16c.load_step16c_live_evidence()["live_results"]
        self.assertEqual(live["initial_fencing_generation"], 1)
        self.assertEqual(live["duplicate_active_acquire_rows"], 0)
        self.assertEqual(live["owner_renew_rows"], 1)
        self.assertEqual(live["wrong_owner_renew_rows"], 0)
        self.assertEqual(live["owner_release_rows"], 1)

    def test_07_live_checkpoint_round_trip_exact(self):
        live = s16c.load_step16c_live_evidence()["live_results"]
        self.assertTrue(live["checkpoint_load_round_trip_exact"])
        self.assertEqual(live["loaded_envelope_sha256"], s16c.EXPECTED_ENVELOPE_SHA256)
        self.assertEqual(live["loaded_controller_state_sha256"], s16c.EXPECTED_CONTROLLER_STATE_SHA256)

    def test_08_live_execution_boundary_is_split_layer(self):
        boundary = s16c.load_step16c_live_evidence()["execution_boundary"]
        self.assertTrue(boundary["live_postgresql_used"])
        self.assertTrue(boundary["frozen_step14b_step14c_sql_semantics_exercised_live"])
        self.assertFalse(boundary["direct_python_psycopg_live_connection"])
        self.assertFalse(boundary["deployed_fastapi_container_connected_live"])
        self.assertFalse(boundary["bound_step14c_python_runner_executed_live"])

    def test_09_safety_contract_all_false(self):
        self.assertTrue(s16c.SAFETY_CONTRACT)
        self.assertTrue(all(value is False for value in s16c.SAFETY_CONTRACT.values()))
        self.assertFalse(s16c.PRODUCTION_ACTIVATION_ALLOWED)
        self.assertFalse(s16c.CONTROLLED_PRODUCTION_ACTIVATION_READY)

    def test_10_manifest_certifies_canary_but_not_production(self):
        manifest = s16c.build_step16c_canary_manifest(env=safe_env(), generated_at_utc="2026-08-28T20:12:00+00:00")
        self.assertTrue(manifest["live_database_canary"]["certified"])
        self.assertTrue(manifest["bound_runner_canary"]["exact_step16b_bound_step14c_runner"])
        self.assertFalse(manifest["bound_runner_canary"]["direct_psycopg_live_connection_certified"])
        self.assertTrue(manifest["phase_boundary"]["controlled_production_activation_not_authorized"])

    def test_11_manifest_hash_stable_across_generation_time(self):
        first = s16c.build_step16c_canary_manifest(env=safe_env(), generated_at_utc="2026-08-28T20:12:00+00:00")
        second = s16c.build_step16c_canary_manifest(env=safe_env(), generated_at_utc="2026-08-29T01:12:00+00:00")
        self.assertNotEqual(first["generated_at_utc"], second["generated_at_utc"])
        self.assertEqual(first["manifest_content_sha256"], second["manifest_content_sha256"])

    def test_12_step16c_gate_required(self):
        env = safe_env(); env["WNBA_STEP16C_LIVE_POSTGRES_CANARY_ENABLED"] = "false"
        with self.assertRaises(s16c.WNBAStep16CCanaryDisabledError):
            s16c.build_step16c_canary_manifest(env=env)

    def test_13_step16b_lifecycle_gate_required(self):
        env = safe_env(); env["WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED"] = "false"
        with self.assertRaises(s16c.WNBAStep16CCanaryDisabledError):
            s16c.build_step16c_canary_manifest(env=env)

    def test_14_unsafe_activation_switches_are_rejected(self):
        for key in (
            "WNBA_PRODUCTION_RUNTIME_ENABLED",
            "WNBA_BOARD_SCHEDULER_ENABLED",
            "WNBA_PERSISTENCE_ENABLED",
            "WNBA_SUPABASE_WRITE_ENABLED",
            "WNBA_WAGERING_ENABLED",
            "WNBA_STEP12_SCHEDULER_ENABLED",
        ):
            env = safe_env(); env[key] = "true"
            with self.subTest(key=key):
                with self.assertRaises(s16c.WNBAStep16CCanaryDisabledError):
                    s16c.build_step16c_canary_manifest(env=env)

    def test_15_direct_psycopg_path_is_refused_in_step16c_ci_canary(self):
        with self.assertRaises(s16c.WNBAStep16CCanaryDisabledError):
            s16c.run_step16c_bound_runner_canary(
                request(), owner_id="step16c-ci-owner", env=safe_env(), lease_ttl_seconds=61,
                lease_connection_factory=None, checkpoint_connection_factory=None,
            )

    def test_16_exact_step16b_bound_runner_identity(self):
        runner = step16b.get_step16b_runtime_binding(safe_env())
        self.assertIs(runner, s16c.step14c.run_step14c_durable_restart_lease)

    def test_17_bound_runner_canary_invokes_frozen_step14c_path(self):
        lease_factory = SequenceFactory([acquire_script(), renew_script(), release_script()])
        saved_calls = []

        def save(**kwargs):
            saved_calls.append(kwargs)
            return saved_result(kwargs["checkpoint_envelope"])

        with patch.object(s16c.step14c, "load_step14c_restart_checkpoint", return_value=loaded_result()), patch.object(
            s16c.step14c.step14b, "save_step14b_checkpoint", side_effect=save
        ), patch.object(
            s16c.step14c.step14b, "validate_step14b_adapter_result", side_effect=lambda value: value
        ):
            result = s16c.run_step16c_bound_runner_canary(
                request(),
                owner_id="step16c-ci-owner",
                env=safe_env(),
                lease_ttl_seconds=61,
                lease_connection_factory=lease_factory,
                checkpoint_connection_factory=lambda: object(),
                token_factory=lambda: TOKEN,
                step13c_runner=lambda req, **kwargs: source_response(),
                generated_at_utc="2026-08-28T20:12:00+00:00",
            )
        validated = s16c.validate_step16c_bound_runner_result(result)
        self.assertTrue(validated["bound_runner_invoked"])
        self.assertEqual(validated["database_transport"], "injected_dbapi_ci")
        self.assertEqual(validated["step14c_runtime_result"]["saved_checkpoint_version"], 1)
        self.assertEqual(saved_calls[0]["expected_head_version"], 0)
        self.assertEqual(len(lease_factory.connections), 3)

    def test_18_bound_runner_result_tamper_fails_closed(self):
        lease_factory = SequenceFactory([acquire_script(), renew_script(), release_script()])
        with patch.object(s16c.step14c, "load_step14c_restart_checkpoint", return_value=loaded_result()), patch.object(
            s16c.step14c.step14b, "save_step14b_checkpoint", side_effect=lambda **kwargs: saved_result(kwargs["checkpoint_envelope"])
        ), patch.object(
            s16c.step14c.step14b, "validate_step14b_adapter_result", side_effect=lambda value: value
        ):
            result = s16c.run_step16c_bound_runner_canary(
                request(), owner_id="step16c-ci-owner", env=safe_env(), lease_ttl_seconds=61,
                lease_connection_factory=lease_factory, checkpoint_connection_factory=lambda: object(),
                token_factory=lambda: TOKEN, step13c_runner=lambda req, **kwargs: source_response(),
                generated_at_utc="2026-08-28T20:12:00+00:00",
            )
        result["database_transport"] = "live_psycopg"
        with self.assertRaises(s16c.WNBAStep16CCanaryIntegrityError):
            s16c.validate_step16c_bound_runner_result(result)

    def test_19_live_evidence_tamper_fails_closed(self):
        evidence = s16c.load_step16c_live_evidence()
        evidence["live_results"]["post_rollback_lease_rows"] = 1
        with self.assertRaises(s16c.WNBAStep16CCanaryIntegrityError):
            s16c.validate_step16c_live_evidence(evidence)

    def test_20_safety_constant_drift_fails_closed(self):
        with patch.object(s16c, "PRODUCTION_ACTIVATION_ALLOWED", True):
            with self.assertRaises(s16c.WNBAStep16CCanaryIntegrityError):
                s16c.build_step16c_canary_manifest(env=safe_env())


if __name__ == "__main__":
    unittest.main(verbosity=2)
