from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unittest

from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as s14


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


def safe_env():
    return {
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


def source_response(state=None):
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": step13c.SCHEMA_VERSION,
        "generated_at_utc": "2026-08-28T17:40:00+00:00",
        "status": "completed",
        "health": "healthy",
        "lineage": {
            "step13b_frozen_sha": s14.STEP13B_FROZEN_SHA,
            "latest_step13b_supervisor_content_sha256": "a" * 64,
            "step13a_frozen_sha": s14.STEP13A_FROZEN_SHA,
            "step12d_frozen_sha": s14.step13_release.STEP12D_FROZEN_SHA,
        },
        "final_controller_state_for_restart_handoff": state
        if state is not None
        else {
            "season": 2026,
            "slate_date": "2026-08-28",
            "cycle_index": 7,
            "next_refresh_due_at_utc": "2026-08-28T17:41:00+00:00",
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


class Tests(unittest.TestCase):
    def test_default_off_and_exact_frozen_parent(self):
        self.assertFalse(s14.step14a_persistence_contract_enabled({}))
        self.assertEqual(
            s14.STEP13D_FROZEN_SHA,
            "41d1ce4a3a88020199a3de42514b3cd744b1e831",
        )
        self.assertEqual(
            s14.STEP13_RELEASE_CONTENT_SHA256,
            "7857651813d8114de58d21163fdb8f3eceb695a43834c3eb48b55bb5c01c9046",
        )

    def test_step14a_gate_is_required(self):
        env = safe_env()
        env.pop("WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED")
        with self.assertRaises(s14.WNBAStep14PersistenceContractDisabledError):
            s14.build_step14a_schema_manifest(env=env)

    def test_all_frozen_parent_gates_are_required(self):
        for key in (
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
            with self.assertRaises(s14.WNBAStep14PersistenceContractDisabledError):
                s14.build_step14a_schema_manifest(env=env)

    def test_unsafe_external_switches_are_refused(self):
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
            with self.assertRaises(s14.WNBAStep14PersistenceContractDisabledError):
                s14.build_step14a_schema_manifest(env=env)

    def test_schema_manifest_preserves_frozen_step13_release(self):
        manifest = s14.build_step14a_schema_manifest(env=safe_env())
        self.assertEqual(manifest["lineage"]["step13d_frozen_sha"], s14.STEP13D_FROZEN_SHA)
        self.assertEqual(
            manifest["lineage"]["step13_release_content_sha256"],
            s14.STEP13_RELEASE_CONTENT_SHA256,
        )
        self.assertEqual(
            manifest["lineage"]["step12_release_content_sha256"],
            "b557bcf8a8f585df1d91c6e5a178fd0d87ddfd5dd4a543d323b9d16d848d3c46",
        )

    def test_checkpoint_key_is_deterministic_and_slate_scoped(self):
        self.assertEqual(
            s14.checkpoint_key_for_slate("2026-08-28"),
            "wnba:runtime:2026:regular-season:2026-08-28",
        )
        self.assertNotEqual(
            s14.checkpoint_key_for_slate("2026-08-28"),
            s14.checkpoint_key_for_slate("2026-08-29"),
        )

    def test_non_2026_slate_is_rejected(self):
        with self.assertRaises(s14.WNBAStep14PersistenceContractInputError):
            s14.checkpoint_key_for_slate("2027-01-01")

    def test_happy_path_builds_json_safe_release_pinned_envelope(self):
        envelope = s14.build_step14a_checkpoint_envelope(
            step13c_response=source_response(),
            slate_date="2026-08-28",
            env=safe_env(),
            created_at_utc="2026-08-28T17:42:00+00:00",
        )
        self.assertEqual(envelope["checkpoint_key"], "wnba:runtime:2026:regular-season:2026-08-28")
        self.assertEqual(envelope["step13_release_id"], s14.STEP13_RELEASE_ID)
        self.assertEqual(envelope["step13_release_content_sha256"], s14.STEP13_RELEASE_CONTENT_SHA256)
        self.assertEqual(envelope["source_status"], "completed")
        self.assertEqual(envelope["source_health"], "healthy")
        self.assertEqual(len(envelope["controller_state_sha256"]), 64)
        self.assertEqual(len(envelope["envelope_content_sha256"]), 64)
        json.dumps(envelope, allow_nan=False)

    def test_envelope_hash_is_stable_across_creation_timestamp_only(self):
        a = s14.build_step14a_checkpoint_envelope(
            step13c_response=source_response(),
            slate_date="2026-08-28",
            env=safe_env(),
            created_at_utc="2026-08-28T17:42:00+00:00",
        )
        b = s14.build_step14a_checkpoint_envelope(
            step13c_response=source_response(),
            slate_date="2026-08-28",
            env=safe_env(),
            created_at_utc="2026-08-28T17:43:00+00:00",
        )
        self.assertNotEqual(a["created_at_utc"], b["created_at_utc"])
        self.assertEqual(a["envelope_content_sha256"], b["envelope_content_sha256"])

    def test_source_response_hash_tamper_is_rejected(self):
        source = source_response()
        source["health"] = "tampered"
        with self.assertRaises(s14.WNBAStep14PersistenceContractIntegrityError):
            s14.build_step14a_checkpoint_envelope(
                step13c_response=source,
                slate_date="2026-08-28",
                env=safe_env(),
            )

    def test_source_lineage_tamper_is_rejected(self):
        source = source_response()
        source["lineage"]["step13b_frozen_sha"] = "0" * 40
        surface = {
            key: deepcopy(value)
            for key, value in source.items()
            if key not in {"generated_at_utc", "reliability_content_sha256"}
        }
        source["reliability_content_sha256"] = canonical(surface)
        with self.assertRaises(s14.WNBAStep14PersistenceContractIntegrityError):
            s14.build_step14a_checkpoint_envelope(
                step13c_response=source,
                slate_date="2026-08-28",
                env=safe_env(),
            )

    def test_missing_controller_state_is_rejected(self):
        source = source_response()
        source["final_controller_state_for_restart_handoff"] = None
        surface = {
            key: deepcopy(value)
            for key, value in source.items()
            if key not in {"generated_at_utc", "reliability_content_sha256"}
        }
        source["reliability_content_sha256"] = canonical(surface)
        with self.assertRaises(s14.WNBAStep14PersistenceContractInputError):
            s14.build_step14a_checkpoint_envelope(
                step13c_response=source,
                slate_date="2026-08-28",
                env=safe_env(),
            )

    def test_non_json_controller_state_is_rejected(self):
        source = source_response(
            {"season": 2026, "slate_date": "2026-08-28", "bad": float("nan")}
        )
        with self.assertRaises(s14.WNBAStep14PersistenceContractInputError):
            s14.build_step14a_checkpoint_envelope(
                step13c_response=source,
                slate_date="2026-08-28",
                env=safe_env(),
            )

    def test_cross_slate_controller_state_is_rejected(self):
        source = source_response(
            {"season": 2026, "slate_date": "2026-08-27", "cycle_index": 2}
        )
        with self.assertRaises(s14.WNBAStep14PersistenceContractIntegrityError):
            s14.build_step14a_checkpoint_envelope(
                step13c_response=source,
                slate_date="2026-08-28",
                env=safe_env(),
            )

    def test_controller_state_hash_tamper_is_rejected_on_restore_validation(self):
        envelope = s14.build_step14a_checkpoint_envelope(
            step13c_response=source_response(),
            slate_date="2026-08-28",
            env=safe_env(),
        )
        envelope["controller_state"]["cycle_index"] = 999
        with self.assertRaises(s14.WNBAStep14PersistenceContractIntegrityError):
            s14.validate_step14a_checkpoint_envelope(envelope, env=safe_env())

    def test_envelope_hash_tamper_is_rejected(self):
        envelope = s14.build_step14a_checkpoint_envelope(
            step13c_response=source_response(),
            slate_date="2026-08-28",
            env=safe_env(),
        )
        envelope["source_health"] = "tampered"
        with self.assertRaises(s14.WNBAStep14PersistenceContractIntegrityError):
            s14.validate_step14a_checkpoint_envelope(envelope, env=safe_env())

    def test_restore_validation_refuses_wrong_requested_slate(self):
        envelope = s14.build_step14a_checkpoint_envelope(
            step13c_response=source_response(),
            slate_date="2026-08-28",
            env=safe_env(),
        )
        with self.assertRaises(s14.WNBAStep14PersistenceContractIntegrityError):
            s14.validate_step14a_checkpoint_envelope(
                envelope,
                env=safe_env(),
                expected_slate_date="2026-08-29",
            )

    def test_unknown_envelope_field_fails_closed(self):
        envelope = s14.build_step14a_checkpoint_envelope(
            step13c_response=source_response(),
            slate_date="2026-08-28",
            env=safe_env(),
        )
        envelope["surprise"] = True
        with self.assertRaises(s14.WNBAStep14PersistenceContractInputError):
            s14.validate_step14a_checkpoint_envelope(envelope, env=safe_env())

    def test_sql_contract_is_ddl_only_and_has_no_lease_table(self):
        text = Path(s14.SQL_SCHEMA_PATH).read_text(encoding="utf-8")
        self.assertIn("CREATE SCHEMA IF NOT EXISTS kyre_runtime", text)
        self.assertIn("wnba_runtime_checkpoints", text)
        self.assertIn("wnba_runtime_checkpoint_heads", text)
        self.assertNotIn("wnba_runtime_leases", text)
        self.assertIsNone(
            re.search(
                r"^\s*(insert|update|delete|truncate|merge|call|do)\b",
                text,
                flags=re.IGNORECASE | re.MULTILINE,
            )
        )

    def test_sql_contract_has_append_only_history_and_head_cas_constraints(self):
        text = Path(s14.SQL_SCHEMA_PATH).read_text(encoding="utf-8")
        required = (
            "UNIQUE (checkpoint_key, checkpoint_version)",
            "UNIQUE (checkpoint_key, envelope_content_sha256)",
            "checkpoint_version bigint NOT NULL CHECK (checkpoint_version >= 1)",
            "FOREIGN KEY (checkpoint_id)",
            "ON DELETE RESTRICT",
            "envelope_json jsonb NOT NULL",
            "controller_state_sha256 char(64) NOT NULL",
        )
        for fragment in required:
            self.assertIn(fragment, text)

    def test_capability_boundary_defines_schema_but_starts_no_persistence(self):
        manifest = s14.build_step14a_schema_manifest(env=safe_env())
        boundary = manifest["capability_boundary"]
        self.assertTrue(boundary["schema_definition_allowed"])
        self.assertTrue(boundary["checkpoint_envelope_allowed"])
        for key in (
            "database_read_allowed",
            "database_write_allowed",
            "persistence_runtime_enabled",
            "supabase_write_allowed",
            "durable_restart_recovery_allowed",
            "durable_distributed_lease_allowed",
            "cross_process_duplicate_run_guard_allowed",
            "production_activation_allowed",
        ):
            self.assertFalse(boundary[key])


if __name__ == "__main__":
    unittest.main(verbosity=2)
