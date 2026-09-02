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
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


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


def source_response(cycle_index=7):
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
            "next_refresh_due_at_utc": "2026-08-28T17:41:00+00:00",
            "circuit_state": "closed",
        },
    }
    response["reliability_content_sha256"] = canonical({k: deepcopy(v) for k, v in response.items() if k not in {"generated_at_utc", "reliability_content_sha256"}})
    return response


def envelope(cycle_index=7, created="2026-08-28T17:42:00+00:00"):
    return step14a.build_step14a_checkpoint_envelope(step13c_response=source_response(cycle_index), slate_date="2026-08-28", env=safe_env(), created_at_utc=created)


def head_row(envlp, version=1):
    cid = s14b.checkpoint_id_for_envelope(envlp)
    return (
        version, cid, envlp["envelope_content_sha256"],
        version, cid, envlp["checkpoint_key"], envlp["slate_date"],
        envlp["step13d_frozen_sha"], envlp["step13_release_id"],
        envlp["step13_release_content_sha256"], envlp["source_step13c_frozen_sha"],
        envlp["source_reliability_content_sha256"], envlp["controller_state_sha256"],
        envlp["envelope_content_sha256"], deepcopy(envlp),
    )


class UniqueViolation(Exception):
    sqlstate = "23505"


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
        if step.get("contains") and step["contains"] not in sql:
            raise AssertionError(f"expected {step['contains']!r} in SQL")
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


def schema_step(present=True):
    return {"contains": "to_regclass", "fetchone": (present, present)}


class Tests(unittest.TestCase):
    def test_default_off_and_exact_frozen_parent(self):
        self.assertFalse(s14b.step14b_database_checkpoint_adapter_enabled({}))
        self.assertEqual(s14b.STEP14A_FROZEN_SHA, "aa1d770cd9840dac7e31139ab177fa4aa3ac9020")
        self.assertEqual(s14b.STEP14A_MANIFEST_CONTENT_SHA256, "2768d83f2bccb8cf1e47318c0910d4758fdeb68916683e67db92ffb282bea2e1")
        self.assertEqual(s14b.STEP14A_SQL_SCHEMA_SHA256, "308042f8196607a477158d348ba6e03e090267910cba749491534131b490a2eb")

    def test_step14b_gate_is_required(self):
        env = safe_env(); env["WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED"] = "false"
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
            s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=env, connection_factory=lambda: None)

    def test_read_gate_is_required_for_load(self):
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
            s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(read=False), connection_factory=lambda: None)

    def test_write_gate_is_required_for_save(self):
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
            s14b.save_step14b_checkpoint(checkpoint_envelope=envelope(), expected_head_version=0, env=safe_env(write=False), connection_factory=lambda: None)

    def test_required_frozen_parent_gates_are_enforced(self):
        keys = (
            "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED", "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED",
            "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED", "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
            "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED", "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
            "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED", "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
            "WNBA_STEP12A_SHADOW_RUNNER_ENABLED", "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
        )
        for key in keys:
            env = safe_env(); env[key] = "false"
            with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
                s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=env, connection_factory=lambda: None)

    def test_unsafe_global_switches_are_refused(self):
        for key in ("WNBA_PRODUCTION_RUNTIME_ENABLED", "WNBA_BOARD_SCHEDULER_ENABLED", "WNBA_PERSISTENCE_ENABLED", "WNBA_SUPABASE_WRITE_ENABLED", "WNBA_WAGERING_ENABLED", "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED", "WNBA_STEP12_SCHEDULER_ENABLED"):
            env = safe_env(); env[key] = "true"
            with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
                s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=env, connection_factory=lambda: None)

    def test_capability_boundary_allows_adapter_io_but_not_runtime_recovery(self):
        for value in (s14b.POSTGRESQL_DATABASE_READ_ALLOWED, s14b.POSTGRESQL_DATABASE_WRITE_ALLOWED, s14b.CHECKPOINT_LOAD_ALLOWED, s14b.CHECKPOINT_SAVE_ALLOWED, s14b.ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED, s14b.APPEND_ONLY_HISTORY_REQUIRED, s14b.SUPABASE_POSTGRES_COMPATIBLE):
            self.assertTrue(value)
        for value in (s14b.PERSISTENCE_RUNTIME_ENABLED, s14b.SUPABASE_REST_WRITE_ALLOWED, s14b.DURABLE_RESTART_RECOVERY_ALLOWED, s14b.DURABLE_DISTRIBUTED_LEASE_ALLOWED, s14b.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED, s14b.PRODUCTION_ACTIVATION_ALLOWED, s14b.PUBLIC_FASTAPI_ACTIVATION_ALLOWED, s14b.WAGERING_ALLOWED):
            self.assertFalse(value)

    def test_persistence_requirement_is_additive_and_uses_psycopg3(self):
        text = Path("sports_api/requirements-persistence.txt").read_text()
        self.assertIn("psycopg[binary]", text)
        self.assertNotIn("supabase", text.lower())

    def test_verify_schema_happy_path_is_read_only(self):
        factory, box = factory_for([schema_step()])
        result = s14b.verify_step14b_database_schema(env=safe_env(read=True, write=False), connection_factory=factory, generated_at_utc="2026-08-28T17:58:00+00:00")
        self.assertTrue(result["tables_present"])
        self.assertEqual(box["connection"].commits, 0)
        self.assertGreaterEqual(box["connection"].rollbacks, 1)
        self.assertTrue(box["connection"].closed)

    def test_verify_schema_missing_table_fails_closed(self):
        factory, _ = factory_for([schema_step(False)])
        with self.assertRaises(s14b.WNBAStep14DatabaseSchemaError):
            s14b.verify_step14b_database_schema(env=safe_env(read=True, write=False), connection_factory=factory)

    def test_load_not_found_returns_clean_result_without_write(self):
        factory, box = factory_for([schema_step(), {"contains": "WHERE h.checkpoint_key = %s", "fetchone": None}])
        result = s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(read=True, write=False), connection_factory=factory)
        self.assertEqual(result["status"], "not_found")
        self.assertFalse(result["found"])
        self.assertIsNone(result["checkpoint_version"])
        self.assertEqual(box["connection"].commits, 0)

    def test_load_valid_head_returns_exact_restart_state(self):
        envlp = envelope(); factory, _ = factory_for([schema_step(), {"contains": "JOIN kyre_runtime.wnba_runtime_checkpoints", "fetchone": head_row(envlp)}])
        result = s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(read=True, write=False), connection_factory=factory)
        self.assertEqual(result["status"], "loaded")
        self.assertEqual(result["checkpoint_envelope"], envlp)
        self.assertEqual(result["controller_state_for_restart"], envlp["controller_state"])
        s14b.validate_step14b_adapter_result(result)

    def test_load_tampered_envelope_fails_closed(self):
        envlp = envelope(); row = list(head_row(envlp)); bad = deepcopy(envlp); bad["controller_state"]["cycle_index"] = 999; row[14] = bad
        factory, _ = factory_for([schema_step(), {"contains": "JOIN", "fetchone": tuple(row)}])
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterIntegrityError):
            s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(read=True, write=False), connection_factory=factory)

    def test_load_release_metadata_mismatch_fails_closed(self):
        envlp = envelope(); row = list(head_row(envlp)); row[9] = "0" * 64
        factory, _ = factory_for([schema_step(), {"contains": "JOIN", "fetchone": tuple(row)}])
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterIntegrityError):
            s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(read=True, write=False), connection_factory=factory)

    def test_load_wrong_slate_row_fails_closed(self):
        envlp = envelope(); row = list(head_row(envlp)); row[6] = "2026-08-29"
        factory, _ = factory_for([schema_step(), {"contains": "JOIN", "fetchone": tuple(row)}])
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterIntegrityError):
            s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(read=True, write=False), connection_factory=factory)

    def test_deterministic_checkpoint_id_is_uuidv5_and_content_scoped(self):
        a, b = envelope(7), envelope(8)
        aid = s14b.checkpoint_id_for_envelope(a)
        self.assertEqual(aid, s14b.checkpoint_id_for_envelope(a))
        self.assertNotEqual(aid, s14b.checkpoint_id_for_envelope(b))
        self.assertEqual(UUID(aid).version, 5)

    def test_save_initial_checkpoint_creates_version_one_and_head(self):
        envlp = envelope(); factory, box = factory_for([schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": None}, {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "rowcount": 1}, {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoint_heads", "rowcount": 1}])
        result = s14b.save_step14b_checkpoint(checkpoint_envelope=envlp, expected_head_version=0, env=safe_env(), connection_factory=factory)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["checkpoint_version"], 1)
        self.assertEqual(box["connection"].commits, 1)
        s14b.validate_step14b_adapter_result(result)

    def test_save_existing_checkpoint_advances_version_with_cas(self):
        old, new = envelope(7), envelope(8, "2026-08-28T18:01:00+00:00")
        factory, box = factory_for([schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": head_row(old, 1)}, {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "rowcount": 1}, {"contains": "UPDATE kyre_runtime.wnba_runtime_checkpoint_heads", "rowcount": 1}])
        result = s14b.save_step14b_checkpoint(checkpoint_envelope=new, expected_head_version=1, env=safe_env(), connection_factory=factory)
        self.assertEqual(result["status"], "advanced")
        self.assertEqual(result["checkpoint_version"], 2)
        self.assertEqual(box["connection"].cursor_obj.calls[-1][1][-1], 1)

    def test_save_stale_expected_version_conflicts_before_insert(self):
        old, new = envelope(7), envelope(8); factory, box = factory_for([schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": head_row(old, 2)}])
        with self.assertRaises(s14b.WNBAStep14DatabaseConflictError):
            s14b.save_step14b_checkpoint(checkpoint_envelope=new, expected_head_version=1, env=safe_env(), connection_factory=factory)
        self.assertEqual(len(box["connection"].cursor_obj.calls), 2)
        self.assertGreaterEqual(box["connection"].rollbacks, 1)

    def test_save_identical_current_envelope_is_idempotent_without_append(self):
        envlp = envelope(); factory, box = factory_for([schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": head_row(envlp, 3)}])
        result = s14b.save_step14b_checkpoint(checkpoint_envelope=envlp, expected_head_version=0, env=safe_env(), connection_factory=factory)
        self.assertEqual(result["status"], "idempotent")
        self.assertEqual(result["checkpoint_version"], 3)
        self.assertEqual(len(box["connection"].cursor_obj.calls), 2)

    def test_save_head_update_rowcount_zero_is_conflict_and_rolls_back(self):
        old, new = envelope(7), envelope(8); factory, box = factory_for([schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": head_row(old, 1)}, {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "rowcount": 1}, {"contains": "UPDATE kyre_runtime.wnba_runtime_checkpoint_heads", "rowcount": 0}])
        with self.assertRaises(s14b.WNBAStep14DatabaseConflictError):
            s14b.save_step14b_checkpoint(checkpoint_envelope=new, expected_head_version=1, env=safe_env(), connection_factory=factory)
        self.assertGreaterEqual(box["connection"].rollbacks, 1)

    def test_unique_violation_maps_to_reloadable_conflict(self):
        envlp = envelope(); factory, _ = factory_for([schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": None}, {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "raise": UniqueViolation("race")}])
        with self.assertRaises(s14b.WNBAStep14DatabaseConflictError):
            s14b.save_step14b_checkpoint(checkpoint_envelope=envlp, expected_head_version=0, env=safe_env(), connection_factory=factory)

    def test_generic_database_failure_is_wrapped_and_secret_is_not_echoed(self):
        secret = "postgresql://user:super-secret@db.example/test"
        def broken(): raise RuntimeError(secret)
        with self.assertRaises(s14b.WNBAStep14DatabaseError) as ctx:
            s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(), connection_factory=broken)
        self.assertNotIn("super-secret", str(ctx.exception))

    def test_missing_database_url_fails_without_opening_live_connection(self):
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterDisabledError):
            s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(), connection_factory=None)

    def test_invalid_expected_version_is_rejected_before_database_io(self):
        for value in (-1, True, 1.5, "1"):
            with self.assertRaises(s14b.WNBAStep14DatabaseAdapterInputError):
                s14b.save_step14b_checkpoint(checkpoint_envelope=envelope(), expected_head_version=value, env=safe_env(), connection_factory=lambda: None)

    def test_adapter_result_hash_tamper_is_detected(self):
        envlp = envelope(); factory, _ = factory_for([schema_step(), {"contains": "JOIN", "fetchone": head_row(envlp)}])
        result = s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(read=True, write=False), connection_factory=factory)
        result["checkpoint_version"] = 999
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterIntegrityError):
            s14b.validate_step14b_adapter_result(result)

    def test_adapter_result_unknown_field_fails_closed(self):
        factory, _ = factory_for([schema_step(), {"contains": "WHERE h.checkpoint_key = %s", "fetchone": None}])
        result = s14b.load_step14b_checkpoint(slate_date="2026-08-28", env=safe_env(read=True, write=False), connection_factory=factory)
        result["surprise"] = True
        with self.assertRaises(s14b.WNBAStep14DatabaseAdapterInputError):
            s14b.validate_step14b_adapter_result(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
