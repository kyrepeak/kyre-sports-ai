from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from uuid import UUID

from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14b_database_checkpoint_adapter as s14b


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def safe_env(*, read=True, write=True):
    return {
        "WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED": "true",
        "WNBA_STEP14B_DATABASE_READ_ENABLED": "true" if read else "false",
        "WNBA_STEP14B_DATABASE_WRITE_ENABLED": "true" if write else "false",
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


def source_response(*, cycle_index=7, next_due="2026-08-28T17:41:00+00:00"):
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": step13c.SCHEMA_VERSION,
        "generated_at_utc": "2026-08-28T17:40:00+00:00",
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
            "next_refresh_due_at_utc": next_due,
            "circuit_state": "closed",
        },
    }
    surface = {
        key: deepcopy(value)
        for key, value in response.items()
        if key not in {"generated_at_utc", "reliability_content_sha256"}
    }
    response["reliability_content_sha256"] = canonical(surface)
    return response


def envelope(*, cycle_index=7, created="2026-08-28T17:42:00+00:00"):
    return step14a.build_step14a_checkpoint_envelope(
        step13c_response=source_response(cycle_index=cycle_index),
        slate_date="2026-08-28",
        env=safe_env(),
        created_at_utc=created,
    )


def persisted_head_row(envlp, *, version=1, checkpoint_id=None):
    cid = checkpoint_id or s14b.checkpoint_id_for_envelope(envlp)
    return (
        version,
        cid,
        envlp["envelope_content_sha256"],
        version,
        cid,
        envlp["checkpoint_key"],
        envlp["slate_date"],
        envlp["step13d_frozen_sha"],
        envlp["step13_release_id"],
        envlp["step13_release_content_sha256"],
        envlp["source_step13c_frozen_sha"],
        envlp["source_reliability_content_sha256"],
        envlp["controller_state_sha256"],
        envlp["envelope_content_sha256"],
        deepcopy(envlp),
    )


class UniqueViolation(Exception):
    sqlstate = "23505"


class FakeCursor:
    def __init__(self, script):
        self.script = list(script)
        self.current = None
        self.rowcount = -1
        self.closed = False
        self.calls = []

    def execute(self, sql, params=None):
        if not self.script:
            raise AssertionError(f"Unexpected SQL execution: {sql}")
        step = self.script.pop(0)
        expected = step.get("contains")
        if expected is not None and expected not in sql:
            raise AssertionError(f"Expected SQL containing {expected!r}, got {sql!r}")
        self.calls.append((sql, params))
        if "raise" in step:
            raise step["raise"]
        self.current = step
        self.rowcount = step.get("rowcount", -1)

    def fetchone(self):
        if self.current is None:
            raise AssertionError("fetchone before execute")
        return self.current.get("fetchone")

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


def factory_for(script):
    holder = {}

    def factory():
        conn = FakeConnection(script)
        holder["connection"] = conn
        return conn

    return factory, holder


def schema_step(*, present=True):
    return {
        "contains": "to_regclass",
        "fetchone": (present, present),
    }


class Tests(unittest.TestCase):
    def test_default_off_and_exact_frozen_parent(self):
        self.assertFalse(s14b.step14b_database_checkpoint_adapter_enabled({}))
        self.assertEqual(
            s14b.STEP14A_FROZEN_SHA,
            "aa1d770cd9840dac7e31139ab177fa4aa3ac9020",
        )
        self.assertEqual(
            s14b.STEP14A_MANIFEST_CONTENT_SHA256,
            "2768d83f2bccb8cf1e47318c0910d4758fdeb68916683e67db92ffb282bea2e1",
        )
        self.assertEqual(
            s14b.STEP14A_SQL_SCHEMA_SHA256,
            "308042f8196607a477158d348ba6e03e090267910cba749491534131b490a2eb",
        )

    def test_step14b_gate_is_required(self):
        env = safe_env()
        env["WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED"] = "false"
        factory, _ = factory_for([])
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
            s14b.load_step14b_checkpoint(
                slate_date="2026-08-28", env=env, connection_factory=factory
            )

    def test_read_gate_is_required_for_load(self):
        factory, _ = factory_for([])
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
            s14b.load_step14b_checkpoint(
                slate_date="2026-08-28",
                env=safe_env(read=False),
                connection_factory=factory,
            )

    def test_write_gate_is_required_for_save(self):
        factory, _ = factory_for([])
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
            s14b.save_step14b_checkpoint(
                checkpoint_envelope=envelope(),
                expected_head_version=0,
                env=safe_env(write=False),
                connection_factory=factory,
            )

    def test_required_frozen_parent_gates_are_enforced(self):
        for key in (
            "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED",
            "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED",
            "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED",
            "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
            "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
            "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
            "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
            "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
            "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
            "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
        ):
            env = safe_env()
            env[key] = "false"
            factory, _ = factory_for([])
            with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
                s14b.load_step14b_checkpoint(
                    slate_date="2026-08-28", env=env, connection_factory=factory
                )

    def test_unsafe_global_switches_are_refused(self):
        for key in (
            "WNBA_PRODUCTION_RUNTIME_ENABLED",
            "WNBA_BOARD_SCHEDULER_ENABLED",
            "WNBA_PERSISTENCE_ENABLED",
            "WNBA_SUPABASE_WRITE_ENABLED",
            "WNBA_WAGERING_ENABLED",
            "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
            "WNBA_STEP12_SCHEDULER_ENABLED",
        ):
            env = safe_env()
            env[key] = "true"
            factory, _ = factory_for([])
            with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
                s14b.load_step14b_checkpoint(
                    slate_date="2026-08-28", env=env, connection_factory=factory
                )

    def test_capability_boundary_allows_adapter_io_but_not_runtime_recovery(self):
        self.assertTrue(s14b.POSTGRESQL_DATABASE_READ_ALLOWED)
        self.assertTrue(s14b.POSTGRESQL_DATABASE_WRITE_ALLOWED)
        self.assertTrue(s14b.CHECKPOINT_LOAD_ALLOWED)
        self.assertTrue(s14b.CHECKPOINT_SAVE_ALLOWED)
        self.assertTrue(s14b.ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED)
        self.assertTrue(s14b.APPEND_ONLY_HISTORY_REQUIRED)
        self.assertTrue(s14b.SUPABASE_POSTGRES_COMPATIBLE)
        for value in (
            s14b.PERSISTENCE_RUNTIME_ENABLED,
            s14b.SUPABASE_REST_WRITE_ALLOWED,
            s14b.DURABLE_RESTART_RECOVERY_ALLOWED,
            s14b.DURABLE_DISTRIBUTED_LEASE_ALLOWED,
            s14b.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
            s14b.PRODUCTION_ACTIVATION_ALLOWED,
            s14b.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
            s14b.WAGERING_ALLOWED,
        ):
            self.assertFalse(value)

    def test_persistence_requirement_is_additive_and_uses_psycopg3(self):
        text = Path("sports_api/requirements-persistence.txt").read_text(encoding="utf-8")
        self.assertIn("psycopg[binary]", text)
        self.assertNotIn("supabase", text.lower())

    def test_verify_schema_happy_path_is_read_only(self):
        factory, holder = factory_for([schema_step()])
        result = s14b.verify_step14b_database_schema(
            env=safe_env(read=True, write=False),
            connection_factory=factory,
            generated_at_utc="2026-08-28T17:58:00+00:00",
        )
        self.assertTrue(result["tables_present"])
        conn = holder["connection"]
        self.assertEqual(conn.commits, 0)
        self.assertGreaterEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)
        self.assertTrue(conn.cursor_obj.closed)

    def test_verify_schema_missing_table_fails_closed(self):
        factory, holder = factory_for([schema_step(present=False)])
        with self.assertRaises(s14b.WNBAStep14DatabaseSchemaError):
            s14b.verify_step14b_database_schema(
                env=safe_env(read=True, write=False), connection_factory=factory
            )
        self.assertTrue(holder["connection"].closed)

    def test_load_not_found_returns_clean_result_without_write(self):
        factory, holder = factory_for(
            [
                schema_step(),
                {"contains": "WHERE h.checkpoint_key = %s", "fetchone": None},
            ]
        )
        result = s14b.load_step14b_checkpoint(
            slate_date="2026-08-28",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
            generated_at_utc="2026-08-28T17:59:00+00:00",
        )
        self.assertEqual(result["status"], "not_found")
        self.assertFalse(result["found"])
        self.assertIsNone(result["checkpoint_version"])
        self.assertIsNone(result["checkpoint_envelope"])
        self.assertEqual(holder["connection"].commits, 0)
        self.assertGreaterEqual(holder["connection"].rollbacks, 1)

    def test_load_valid_head_returns_exact_restart_state(self):
        envlp = envelope()
        factory, _ = factory_for(
            [schema_step(), {"contains": "JOIN kyre_runtime.wnba_runtime_checkpoints", "fetchone": persisted_head_row(envlp)}]
        )
        result = s14b.load_step14b_checkpoint(
            slate_date="2026-08-28",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
            generated_at_utc="2026-08-28T17:59:00+00:00",
        )
        self.assertEqual(result["status"], "loaded")
        self.assertTrue(result["found"])
        self.assertEqual(result["checkpoint_version"], 1)
        self.assertEqual(result["checkpoint_envelope"], envlp)
        self.assertEqual(result["controller_state_for_restart"], envlp["controller_state"])
        s14b.validate_step14b_adapter_result(result)

    def test_load_tampered_envelope_fails_closed(self):
        envlp = envelope()
        row = list(persisted_head_row(envlp))
        bad = deepcopy(envlp)
        bad["controller_state"]["cycle_index"] = 999
        row[14] = bad
        factory, _ = factory_for([schema_step(), {"contains": "JOIN", "fetchone": tuple(row)}])
        with self.assertRaises(step14a.WNBAStep14PersistenceContractIntegrityError):
            s14b.load_step14b_checkpoint(
                slate_date="2026-08-28",
                env=safe_env(read=True, write=False),
                connection_factory=factory,
            )

    def test_load_release_metadata_mismatch_fails_closed(self):
        envlp = envelope()
        row = list(persisted_head_row(envlp))
        row[9] = "0" * 64
        factory, _ = factory_for([schema_step(), {"contains": "JOIN", "fetchone": tuple(row)}])
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterIntegrityError):
            s14b.load_step14b_checkpoint(
                slate_date="2026-08-28",
                env=safe_env(read=True, write=False),
                connection_factory=factory,
            )

    def test_load_wrong_slate_row_fails_closed(self):
        envlp = envelope()
        row = list(persisted_head_row(envlp))
        row[6] = "2026-08-29"
        factory, _ = factory_for([schema_step(), {"contains": "JOIN", "fetchone": tuple(row)}])
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterIntegrityError):
            s14b.load_step14b_checkpoint(
                slate_date="2026-08-28",
                env=safe_env(read=True, write=False),
                connection_factory=factory,
            )

    def test_deterministic_checkpoint_id_is_uuidv5_and_content_scoped(self):
        a = envelope(cycle_index=7)
        b = envelope(cycle_index=8)
        aid = s14b.checkpoint_id_for_envelope(a)
        self.assertEqual(aid, s14b.checkpoint_id_for_envelope(a))
        self.assertNotEqual(aid, s14b.checkpoint_id_for_envelope(b))
        self.assertEqual(UUID(aid).version, 5)

    def test_save_initial_checkpoint_creates_version_one_and_head(self):
        envlp = envelope()
        factory, holder = factory_for(
            [
                schema_step(),
                {"contains": "FOR UPDATE OF h", "fetchone": None},
                {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "rowcount": 1},
                {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoint_heads", "rowcount": 1},
            ]
        )
        result = s14b.save_step14b_checkpoint(
            checkpoint_envelope=envlp,
            expected_head_version=0,
            env=safe_env(),
            connection_factory=factory,
            generated_at_utc="2026-08-28T18:00:00+00:00",
        )
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["checkpoint_version"], 1)
        self.assertEqual(result["checkpoint_id"], s14b.checkpoint_id_for_envelope(envlp))
        self.assertEqual(holder["connection"].commits, 1)
        self.assertEqual(holder["connection"].rollbacks, 0)
        self.assertEqual(len(holder["connection"].cursor_obj.calls), 4)
        s14b.validate_step14b_adapter_result(result)

    def test_save_existing_checkpoint_advances_version_with_cas(self):
        old = envelope(cycle_index=7)
        new = envelope(cycle_index=8, created="2026-08-28T18:01:00+00:00")
        factory, holder = factory_for(
            [
                schema_step(),
                {"contains": "FOR UPDATE OF h", "fetchone": persisted_head_row(old, version=1)},
                {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "rowcount": 1},
                {"contains": "UPDATE kyre_runtime.wnba_runtime_checkpoint_heads", "rowcount": 1},
            ]
        )
        result = s14b.save_step14b_checkpoint(
            checkpoint_envelope=new,
            expected_head_version=1,
            env=safe_env(),
            connection_factory=factory,
            generated_at_utc="2026-08-28T18:02:00+00:00",
        )
        self.assertEqual(result["status"], "advanced")
        self.assertEqual(result["checkpoint_version"], 2)
        self.assertEqual(holder["connection"].commits, 1)
        update_params = holder["connection"].cursor_obj.calls[-1][1]
        self.assertEqual(update_params[-1], 1)
        self.assertEqual(update_params[0], 2)

    def test_save_stale_expected_version_conflicts_before_insert(self):
        old = envelope(cycle_index=7)
        new = envelope(cycle_index=8)
        factory, holder = factory_for(
            [schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": persisted_head_row(old, version=2)}]
        )
        with self.assertRaises(s14b.WNBAStep14DatabaseConflictError):
            s14b.save_step14b_checkpoint(
                checkpoint_envelope=new,
                expected_head_version=1,
                env=safe_env(),
                connection_factory=factory,
            )
        self.assertEqual(len(holder["connection"].cursor_obj.calls), 2)
        self.assertGreaterEqual(holder["connection"].rollbacks, 1)
        self.assertEqual(holder["connection"].commits, 0)

    def test_save_identical_current_envelope_is_idempotent_without_append(self):
        envlp = envelope()
        factory, holder = factory_for(
            [schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": persisted_head_row(envlp, version=3)}]
        )
        result = s14b.save_step14b_checkpoint(
            checkpoint_envelope=envlp,
            expected_head_version=0,
            env=safe_env(),
            connection_factory=factory,
        )
        self.assertEqual(result["status"], "idempotent")
        self.assertEqual(result["checkpoint_version"], 3)
        self.assertEqual(len(holder["connection"].cursor_obj.calls), 2)
        self.assertEqual(holder["connection"].commits, 1)

    def test_save_head_update_rowcount_zero_is_conflict_and_rolls_back(self):
        old = envelope(cycle_index=7)
        new = envelope(cycle_index=8)
        factory, holder = factory_for(
            [
                schema_step(),
                {"contains": "FOR UPDATE OF h", "fetchone": persisted_head_row(old, version=1)},
                {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "rowcount": 1},
                {"contains": "UPDATE kyre_runtime.wnba_runtime_checkpoint_heads", "rowcount": 0},
            ]
        )
        with self.assertRaises(s14b.WNBAStep14DatabaseConflictError):
            s14b.save_step14b_checkpoint(
                checkpoint_envelope=new,
                expected_head_version=1,
                env=safe_env(),
                connection_factory=factory,
            )
        self.assertGreaterEqual(holder["connection"].rollbacks, 1)
        self.assertEqual(holder["connection"].commits, 0)

    def test_unique_violation_maps_to_reloadable_conflict(self):
        envlp = envelope()
        factory, holder = factory_for(
            [
                schema_step(),
                {"contains": "FOR UPDATE OF h", "fetchone": None},
                {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "raise": UniqueViolation("race")},
            ]
        )
        with self.assertRaises(s14b.WNBAStep14DatabaseConflictError):
            s14b.save_step14b_checkpoint(
                checkpoint_envelope=envlp,
                expected_head_version=0,
                env=safe_env(),
                connection_factory=factory,
            )
        self.assertGreaterEqual(holder["connection"].rollbacks, 1)

    def test_generic_database_failure_is_wrapped_and_secret_is_not_echoed(self):
        secret = "postgresql://user:super-secret@db.example/test"
        env = safe_env()
        env[s14b.DATABASE_URL_ENV] = secret

        def broken_factory():
            raise RuntimeError(secret)

        with self.assertRaises(s14b.WNBAStep14DatabaseError) as ctx:
            s14b.load_step14b_checkpoint(
                slate_date="2026-08-28", env=env, connection_factory=broken_factory
            )
        self.assertNotIn("super-secret", str(ctx.exception))

    def test_missing_database_url_fails_without_opening_live_connection(self):
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError) as ctx:
            s14b.load_step14b_checkpoint(
                slate_date="2026-08-28", env=safe_env(), connection_factory=None
            )
        self.assertIn(s14b.DATABASE_URL_ENV, str(ctx.exception))

    def test_invalid_expected_version_is_rejected_before_database_io(self):
        factory, holder = factory_for([])
        for value in (-1, True, 1.5, "1"):
            with self.assertRaises(s14b.WNBAStep14DatabaseAdapterInputError):
                s14b.save_step14b_checkpoint(
                    checkpoint_envelope=envelope(),
                    expected_head_version=value,
                    env=safe_env(),
                    connection_factory=factory,
                )
        self.assertNotIn("connection", holder)

    def test_adapter_result_hash_tamper_is_detected(self):
        envlp = envelope()
        factory, _ = factory_for(
            [schema_step(), {"contains": "JOIN", "fetchone": persisted_head_row(envlp)}]
        )
        result = s14b.load_step14b_checkpoint(
            slate_date="2026-08-28",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )
        result["checkpoint_version"] = 999
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterIntegrityError):
            s14b.validate_step14b_adapter_result(result)

    def test_adapter_result_unknown_field_fails_closed(self):
        factory, _ = factory_for(
            [schema_step(), {"contains": "WHERE h.checkpoint_key = %s", "fetchone": None}]
        )
        result = s14b.load_step14b_checkpoint(
            slate_date="2026-08-28",
            env=safe_env(read=True, write=False),
            connection_factory=factory,
        )
        result["surprise"] = True
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterInputError):
            s14b.validate_step14b_adapter_result(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
