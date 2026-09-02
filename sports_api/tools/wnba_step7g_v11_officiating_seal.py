"""Final OFF-only seal for promoted Step 7G v11 officiating integration.

This seal is intentionally separate from the candidate Step-4O certificate.
Success requires the promoted integration metadata itself to say officiating is
certified, no candidate scope to remain, every first-party core seam to be
installed, and the real public model-input-readiness endpoint to pass current
availability, shot, advanced, and officiating coverage using router defaults.
Production runtime and every mutating/sync surface remain disabled.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPORT_PATH = Path("step7g-v11-officiating-seal.json")
EXPECTED_VERSION = "wnba_step_7g_first_party_core_integration_v11_officiating_certified"
SEASON = 2026
_ALLOWED_WARNING_IDS = {
    "optional_starter_bench_role",
    "optional_five_player_lineups",
}
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)
_REQUIRED_CHECKS = (
    "current_availability_available",
    "shot_context_coverage",
    "advanced_context_coverage",
    "officiating_context_coverage",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _assert_safe() -> None:
    enabled = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if enabled:
        raise RuntimeError(
            "v11 seal refuses to run with production switches enabled: "
            + ", ".join(enabled)
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("v11 seal requires Step 7G first-party mode ON only in CI.")


def _check_by_id(body: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    rows = body.get("checks")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("check_id") == check_id:
            return row
    return None


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    # Import the integration before main/router binding and verify the promoted
    # metadata without mutating any source or production state.
    import sports_api.wnba_step7g_first_party_integration as integration

    status = integration.get_step7g_first_party_status()
    scope = status.get("certified_scope") or {}
    if status.get("model_version") != EXPECTED_VERSION:
        raise RuntimeError(f"Unexpected promoted integration version: {status.get('model_version')!r}.")
    if status.get("enabled_flag") is not True:
        raise RuntimeError("Step 7G first-party flag was not enabled in the isolated CI process.")
    if status.get("all_core_seams_installed") is not True:
        raise RuntimeError("Not every Step 7G first-party core seam is installed.")
    if status.get("candidate_scope") != {}:
        raise RuntimeError(f"Promoted v11 still exposes candidate scope: {status.get('candidate_scope')!r}.")
    for key in (
        "core_model_input_readiness",
        "current_availability",
        "current_availability_coordinate_parser",
        "shot_context",
        "advanced_context",
        "officiating_context",
    ):
        if scope.get(key) is not True:
            raise RuntimeError(f"Promoted v11 certified scope is missing {key!r}.")
    if not all((status.get("seams") or {}).values()):
        raise RuntimeError("At least one promoted v11 seam is not installed.")

    from sports_api.main import app
    from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector

    selector.MIN_TIP_BUFFER_HOURS = 0.5
    selected_game, selected_player, _ = selector._select_live_pregame_case()
    game_id = str(selected_game["game_id"])
    player_id = int(selected_player["player_id"])
    path = f"/api/v1/wnba/games/{game_id}/players/{player_id}/model-input-readiness"

    # Empty params are mandatory: router defaults are the release contract.
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(path)
    if response.status_code != 200:
        raise RuntimeError(f"Promoted v11 default route returned HTTP {response.status_code}.")
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("Promoted v11 default route did not return a JSON object.")

    summary = body.get("summary") or {}
    if body.get("readiness") not in {"READY", "READY_WITH_WARNINGS"}:
        raise RuntimeError(f"Promoted v11 readiness is not startable: {body.get('readiness')!r}.")
    if body.get("can_start_projection") is not True:
        raise RuntimeError("Promoted v11 default route cannot start projection.")
    if summary.get("blocker_count") != 0 or list(summary.get("blocker_ids") or []):
        raise RuntimeError(f"Promoted v11 default route has blockers: {summary!r}.")

    warning_ids = list(summary.get("warning_ids") or [])
    if not set(warning_ids).issubset(_ALLOWED_WARNING_IDS):
        raise RuntimeError(f"Promoted v11 has unexpected warnings: {warning_ids!r}.")

    check_evidence: dict[str, dict[str, Any]] = {}
    for check_id in _REQUIRED_CHECKS:
        row = _check_by_id(body, check_id)
        if not isinstance(row, dict):
            raise RuntimeError(f"Promoted v11 is missing required check {check_id!r}.")
        if row.get("severity") != "pass" or row.get("blocking") is not False:
            raise RuntimeError(f"Promoted v11 check {check_id!r} did not pass: {row!r}.")
        check_evidence[check_id] = {
            "severity": row.get("severity"),
            "blocking": row.get("blocking"),
            "observed": row.get("observed"),
        }

    safety = status.get("safety") or {}
    for key in (
        "production_runtime_enabled_by_this_module",
        "scheduler_started_by_this_module",
        "sportsbook_called_by_this_module",
        "supabase_mutation_supported_by_this_module",
        "persistence_supported_by_this_module",
        "frozen_step4x_source_modified",
        "frozen_step4i_source_modified",
        "frozen_step4l_source_modified",
        "frozen_step4f_source_modified",
        "frozen_step4o_source_modified",
    ):
        if safety.get(key) is not False:
            raise RuntimeError(f"Promoted v11 safety flag {key!r} is not false.")

    report = {
        "data_type": "wnba_step7g_v11_officiating_promoted_seal_v1",
        "certification_result": "STEP7G_V11_OFFICIATING_PROMOTED_LIVE_SEALED",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "integration": {
            "model_version": status.get("model_version"),
            "enabled_flag": status.get("enabled_flag"),
            "all_core_seams_installed": status.get("all_core_seams_installed"),
            "certified_scope": scope,
            "candidate_scope": status.get("candidate_scope"),
        },
        "selected_game": selected_game,
        "selected_player": selected_player,
        "fastapi": {
            "endpoint": path,
            "request_query_overrides": {},
            "http_status": response.status_code,
            "readiness": body.get("readiness"),
            "can_start_projection": body.get("can_start_projection"),
            "summary": summary,
            "required_checks": check_evidence,
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "step7g_enabled_for_isolated_ci_only": True,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("STEP7G_V11_OFFICIATING_PROMOTED_LIVE_SEALED")
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
