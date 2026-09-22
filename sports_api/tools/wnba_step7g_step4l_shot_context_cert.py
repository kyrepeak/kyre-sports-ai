"""OFF-only live certification of Step 7G first-party Step-4L shot context.

The cert selects a real future 2026 WNBA pregame player, exercises all three
shot components consumed by frozen Step 4W, and then calls the real public
FastAPI Step-4X readiness endpoint with *no query overrides*. Success requires
shot_context_coverage=pass, zero blockers, and projection start permission.

Advanced/officiating may remain optional warnings during this isolated Step-4L
certification. No production/scheduler/feed/persistence switch may be enabled.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector
from sports_api.wnba_step7g_first_party_shot_context import (
    get_first_party_opponent_defense_by_shot_zone_dataset,
    get_first_party_player_shot_chart_dataset,
)

REPORT_PATH = Path("step7g-step4l-shot-context-cert.json")
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
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError(
            "Step 4L cert refuses to run with production switches enabled: "
            + ", ".join(bad)
        )
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 4L cert requires Step 7G first-party mode ON in CI.")


def _regular_ids_only(dataset: dict[str, Any]) -> bool:
    ids = dataset.get("selected_game_ids")
    return isinstance(ids, list) and all(
        isinstance(game_id, str)
        and len(game_id) == 10
        and game_id.isdigit()
        and game_id.startswith("10226")
        for game_id in ids
    )


def _check_by_id(body: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    checks = body.get("checks")
    if not isinstance(checks, list):
        return None
    for row in checks:
        if isinstance(row, dict) and row.get("check_id") == check_id:
            return row
    return None


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)

    # The older selector's 2-hour buffer is intentionally relaxed here; frozen
    # Step 4X remains authoritative about whether tip has materially passed.
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    selected_game, selected_player, _ = selector._select_live_pregame_case()
    player_id = int(selected_player["player_id"])
    team_key = str(selected_player["team_key"])
    away_key = str(selected_game["away_team_key"])
    home_key = str(selected_game["home_team_key"])
    if team_key == away_key:
        opponent_key = home_key
    elif team_key == home_key:
        opponent_key = away_key
    else:
        raise RuntimeError("Selected player team is not in selected official game.")

    recent = get_first_party_player_shot_chart_dataset(
        player_id,
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N_GAMES,
    )
    h2h = get_first_party_player_shot_chart_dataset(
        player_id,
        SEASON,
        season_type="Regular Season",
        last_n_games=0,
        opponent_team_key=opponent_key,
    )
    defense = get_first_party_opponent_defense_by_shot_zone_dataset(
        opponent_key,
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N_GAMES,
    )

    if recent.get("data_type") != "official_player_shot_chart":
        raise RuntimeError("Recent first-party shot component returned wrong contract type.")
    if h2h.get("data_type") != "official_player_shot_chart":
        raise RuntimeError("H2H first-party shot component returned wrong contract type.")
    if defense.get("data_type") != "observed_opponent_shooting_by_defensive_team":
        raise RuntimeError("Opponent defense component returned wrong contract type.")
    for label, dataset in (("recent", recent), ("h2h", h2h), ("defense", defense)):
        if not _regular_ids_only(dataset):
            raise RuntimeError(f"{label} Step 4L component admitted a non-regular game ID.")
    if any(
        row.get("player_id") != player_id
        for row in recent.get("shots", [])
        if isinstance(row, dict)
    ):
        raise RuntimeError("Recent shot component returned a conflicting player ID.")
    if any(
        row.get("player_id") != player_id
        for row in h2h.get("shots", [])
        if isinstance(row, dict)
    ):
        raise RuntimeError("H2H shot component returned a conflicting player ID.")

    # Import FastAPI only after the environment is confirmed so the default-OFF
    # integration installs candidate Step-4L seams before router binding.
    from sports_api.main import app
    import sports_api.wnba_step7g_first_party_integration as integration

    status = integration.get_step7g_first_party_status()
    if not status.get("all_core_seams_installed"):
        raise RuntimeError("Step 7G integration seams were not fully installed.")
    seams = status.get("seams") or {}
    if seams.get("projection_player_shot_context") is not True:
        raise RuntimeError("Step 4W player-shot seam is not installed.")
    if seams.get("projection_opponent_zone_defense") is not True:
        raise RuntimeError("Step 4W opponent-zone seam is not installed.")

    game_id = str(selected_game["game_id"])
    path = f"/api/v1/wnba/games/{game_id}/players/{player_id}/model-input-readiness"
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(path)
    try:
        body = response.json()
    except Exception:
        body = {"raw_body_prefix": response.text[:1000]}

    if response.status_code != 200:
        raise RuntimeError(f"Real Step 4X default endpoint returned HTTP {response.status_code}.")
    if not isinstance(body, dict):
        raise RuntimeError("Real Step 4X default endpoint returned a non-object payload.")
    shot_check = _check_by_id(body, "shot_context_coverage")
    if not isinstance(shot_check, dict) or shot_check.get("severity") != "pass":
        raise RuntimeError(f"shot_context_coverage did not pass: {shot_check!r}")
    summary = body.get("summary") or {}
    if summary.get("blocker_count") != 0:
        raise RuntimeError(f"Step 4X still has blockers: {summary!r}")
    if body.get("can_start_projection") is not True:
        raise RuntimeError("Step 4X did not allow projection start after Step 4L integration.")

    report = {
        "data_type": "wnba_step7g_step4l_first_party_shot_context_cert_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": selected_game,
        "selected_player": selected_player,
        "opponent_team_key": opponent_key,
        "direct_components": {
            "recent": {
                "selected_game_count": recent.get("selected_game_count"),
                "selected_game_ids": recent.get("selected_game_ids"),
                "shot_count": recent.get("shot_count"),
                "zone_count": len(recent.get("zone_summary") or []),
                "regular_ids_only": _regular_ids_only(recent),
            },
            "h2h": {
                "selected_game_count": h2h.get("selected_game_count"),
                "selected_game_ids": h2h.get("selected_game_ids"),
                "shot_count": h2h.get("shot_count"),
                "zone_count": len(h2h.get("zone_summary") or []),
                "regular_ids_only": _regular_ids_only(h2h),
            },
            "opponent_defense": {
                "selected_game_count": defense.get("selected_game_count"),
                "selected_game_ids": defense.get("selected_game_ids"),
                "opponent_shooting_team_count": defense.get("opponent_shooting_team_count"),
                "zone_count": len(defense.get("zones_allowed") or []),
                "regular_ids_only": _regular_ids_only(defense),
            },
        },
        "fastapi": {
            "endpoint": path,
            "request_query_overrides": {},
            "http_status": response.status_code,
            "readiness": body.get("readiness"),
            "can_start_projection": body.get("can_start_projection"),
            "summary": summary,
            "shot_context_check": shot_check,
            "warning_ids": summary.get("warning_ids"),
        },
        "integration_status": status,
        "certification_result": "STEP4L_FIRST_PARTY_SHOT_CONTEXT_LIVE_CERTIFIED",
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_enabled": False,
            "sportsbook_sync_enabled": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "step7g_first_party_enabled_for_ci_process_only": True,
            "frozen_step4l_modified": False,
            "frozen_step4w_modified": False,
            "frozen_step4x_modified": False,
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
