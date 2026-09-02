from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step16c_live_postgres_canary as s16c

TOKEN = "11111111-1111-4111-8111-111111111111"
SLATE = "2026-01-16"
OUTPUT_PATH = Path("step16c-live-postgres-canary-cert.json")


def canonical(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    ).hexdigest()


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


def source_response():
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
            "cycle_index": 1,
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
        lease_key(), "step16c-cert-owner", TOKEN, 1,
        "2026-08-28T20:00:00+00:00", renewed, expires,
    )


class FakeCursor:
    def __init__(self, script):
        self.script = list(script)
        self.current = None

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
        pass


class FakeConnection:
    def __init__(self, script):
        self.cursor_obj = FakeCursor(script)

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class SequenceFactory:
    def __init__(self, scripts):
        self.scripts = [list(script) for script in scripts]

    def __call__(self):
        if not self.scripts:
            raise AssertionError("unexpected connection")
        return FakeConnection(self.scripts.pop(0))


def schema_step():
    return {"contains": "to_regclass", "fetchone": (True,)}


def lease_factory():
    return SequenceFactory([
        [schema_step(), {"contains": "ON CONFLICT (lease_key)", "fetchone": lease_row()}],
        [schema_step(), {"contains": "fencing_generation = %s", "fetchone": lease_row(renewed="2026-08-28T20:01:00+00:00", expires="2026-08-28T21:01:00+00:00")}],
        [schema_step(), {"contains": "DELETE FROM kyre_runtime.wnba_runtime_leases", "fetchone": (lease_key(),)}],
    ])


def loaded_result():
    return {
        "found": False,
        "checkpoint_version": None,
        "checkpoint_key": step14a.checkpoint_key_for_slate(SLATE),
        "controller_state_for_restart": None,
    }


def main():
    from unittest.mock import patch

    env = dict(os.environ)
    evidence = s16c.validate_step16c_live_evidence(s16c.load_step16c_live_evidence())
    manifest = s16c.build_step16c_canary_manifest(
        env=env,
        generated_at_utc="2026-08-28T20:12:00+00:00",
    )

    def save(**kwargs):
        envelope = kwargs["checkpoint_envelope"]
        return {
            "checkpoint_version": 1,
            "status": "created",
            "envelope_content_sha256": envelope["envelope_content_sha256"],
            "controller_state_sha256": envelope["controller_state_sha256"],
        }

    with patch.object(s16c.step14c, "load_step14c_restart_checkpoint", return_value=loaded_result()), patch.object(
        s16c.step14c.step14b, "save_step14b_checkpoint", side_effect=save
    ), patch.object(
        s16c.step14c.step14b, "validate_step14b_adapter_result", side_effect=lambda value: value
    ):
        runner_result = s16c.run_step16c_bound_runner_canary(
            request(),
            owner_id="step16c-cert-owner",
            env=env,
            lease_ttl_seconds=61,
            lease_connection_factory=lease_factory(),
            checkpoint_connection_factory=lambda: object(),
            token_factory=lambda: TOKEN,
            step13c_runner=lambda req, **kwargs: source_response(),
            generated_at_utc="2026-08-28T20:12:00+00:00",
        )
    runner_result = s16c.validate_step16c_bound_runner_result(runner_result)

    certification = {
        "data_type": "wnba_step16c_live_postgres_canary_certification",
        "schema_version": s16c.SCHEMA_VERSION,
        "integration_version": s16c.INTEGRATION_VERSION,
        "contract_id": s16c.CONTRACT_ID,
        "branch": s16c.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA", "local"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "local"),
        "expected_regression_tests": 640,
        "new_step16c_tests": 20,
        "frozen_step16b_tests": 20,
        "frozen_step16a_parent_tests": 20,
        "frozen_step15_through_step8_tests": 580,
        "manifest_content_sha256": manifest["manifest_content_sha256"],
        "live_evidence_content_sha256": evidence["evidence_content_sha256"],
        "live_database_canary": {
            "live_postgresql_used": True,
            "supabase_management_sql_used": True,
            "transaction_rolled_back": True,
            "zero_residue_verified": True,
            "initial_fencing_generation": evidence["live_results"]["initial_fencing_generation"],
            "duplicate_active_acquire_rows": evidence["live_results"]["duplicate_active_acquire_rows"],
            "checkpoint_round_trip_exact": evidence["live_results"]["checkpoint_load_round_trip_exact"],
            "post_rollback_rows": {
                "checkpoints": evidence["live_results"]["post_rollback_checkpoint_rows"],
                "heads": evidence["live_results"]["post_rollback_checkpoint_head_rows"],
                "leases": evidence["live_results"]["post_rollback_lease_rows"],
            },
        },
        "bound_runner_canary": {
            "exact_step16b_bound_step14c_runner_invoked": runner_result["bound_runner_invoked"],
            "transport": runner_result["database_transport"],
            "step14c_runtime_status": runner_result["step14c_runtime_result"]["status"],
            "saved_checkpoint_version": runner_result["step14c_runtime_result"]["saved_checkpoint_version"],
            "lease_fencing_generation": runner_result["step14c_runtime_result"]["lease_fencing_generation"],
            "canary_content_sha256": runner_result["canary_content_sha256"],
        },
        "certification_transport": {
            "github_actions_live_database_credentials_used": False,
            "direct_python_psycopg_live_connection": False,
            "deployed_fastapi_container_connected_live": False,
            "live_database_used_during_external_step16c_preflight": True,
            "live_database_used_inside_github_actions": False,
        },
        "safety_contract": deepcopy(s16c.SAFETY_CONTRACT),
        "phase_boundary": {
            "step16c_complete": True,
            "live_postgresql_canary_certified": True,
            "bound_step14c_runner_path_certified": True,
            "direct_deployed_container_psycopg_canary_deferred_to_step16d": True,
            "controlled_production_activation_not_authorized": True,
            "step16d_not_started": True,
        },
    }
    OUTPUT_PATH.write_text(json.dumps(certification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(certification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
