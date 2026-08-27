"""OFF-only smoke of the real FastAPI Step 4X endpoint under Step 7G core mode.

The workflow must set ``WNBA_STEP7G_FIRST_PARTY_ENABLED=true`` before importing
``sports_api.main``. This proves the startup integration is installed before the
WNBA readiness router binds and then calls the actual public API route through
FastAPI's TestClient.

This certification intentionally exercises only the currently certified Step 7G
core scope. It explicitly disables current availability, shot, advanced, and
officiating context in the request. Those default-option dependencies remain a
separate certification boundary and are not silently declared ready here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPORT_PATH = Path("step7g-fastapi-core-smoke.json")
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


def _assert_safety_env() -> None:
    bad = {key: os.getenv(key) for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))}
    if bad:
        raise RuntimeError(
            "Step 7G FastAPI smoke refuses to run while a production switch is enabled: "
            + ", ".join(sorted(bad))
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError(
            "Step 7G FastAPI smoke requires WNBA_STEP7G_FIRST_PARTY_ENABLED=true."
        )


def main() -> int:
    _assert_safety_env()
    started = datetime.now(timezone.utc)

    # Import order is part of the certification: main imports the default-OFF
    # Step 7G integration before WNBA routers. The workflow explicitly enables
    # only that first-party integration flag for this smoke process.
    from sports_api.main import app
    import sports_api.wnba_step7g_first_party_integration as integration
    from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector

    status = integration.get_step7g_first_party_status()
    if status.get("enabled_flag") is not True or status.get("all_core_seams_installed") is not True:
        raise RuntimeError("Step 7G first-party integration was not active before router binding.")

    selected_game, selected_player, _ = selector._select_live_pregame_case()
    game_id = str(selected_game["game_id"])
    player_id = int(selected_player["player_id"])
    path = f"/api/v1/wnba/games/{game_id}/players/{player_id}/model-input-readiness"
    params = {
        "season": SEASON,
        "season_type": "Regular Season",
        "last_n_games": LAST_N_GAMES,
        "require_current_availability": "false",
        "include_shot_context": "false",
        "include_advanced_context": "false",
        "include_officiating_context": "false",
        "include_snapshot": "false",
    }

    with TestClient(app) as client:
        response = client.get(path, params=params)

    try:
        body = response.json()
    except Exception:
        body = {"raw_body_prefix": response.text[:1000]}

    readiness = body.get("readiness") if isinstance(body, dict) else None
    can_start = body.get("can_start_projection") if isinstance(body, dict) else None
    summary = body.get("summary") if isinstance(body, dict) else None
    summary = summary if isinstance(summary, dict) else {}
    blocker_ids = list(summary.get("blocker_ids") or [])
    warning_ids = list(summary.get("warning_ids") or [])

    checks = {
        "http_200": response.status_code == 200,
        "integration_flag_enabled": status.get("enabled_flag") is True,
        "all_certified_core_seams_installed": status.get("all_core_seams_installed") is True,
        "readiness_startable": readiness in {"READY", "READY_WITH_WARNINGS"},
        "can_start_projection_true": can_start is True,
        "no_blockers": not blocker_ids,
        "certified_scope_current_availability_disabled": params["require_current_availability"] == "false",
        "certified_scope_shot_context_disabled": params["include_shot_context"] == "false",
        "certified_scope_advanced_context_disabled": params["include_advanced_context"] == "false",
        "certified_scope_officiating_context_disabled": params["include_officiating_context"] == "false",
    }
    failed = [name for name, passed in checks.items() if not passed]

    report = {
        "data_type": "wnba_step7g_fastapi_core_smoke_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": path,
        "request_params": params,
        "selected_game": selected_game,
        "selected_player": selected_player,
        "http_status": response.status_code,
        "readiness": readiness,
        "can_start_projection": can_start,
        "summary": summary,
        "warning_ids": warning_ids,
        "integration_status": status,
        "checks": checks,
        "failed_checks": failed,
        "certified": not failed,
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "step7g_first_party_enabled_for_ci_process_only": True,
            "full_default_endpoint_scope_certified": False,
        },
    }
    if response.status_code != 200:
        report["response_error"] = body

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safety_env()

    if failed:
        raise RuntimeError(
            "Step 7G FastAPI core smoke failed: " + ", ".join(failed)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
