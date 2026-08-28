from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step13_release_freeze as step13d

ARTIFACT_PATH = Path("step13d-final-scheduler-freeze-cert.json")
MARKER = "STEP13D_FINAL_SCHEDULER_FREEZE_OK"
EXPECTED_REGRESSION_TESTS = 417


def _safe_env() -> dict[str, str]:
    env = {
        step13d.STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED_ENV: "true",
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
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }
    return env


def main() -> int:
    env = _safe_env()
    first = step13d.build_step13d_release_manifest(
        env=env,
        generated_at_utc="2026-08-28T17:30:00+00:00",
    )
    second = step13d.build_step13d_release_manifest(
        env=env,
        generated_at_utc="2026-08-28T17:31:00+00:00",
    )
    if first["release_content_sha256"] != second["release_content_sha256"]:
        raise RuntimeError("Step 13D release hash changed across timestamp-only regeneration.")

    evidence = {
        "data_type": "wnba_step13d_final_scheduler_freeze_certification",
        "schema_version": step13d.SCHEMA_VERSION,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": step13d.BRANCH,
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "release_id": first["release_id"],
        "release_content_sha256": first["release_content_sha256"],
        "step12_release_id": step13d.STEP12_RELEASE_ID,
        "step12_release_content_sha256": step13d.STEP12_RELEASE_CONTENT_SHA256,
        "expected_regression_tests": EXPECTED_REGRESSION_TESTS,
        "lineage": deepcopy(first["lineage"]),
        "scheduler_contract": deepcopy(first["scheduler_contract"]),
        "analytical_contract": deepcopy(first["analytical_contract"]),
        "safety_contract": deepcopy(first["safety_contract"]),
        "phase_boundary": deepcopy(first["phase_boundary"]),
        "certification_summary": {
            "step13a_bounded_scheduler_frozen": True,
            "step13b_runtime_supervisor_frozen": True,
            "step13c_reliability_recovery_frozen": True,
            "step13_complete": True,
            "step14_persistence_not_started": True,
            "production_not_started": True,
            "release_hash_timestamp_stable": True,
        },
    }
    ARTIFACT_PATH.write_text(
        json.dumps(evidence, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(MARKER)
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
