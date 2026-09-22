from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step12_release_freeze as freeze

ARTIFACT_PATH = Path("step12d-final-runtime-freeze-cert.json")
MARKER = "STEP12D_FINAL_RUNTIME_FREEZE_OK"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env[freeze.STEP12D_FINAL_RUNTIME_FREEZE_ENABLED_ENV] = "true"
    env["WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED"] = "true"
    env["WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED"] = "true"
    env["WNBA_STEP12A_SHADOW_RUNNER_ENABLED"] = "true"
    env["WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED"] = "true"
    for key in (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
        "WNBA_STEP6J_CANARY_ENABLED",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
        "WNBA_PERSISTENCE_ENABLED",
        "WNBA_SUPABASE_WRITE_ENABLED",
        "WNBA_WAGERING_ENABLED",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
        "WNBA_STEP12_SCHEDULER_ENABLED",
    ):
        env[key] = "false"
    return env


def main() -> None:
    certified_at = datetime.now(timezone.utc).isoformat()
    manifest = freeze.build_step12d_release_manifest(
        env=_env(), generated_at_utc=certified_at
    )
    lineage = manifest["lineage"]
    contract = manifest["runtime_contract"]
    safety = manifest["safety_contract"]
    phase = manifest["phase_boundary"]

    assert manifest["release_id"] == freeze.RELEASE_ID
    assert lineage["step12c_frozen_sha"] == freeze.STEP12C_FROZEN_SHA
    assert lineage["step12b_frozen_sha"] == freeze.STEP12B_FROZEN_SHA
    assert lineage["step12a_frozen_sha"] == freeze.STEP12A_FROZEN_SHA
    assert lineage["step11e_frozen_sha"] == freeze.STEP11E_FROZEN_SHA
    assert lineage["step8_frozen_sha"] == freeze.STEP8_FROZEN_SHA
    assert contract["certified_simulations_per_projection"] == 5_000_000
    assert contract["sportsbooks"] == ["DraftKings", "FanDuel"]
    assert contract["sportsbook_http_methods"] == ["GET"]
    assert contract["frozen_step9_ranking_preserved"] is True
    assert contract["frozen_step9_qualification_preserved"] is True
    assert contract["step12c_presentation_only"] is True
    assert all(value is False for value in safety.values())
    assert phase == {
        "step12_complete": True,
        "step13_scheduler_not_started": True,
        "step14_persistence_not_started": True,
        "production_not_started": True,
    }

    result = {
        "data_type": "wnba_step12d_final_runtime_freeze_certification",
        "schema_version": freeze.SCHEMA_VERSION,
        "certified": True,
        "certified_at_utc": certified_at,
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "branch": freeze.BRANCH,
        "release_id": freeze.RELEASE_ID,
        "release_content_sha256": manifest["release_content_sha256"],
        "lineage": lineage,
        "runtime_contract": contract,
        "safety_contract": safety,
        "phase_boundary": phase,
        "certification_summary": {
            "step12a_shadow_runner_frozen": True,
            "step12b_live_runtime_assembly_frozen": True,
            "step12c_live_board_runtime_frozen": True,
            "step12_complete": True,
            "scheduler_deferred_to_step13": True,
            "persistence_deferred_to_step14": True,
            "production_activation_deferred": True,
        },
    }
    ARTIFACT_PATH.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(MARKER)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
