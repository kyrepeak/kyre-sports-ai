"""OFF-only live certification for WNBA Step 8A projection handoff.

The certificate first rechecks the frozen Step-7G real FastAPI default route,
then constructs the Step-8A handoff with the included Step-4W snapshot. It does
not run a projection model, Monte Carlo, sportsbook access, persistence, or any
production runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sports_api import wnba_step7g_release_freeze as step7g_freeze
from sports_api.wnba_step8_projection_handoff import (
    HANDOFF_RELEASE_ID,
    SCHEMA_VERSION,
    STEP7G_FROZEN_HEAD_SHA,
    get_player_game_step8_projection_handoff,
    recompute_step4w_snapshot_content_sha256,
)

REPORT_PATH = Path("step8a-projection-handoff-cert.json")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError(
            "Step 8A cert refuses to run with production switches enabled: "
            + ", ".join(bad)
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 8A cert requires Step-7G first-party mode ON only in CI.")
    if not _truthy(os.getenv("WNBA_STEP8_PROJECTION_HANDOFF_ENABLED")):
        raise RuntimeError("Step 8A cert requires Step-8A handoff ON only in CI.")


def _check_by_id(body: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    checks = body.get("checks")
    if not isinstance(checks, list):
        return None
    matches = [row for row in checks if isinstance(row, dict) and row.get("check_id") == check_id]
    if len(matches) != 1:
        return None
    return matches[0]


def _assert_frozen_fastapi(body: dict[str, Any]) -> dict[str, Any]:
    summary = body.get("summary")
    if not isinstance(summary, dict):
        raise RuntimeError("Step 8A frozen FastAPI response is missing readiness summary.")
    if body.get("readiness") not in {"READY", "READY_WITH_WARNINGS"}:
        raise RuntimeError(f"Step 8A frozen FastAPI readiness is not startable: {body.get('readiness')!r}.")
    if body.get("can_start_projection") is not True:
        raise RuntimeError("Step 8A frozen FastAPI route no longer authorizes projection start.")
    if summary.get("blocker_count") != 0 or list(summary.get("blocker_ids") or []):
        raise RuntimeError(f"Step 8A frozen FastAPI route has blockers: {summary!r}.")
    warning_ids = list(summary.get("warning_ids") or [])
    if not set(warning_ids).issubset(step7g_freeze.ALLOWED_NON_BLOCKING_WARNING_IDS):
        raise RuntimeError(f"Step 8A frozen FastAPI route has unexpected warnings: {warning_ids!r}.")

    required: dict[str, Any] = {}
    for check_id in step7g_freeze.REQUIRED_RELEASE_DEFAULT_CHECKS:
        row = _check_by_id(body, check_id)
        if not isinstance(row, dict):
            raise RuntimeError(f"Step 8A frozen FastAPI route is missing unique check {check_id!r}.")
        if row.get("severity") != "pass" or row.get("blocking") is not False:
            raise RuntimeError(f"Step 8A frozen FastAPI check {check_id!r} regressed: {row!r}.")
        required[check_id] = {
            "severity": row.get("severity"),
            "blocking": row.get("blocking"),
            "observed": row.get("observed"),
        }
    return {
        "readiness": body.get("readiness"),
        "can_start_projection": True,
        "summary": {
            "check_count": summary.get("check_count"),
            "pass_count": summary.get("pass_count"),
            "warning_count": summary.get("warning_count"),
            "blocker_count": 0,
            "warning_ids": warning_ids,
            "blocker_ids": [],
        },
        "required_checks": required,
    }


def _assert_handoff(handoff: dict[str, Any], *, game_id: str, player_id: int) -> dict[str, Any]:
    if handoff.get("data_type") != "certified_pre_projection_model_handoff":
        raise RuntimeError("Step 8A handoff returned wrong data type.")
    if handoff.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError("Step 8A handoff returned wrong schema version.")
    if handoff.get("handoff_release_id") != HANDOFF_RELEASE_ID:
        raise RuntimeError("Step 8A handoff returned wrong release ID.")
    if handoff.get("projection_execution_authorized") is not True:
        raise RuntimeError("Step 8A handoff did not authorize isolated projection execution.")
    if handoff.get("production_activation_allowed") is not False:
        raise RuntimeError("Step 8A handoff improperly allows production activation.")

    upstream = handoff.get("upstream_release")
    if not isinstance(upstream, dict):
        raise RuntimeError("Step 8A handoff is missing upstream release provenance.")
    if upstream.get("release_id") != step7g_freeze.RELEASE_ID:
        raise RuntimeError("Step 8A handoff is not bound to the frozen Step-7G release ID.")
    if upstream.get("integration_version") != step7g_freeze.INTEGRATION_VERSION:
        raise RuntimeError("Step 8A handoff is not bound to the frozen Step-7G integration version.")
    if upstream.get("frozen_head_sha") != STEP7G_FROZEN_HEAD_SHA:
        raise RuntimeError("Step 8A handoff is not bound to the certified Step-7G frozen head SHA.")
    if upstream.get("candidate_scope") != {}:
        raise RuntimeError("Step 8A handoff admitted unresolved Step-7G candidate scope.")

    reference = handoff.get("snapshot_reference")
    snapshot = handoff.get("snapshot")
    proof = handoff.get("readiness_proof")
    if not isinstance(reference, dict) or not isinstance(snapshot, dict) or not isinstance(proof, dict):
        raise RuntimeError("Step 8A handoff is missing snapshot/readiness proof.")
    if reference.get("game_id") != game_id or reference.get("player_id") != player_id:
        raise RuntimeError("Step 8A snapshot reference returned wrong requested identity.")
    if snapshot.get("game_id") != game_id or snapshot.get("player_id") != player_id:
        raise RuntimeError("Step 8A included snapshot returned wrong requested identity.")
    digest = recompute_step4w_snapshot_content_sha256(snapshot)
    if digest != snapshot.get("content_sha256") or digest != reference.get("content_sha256"):
        raise RuntimeError("Step 8A live snapshot failed independent Step-4W content hash recomputation.")
    if proof.get("can_start_projection") is not True:
        raise RuntimeError("Step 8A readiness proof is not startable.")
    summary = proof.get("summary") or {}
    if summary.get("blocker_count") != 0 or list(summary.get("blocker_ids") or []):
        raise RuntimeError("Step 8A readiness proof contains blockers.")
    if not set(summary.get("warning_ids") or []).issubset(step7g_freeze.ALLOWED_NON_BLOCKING_WARNING_IDS):
        raise RuntimeError("Step 8A readiness proof contains unexpected warnings.")
    required = proof.get("required_release_checks")
    if not isinstance(required, dict) or set(required) != set(step7g_freeze.REQUIRED_RELEASE_DEFAULT_CHECKS):
        raise RuntimeError("Step 8A readiness proof does not contain the exact frozen release checks.")
    if any((row or {}).get("severity") != "pass" for row in required.values()):
        raise RuntimeError("Step 8A readiness proof contains a non-pass frozen release check.")

    guardrails = handoff.get("guardrails")
    verification = handoff.get("verification")
    if not isinstance(guardrails, dict) or not isinstance(verification, dict):
        raise RuntimeError("Step 8A handoff guardrails/verification are missing.")
    for key in (
        "handoff_is_not_projection",
        "no_projected_minutes_created",
        "no_projected_starters_created",
        "no_monte_carlo_created",
        "no_sportsbook_data_created",
        "no_betting_probability_created",
        "no_persistence_created",
        "no_production_activation_created",
    ):
        if guardrails.get(key) is not True:
            raise RuntimeError(f"Step 8A handoff guardrail {key!r} is not true.")
    if verification.get("no_model_output_created") is not True:
        raise RuntimeError("Step 8A handoff unexpectedly contains model output semantics.")

    handoff_sha = str(handoff.get("handoff_content_sha256") or "")
    if len(handoff_sha) != 64:
        raise RuntimeError("Step 8A handoff content hash is malformed.")
    return {
        "handoff_id": handoff.get("handoff_id"),
        "handoff_content_sha256": handoff_sha,
        "snapshot_id": reference.get("snapshot_id"),
        "snapshot_content_sha256": reference.get("content_sha256"),
        "readiness": proof.get("readiness"),
        "warning_ids": list(summary.get("warning_ids") or []),
        "required_release_checks": required,
    }


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    from sports_api.main import app
    from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector

    selector.MIN_TIP_BUFFER_HOURS = 0.5
    selected_game, selected_player, _ = selector._select_live_pregame_case()
    game_id = str(selected_game["game_id"])
    player_id = int(selected_player["player_id"])
    path = f"/api/v1/wnba/games/{game_id}/players/{player_id}/model-input-readiness"

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(path)
    if response.status_code != 200:
        raise RuntimeError(f"Step 8A frozen release route returned HTTP {response.status_code}.")
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("Step 8A frozen release route returned non-object JSON.")
    frozen_fastapi = _assert_frozen_fastapi(body)

    handoff = get_player_game_step8_projection_handoff(player_id, game_id)
    handoff_evidence = _assert_handoff(handoff, game_id=game_id, player_id=player_id)

    report = {
        "data_type": "wnba_step8a_projection_handoff_cert_v1",
        "certification_result": "STEP8A_PROJECTION_HANDOFF_CONTRACT_LIVE_CERTIFIED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step8a": {
            "handoff_release_id": HANDOFF_RELEASE_ID,
            "schema_version": SCHEMA_VERSION,
            "branch_head_sha": os.getenv("GITHUB_SHA"),
            "step7g_frozen_head_sha": STEP7G_FROZEN_HEAD_SHA,
        },
        "selected_game": selected_game,
        "selected_player": selected_player,
        "frozen_step7g_fastapi": {
            "endpoint": path,
            "request_query_overrides": {},
            "http_status": response.status_code,
            "critical_result": frozen_fastapi,
        },
        "live_handoff": handoff_evidence,
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "step7g_enabled_for_isolated_ci_only": True,
            "step8a_enabled_for_isolated_ci_only": True,
            "projection_model_executed": False,
            "monte_carlo_executed": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP8A_PROJECTION_HANDOFF_CONTRACT_LIVE_CERTIFIED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
