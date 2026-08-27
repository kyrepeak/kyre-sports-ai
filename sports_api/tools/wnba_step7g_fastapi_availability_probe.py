"""OFF-only diagnostic of the next Step 7G FastAPI default-option boundary.

The certified Step 7G core integration is enabled before importing the FastAPI
app. The public Step 4X endpoint is then called with current availability ON,
while shot, advanced, and officiating contexts remain OFF. This isolates Step 4I
availability without conflating later optional/default dependencies.

This is a diagnostic probe, not an activation. Expected upstream failures are
captured as HTTP responses and written to sanitized evidence so the next exact
transport seam can be identified.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPORT_PATH = Path("step7g-fastapi-availability-probe.json")
SEASON = 2026
LAST_N_GAMES = 3
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
    bad = {key: os.getenv(key) for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))}
    if bad:
        raise RuntimeError(
            "Step 7G availability probe refuses to run while a production switch is enabled: "
            + ", ".join(sorted(bad))
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 7G availability probe requires first-party core mode ON.")


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    from sports_api.main import app
    import sports_api.wnba_step7g_first_party_integration as integration
    from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector

    status = integration.get_step7g_first_party_status()
    if not status.get("all_core_seams_installed"):
        raise RuntimeError("Step 7G core integration was not installed before router binding.")

    # Avoid making the diagnostic depend on the older 2-hour certification
    # buffer. The frozen Step 4X gate remains authoritative about whether tip has
    # materially passed.
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    selected_game, selected_player, _ = selector._select_live_pregame_case()
    game_id = str(selected_game["game_id"])
    player_id = int(selected_player["player_id"])
    path = f"/api/v1/wnba/games/{game_id}/players/{player_id}/model-input-readiness"
    params = {
        "season": SEASON,
        "season_type": "Regular Season",
        "last_n_games": LAST_N_GAMES,
        "require_current_availability": "true",
        "include_shot_context": "false",
        "include_advanced_context": "false",
        "include_officiating_context": "false",
        "include_snapshot": "false",
    }

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(path, params=params)

    try:
        body = response.json()
    except Exception:
        body = {"raw_body_prefix": response.text[:1000]}

    summary = body.get("summary") if isinstance(body, dict) else None
    readiness = body.get("readiness") if isinstance(body, dict) else None
    can_start = body.get("can_start_projection") if isinstance(body, dict) else None
    if response.status_code == 200:
        outcome = "AVAILABILITY_PATH_RETURNED"
        next_required_dependency = None
    elif response.status_code == 502:
        outcome = "AVAILABILITY_UPSTREAM_BOUNDARY_CAPTURED"
        next_required_dependency = "Step 4I current availability upstream dependency"
    elif response.status_code == 404:
        outcome = "AVAILABILITY_NOT_FOUND_BOUNDARY_CAPTURED"
        next_required_dependency = "Step 4I current availability data discovery"
    else:
        outcome = "UNEXPECTED_FASTAPI_RESPONSE"
        next_required_dependency = "Investigate unexpected availability probe response"

    report = {
        "data_type": "wnba_step7g_fastapi_availability_probe_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": path,
        "request_params": params,
        "selected_game": selected_game,
        "selected_player": selected_player,
        "http_status": response.status_code,
        "probe_outcome": outcome,
        "next_required_dependency": next_required_dependency,
        "readiness": readiness,
        "can_start_projection": can_start,
        "summary": summary,
        "response_body": body,
        "integration_status": status,
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "step7g_first_party_enabled_for_ci_process_only": True,
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()

    if outcome == "UNEXPECTED_FASTAPI_RESPONSE":
        raise RuntimeError(f"Unexpected Step 7G availability probe HTTP {response.status_code}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
