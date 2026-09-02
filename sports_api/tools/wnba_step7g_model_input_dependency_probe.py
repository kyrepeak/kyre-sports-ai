"""OFF-only Step 7G probe of the real Step 4X model-input dependency chain.

The probe intentionally uses the real frozen Step 4X -> 4W -> 4V -> 4U/4T/4R
call path. It injects only already-certified first-party WNBA.com transports at
module-local seams. The unresolved Step 4N team-history dependency is replaced
with a sentinel that raises the same frozen upstream exception immediately, so
we can prove whether the real chain reaches that boundary without calling the
known-unreachable Stats host.

No sportsbook, scheduler, persistence, Supabase, or production runtime is used.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_event_lineup_context as event_lineup
from sports_api import wnba_model_input_readiness as readiness
from sports_api import wnba_player_event_features as event_features
from sports_api import wnba_player_opportunity_context as opportunity
from sports_api import wnba_rotation_context as rotation
from sports_api import wnba_schedule as frozen_schedule
from sports_api import wnba_schedule_context as schedule_context
from sports_api.wnba_step7g_first_party_history import (
    WNBAStep7GFirstPartyNotFoundError,
    WNBAStep7GFirstPartyUpstreamError,
    get_first_party_game_box_score_dataset,
    get_first_party_player_recent_game_log_dataset,
    get_first_party_play_by_play_dataset,
)
from sports_api.wnba_step7g_first_party_schedule import (
    _fetch_first_party_schedule_payload,
)

SEASON = 2026
SAMPLE_GAME_ID = "1022600288"
LAST_N_GAMES = 3
REPORT_PATH = Path("step7g-model-input-dependency-probe.json")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _assert_off() -> None:
    bad = {
        key: os.getenv(key)
        for key in _OFF_ENV_KEYS
        if str(os.getenv(key, "false")).strip().casefold() not in {"", "0", "false", "no", "off"}
    }
    if bad:
        raise RuntimeError(
            "Step 7G model-input dependency probe refuses to run while a production switch is enabled: "
            + ", ".join(sorted(bad))
        )


def _first_party_season_schedule_dataset(season: int) -> dict[str, Any]:
    """Step-4N-compatible season view using certified Step-4C normalization."""
    payload, retrieved, variant, source_url, cache_hit = _fetch_first_party_schedule_payload(season)
    root = frozen_schedule._schedule_root(payload)
    games: list[dict[str, Any]] = []
    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        official_date = frozen_schedule._date_block_iso(block.get("gameDate"))
        if official_date is None:
            continue
        raw_games = block.get("games")
        if not isinstance(raw_games, list):
            continue
        for raw in raw_games:
            if not isinstance(raw, dict):
                continue
            normalized = frozen_schedule._normalize_game(raw, official_date, season)
            away_mapped = bool((normalized.get("away") or {}).get("mapped_to_registry"))
            home_mapped = bool((normalized.get("home") or {}).get("mapped_to_registry"))
            if away_mapped and home_mapped:
                games.append(normalized)
            elif away_mapped != home_mapped:
                raise schedule_context.WNBARestTravelUpstreamError(
                    "First-party WNBA schedule returned a one-sided unmapped team identity."
                )
    ids = [game.get("game_id") for game in games if game.get("game_id")]
    if len(ids) != len(set(ids)):
        raise schedule_context.WNBARestTravelUpstreamError(
            "First-party WNBA season schedule contains duplicate game IDs."
        )
    games.sort(
        key=lambda game: (
            game.get("official_schedule_date") or "",
            game.get("game_datetime_utc") or "",
            game.get("game_id") or "",
        )
    )
    return {
        "source": frozen_schedule.WNBA_SCHEDULE_SOURCE,
        "source_url": source_url,
        "source_variant": variant,
        "league_id": frozen_schedule.WNBA_LEAGUE_ID,
        "season": season,
        "retrieved_at_utc": retrieved,
        "cache_hit": cache_hit,
        "game_count": len(games),
        "games": games,
        "verification": {
            "all_game_ids_valid": all(
                bool(game.get("verification", {}).get("game_id_valid")) for game in games
            ),
            "all_game_ids_unique": True,
            "all_teams_mapped_to_registry": True,
        },
    }


def _minutes(player: dict[str, Any]) -> float:
    value = (player.get("stats") or {}).get("minutes") if isinstance(player.get("stats"), dict) else None
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _select_probe_player() -> tuple[dict[str, Any], dict[str, Any]]:
    box = get_first_party_game_box_score_dataset(SAMPLE_GAME_ID, SEASON)
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for side in ("away", "home"):
        team = box.get(side)
        if not isinstance(team, dict):
            continue
        for player in team.get("players", []):
            if not isinstance(player, dict) or not isinstance(player.get("player_id"), int):
                continue
            if player.get("appeared") is not True:
                continue
            candidates.append((_minutes(player), side, player))
    candidates.sort(key=lambda row: (-row[0], row[2]["player_id"]))

    errors: list[str] = []
    for _, side, player in candidates:
        player_id = player["player_id"]
        try:
            history = get_first_party_player_recent_game_log_dataset(
                player_id,
                SEASON,
                season_type="Regular Season",
            )
        except (WNBAStep7GFirstPartyNotFoundError, WNBAStep7GFirstPartyUpstreamError) as exc:
            errors.append(f"{player_id}:{type(exc).__name__}")
            continue
        games = history.get("games")
        if not isinstance(games, list) or len(games) < LAST_N_GAMES:
            continue
        team = box[side]
        latest_matchup = games[0].get("matchup") if isinstance(games[0], dict) else None
        if not isinstance(latest_matchup, dict):
            continue
        if latest_matchup.get("team_key") != team.get("team_key"):
            continue
        return {
            "player_id": player_id,
            "player_name": player.get("full_name"),
            "sample_game_side": side,
            "team_key": team.get("team_key"),
            "sample_game_minutes": _minutes(player),
            "recent_game_count_exposed": len(games),
        }, history
    raise RuntimeError(
        "No sample-game player exposed enough certified first-party recent history for the Step 4X probe. "
        + "; ".join(errors[:5])
    )


def _raise_rotation_transport_unavailable(*args: Any, **kwargs: Any) -> Any:
    raise rotation.WNBAHistoryUpstreamError(
        "STEP7G_DIAGNOSTIC_DIRECT_STATS_TRANSPORT_UNAVAILABLE"
    )


def _raise_optional_lineup_unavailable(*args: Any, **kwargs: Any) -> Any:
    raise opportunity.WNBALineupContextUpstreamError(
        "STEP7G_DIAGNOSTIC_OPTIONAL_LINEUP_STATS_TRANSPORT_UNAVAILABLE"
    )


def main() -> int:
    _assert_off()
    started = datetime.now(timezone.utc)
    player, selected_history = _select_probe_player()
    player_id = int(player["player_id"])
    sentinel = {"team_history_called": False, "calls": []}

    def recent_history(pid: int, season: int, *, season_type: str = "Regular Season") -> dict[str, Any]:
        if pid == player_id and season == SEASON and season_type == "Regular Season":
            return selected_history
        return get_first_party_player_recent_game_log_dataset(
            pid, season, season_type=season_type
        )

    def unresolved_team_history(
        team_key: str,
        season: int,
        *,
        season_type: str = "Regular Season",
        **kwargs: Any,
    ) -> dict[str, Any]:
        sentinel["team_history_called"] = True
        sentinel["calls"].append(
            {
                "team_key": team_key,
                "season": season,
                "season_type": season_type,
            }
        )
        raise schedule_context.WNBATeamHistoryUpstreamError(
            "STEP7G_UNRESOLVED_TEAM_GAME_HISTORY_TRANSPORT_SENTINEL"
        )

    # Module-local diagnostic injections only. Frozen source files are unchanged.
    rotation._request_stats_json = _raise_rotation_transport_unavailable
    rotation.get_player_game_log_dataset = recent_history
    event_lineup.get_play_by_play_dataset = get_first_party_play_by_play_dataset
    event_features.get_player_game_log_dataset = recent_history
    opportunity.get_player_role_context_dataset = _raise_optional_lineup_unavailable
    opportunity.get_lineups_dataset = _raise_optional_lineup_unavailable
    schedule_context._season_schedule_dataset = _first_party_season_schedule_dataset
    schedule_context.get_team_game_log_dataset = unresolved_team_history

    report: dict[str, Any] = {
        "data_type": "wnba_step7g_real_model_input_dependency_probe_v1",
        "started_at_utc": started.isoformat(),
        "season": SEASON,
        "sample_game_id": SAMPLE_GAME_ID,
        "recent_window_games": LAST_N_GAMES,
        "sample_player": player,
        "diagnostic_injections": {
            "first_party_player_recent_history": True,
            "first_party_play_by_play": True,
            "certified_rotation_fallback_forced_by_transport_failure": True,
            "first_party_schedule_for_step4n": True,
            "optional_step4v_lineup_stats_fail_soft_without_network": True,
            "team_history_replaced_by_unresolved_boundary_sentinel": True,
            "frozen_source_files_modified": False,
        },
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
        },
    }

    try:
        result = readiness.get_player_game_model_input_readiness(
            player_id,
            SAMPLE_GAME_ID,
            SEASON,
            season_type="Regular Season",
            last_n_games=LAST_N_GAMES,
            require_current_availability=False,
            include_shot_context=False,
            include_advanced_context=False,
            include_officiating_context=False,
            include_snapshot=True,
        )
    except Exception as exc:  # diagnostic boundary capture; no secrets in inputs
        report["returned_readiness"] = False
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc)[:1000],
        }
    else:
        report["returned_readiness"] = True
        report["readiness"] = result.get("readiness")
        report["can_start_projection"] = result.get("can_start_projection")
        report["summary"] = result.get("summary")

    report["team_history_boundary"] = sentinel
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_seconds"] = round(
        (datetime.now(timezone.utc) - started).total_seconds(), 3
    )

    if sentinel["team_history_called"]:
        report["probe_outcome"] = "REAL_STEP4X_CHAIN_REACHED_UNRESOLVED_TEAM_HISTORY_BOUNDARY"
        report["next_required_dependency"] = "Step 4N official team game history / observed workload"
    elif report.get("returned_readiness"):
        report["probe_outcome"] = "UNEXPECTEDLY_RETURNED_BEFORE_TEAM_HISTORY_BOUNDARY"
    else:
        report["probe_outcome"] = "FAILED_BEFORE_EXPECTED_TEAM_HISTORY_BOUNDARY"

    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_off()

    if report["probe_outcome"] != "REAL_STEP4X_CHAIN_REACHED_UNRESOLVED_TEAM_HISTORY_BOUNDARY":
        raise RuntimeError(
            "Step 7G model-input dependency probe did not reach the expected unresolved team-history boundary."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
