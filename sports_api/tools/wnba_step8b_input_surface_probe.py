"""OFF-only sanitized probe of the Step-8B deterministic model input surface.

Consumes only the certified Step-8A handoff. It does not calculate a projection,
Monte Carlo result, sportsbook probability, or persistence record.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_step8_projection_handoff import get_player_game_step8_projection_handoff
from sports_api.tools import wnba_step7g_pregame_readiness_cert as selector

REPORT_PATH = Path("step8b-input-surface-probe.json")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _assert_safe() -> None:
    bad = [key for key in _OFF_ENV_KEYS if _truthy(os.getenv(key))]
    if bad:
        raise RuntimeError("Step 8B input probe refuses production switches: " + ", ".join(bad))
    if not _truthy(os.getenv("WNBA_STEP7G_FIRST_PARTY_ENABLED")):
        raise RuntimeError("Step 8B input probe requires Step 7G first-party mode in isolated CI.")
    if not _truthy(os.getenv("WNBA_STEP8_PROJECTION_HANDOFF_ENABLED")):
        raise RuntimeError("Step 8B input probe requires Step 8A handoff mode in isolated CI.")


def _dig(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def main() -> int:
    _assert_safe()
    started = datetime.now(timezone.utc)
    selector.MIN_TIP_BUFFER_HOURS = 0.5
    game, player, _ = selector._select_live_pregame_case()
    game_id = str(game["game_id"])
    player_id = int(player["player_id"])
    handoff = get_player_game_step8_projection_handoff(player_id, game_id)
    snapshot = handoff["snapshot"]
    inputs = snapshot["inputs"]
    opportunity = inputs["player_opportunity_context"]
    minutes = opportunity["observed_minutes_opportunity"]
    stability = minutes["tracked_minutes"]["stability"]
    events = opportunity["observed_event_opportunity"]
    per_game = events["own_event_counts_per_feature_game"]
    quality = events["data_quality"]
    availability = inputs.get("game_availability")
    advanced = inputs.get("player_advanced")
    team_advanced = inputs.get("team_advanced")
    opponent_advanced = inputs.get("opponent_advanced")
    rest_travel = inputs.get("game_rest_travel_context")

    report = {
        "data_type": "wnba_step8b_input_surface_probe_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_game": game,
        "selected_player": player,
        "handoff": {
            "handoff_id": handoff.get("handoff_id"),
            "handoff_content_sha256": handoff.get("handoff_content_sha256"),
            "snapshot_id": handoff.get("snapshot_reference", {}).get("snapshot_id"),
            "projection_execution_authorized": handoff.get("projection_execution_authorized"),
        },
        "complete_window_alignment": {
            "requested_games": snapshot.get("recent_window_games"),
            "rotation_source_game_count": minutes.get("source_game_count"),
            "rotation_stability_game_count": stability.get("rotation_game_count"),
            "rotation_missing_game_ids": minutes.get("missing_rotation_game_ids"),
            "event_feature_game_count": events.get("feature_game_count"),
            "event_missing_game_ids": events.get("missing_feature_game_ids"),
        },
        "observed_minutes": {
            "tracked_minutes_by_game": stability.get("tracked_minutes_by_game"),
            "mean": stability.get("tracked_minutes_mean"),
            "median": stability.get("tracked_minutes_median"),
            "minimum": stability.get("tracked_minutes_min"),
            "maximum": stability.get("tracked_minutes_max"),
            "range": stability.get("tracked_minutes_range"),
            "population_stddev": stability.get("tracked_minutes_population_stddev"),
            "coefficient_of_variation": stability.get("tracked_minutes_coefficient_of_variation"),
            "start_share": stability.get("start_share"),
        },
        "feature_event_rates_per_game": {
            "points": per_game.get("points"),
            "rebounds": per_game.get("rebounds"),
            "assists": per_game.get("assists"),
            "field_goals_attempted": per_game.get("field_goals_attempted"),
            "free_throws_attempted": per_game.get("free_throws_attempted"),
            "turnovers": per_game.get("turnovers"),
        },
        "event_quality": {
            "selected_lineup_event_count": quality.get("selected_lineup_event_count"),
            "feature_eligible_event_count": quality.get("feature_eligible_event_count"),
            "feature_eligible_share_of_selected_lineup_events": quality.get("feature_eligible_share_of_selected_lineup_events"),
            "semantics": events.get("semantics"),
        },
        "advanced_context": {
            "player_data_type": advanced.get("data_type") if isinstance(advanced, dict) else None,
            "player_stats": advanced.get("stats") if isinstance(advanced, dict) else None,
            "team_stats": team_advanced.get("stats") if isinstance(team_advanced, dict) else None,
            "opponent_stats": opponent_advanced.get("stats") if isinstance(opponent_advanced, dict) else None,
        },
        "current_availability": {
            "focal_side": snapshot.get("focal_identity", {}).get("side"),
            "focal_summary": snapshot.get("availability_summary"),
            "source_available": isinstance(availability, dict),
        },
        "rest_travel": {
            "focal_team_key": snapshot.get("focal_identity", {}).get("team_key"),
            "opponent_team_key": snapshot.get("focal_identity", {}).get("opponent_team_key"),
            "away": _dig(rest_travel, "away"),
            "home": _dig(rest_travel, "home"),
        },
        "safety": {
            "projection_created": False,
            "monte_carlo_created": False,
            "sportsbook_called": False,
            "persistence_mutated": False,
            "supabase_mutated": False,
            "production_runtime_enabled": False,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_safe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
