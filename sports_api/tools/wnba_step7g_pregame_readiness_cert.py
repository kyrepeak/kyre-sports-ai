"""OFF-only live pregame certification of the complete Step 7G Step 4X chain.

Selects a real future scheduled 2026 WNBA game from the certified first-party
schedule and a recently active player from one of its teams. Then it executes
the real frozen Step 4X readiness gate with only previously certified Step 7G
first-party transport seams injected.

Success requires the real pregame gate to return READY or READY_WITH_WARNINGS,
``can_start_projection`` to be true, no blockers, and any warnings to be limited
to the already-optional starter/bench and five-player-lineup components.
Production remains disabled throughout.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from sports_api.tools import wnba_step7g_model_input_dependency_probe as probe
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)
from sports_api.wnba_step7g_first_party_team_history import (
    get_first_party_team_game_log_dataset,
)

SEASON = 2026
LAST_N_GAMES = 3
MIN_TIP_BUFFER = timedelta(hours=2)
REPORT_PATH = Path("step7g-pregame-readiness-cert.json")
_ALLOWED_WARNING_IDS = {
    "optional_starter_bench_role",
    "optional_five_player_lineups",
}


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _team_in_game(game: dict[str, Any], team_key: str) -> bool:
    return any(
        isinstance(game.get(side), dict) and game[side].get("team_key") == team_key
        for side in ("away", "home")
    )


def _regular_final(game: dict[str, Any], now: datetime) -> bool:
    game_id = str(game.get("game_id") or "")
    status = game.get("status") or {}
    tip = _parse_dt(game.get("game_datetime_utc"))
    return (
        len(game_id) == 10
        and game_id.isdigit()
        and game_id.startswith("10226")
        and status.get("category") == "final"
        and (tip is None or tip < now)
    )


def _minutes(player: dict[str, Any]) -> float:
    stats = player.get("stats")
    value = stats.get("minutes") if isinstance(stats, dict) else None
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _select_live_pregame_case() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = datetime.now(timezone.utc)
    schedule = get_step7g_step4n_season_schedule_dataset(SEASON)
    games = schedule.get("games")
    if not isinstance(games, list):
        raise RuntimeError("Certified first-party schedule returned no games list.")

    upcoming: list[tuple[datetime, dict[str, Any]]] = []
    for game in games:
        if not isinstance(game, dict):
            continue
        status = game.get("status") or {}
        if status.get("category") != "scheduled":
            continue
        tip = _parse_dt(game.get("game_datetime_utc"))
        if tip is None or tip - now < MIN_TIP_BUFFER:
            continue
        verification = game.get("verification") or {}
        if (
            verification.get("game_id_valid") is not True
            or verification.get("teams_mapped_to_registry") is not True
            or verification.get("home_away_distinct") is not True
        ):
            continue
        upcoming.append((tip, game))
    upcoming.sort(key=lambda item: (item[0], str(item[1].get("game_id") or "")))
    if not upcoming:
        raise RuntimeError("No certified scheduled WNBA game exists at least two hours from tip.")

    diagnostics: list[str] = []
    for tip, future_game in upcoming[:8]:
        for future_side in ("away", "home"):
            future_team = future_game.get(future_side) or {}
            team_key = future_team.get("team_key")
            if not team_key:
                continue

            prior = [
                game
                for game in games
                if isinstance(game, dict)
                and _regular_final(game, now)
                and _team_in_game(game, str(team_key))
            ]
            prior.sort(
                key=lambda game: (
                    _parse_dt(game.get("game_datetime_utc")) or datetime.min.replace(tzinfo=timezone.utc),
                    str(game.get("game_id") or ""),
                ),
                reverse=True,
            )

            for previous_game in prior[:3]:
                previous_game_id = str(previous_game.get("game_id") or "")
                try:
                    box = probe.get_first_party_game_box_score_dataset(previous_game_id, SEASON)
                except Exception as exc:
                    diagnostics.append(
                        f"{previous_game_id}:box:{type(exc).__name__}"
                    )
                    continue

                team_box = None
                for side in ("away", "home"):
                    candidate = box.get(side)
                    if isinstance(candidate, dict) and candidate.get("team_key") == team_key:
                        team_box = candidate
                        break
                if not isinstance(team_box, dict):
                    diagnostics.append(f"{previous_game_id}:team_box_missing:{team_key}")
                    continue

                players = [
                    player
                    for player in team_box.get("players", [])
                    if isinstance(player, dict)
                    and isinstance(player.get("player_id"), int)
                    and player.get("appeared") is True
                ]
                players.sort(key=lambda player: (-_minutes(player), int(player["player_id"])))

                for player in players:
                    player_id = int(player["player_id"])
                    try:
                        history = probe.get_first_party_player_recent_game_log_dataset(
                            player_id,
                            SEASON,
                            season_type="Regular Season",
                        )
                    except Exception as exc:
                        diagnostics.append(
                            f"{player_id}:history:{type(exc).__name__}"
                        )
                        continue
                    history_games = history.get("games")
                    if not isinstance(history_games, list) or len(history_games) < LAST_N_GAMES:
                        continue
                    latest = history_games[0] if history_games else None
                    matchup = latest.get("matchup") if isinstance(latest, dict) else None
                    if not isinstance(matchup, dict) or matchup.get("team_key") != team_key:
                        continue

                    selected_game = {
                        "game_id": future_game.get("game_id"),
                        "game_datetime_utc": future_game.get("game_datetime_utc"),
                        "hours_to_tip_at_selection": round(
                            (tip - now).total_seconds() / 3600.0, 3
                        ),
                        "status_category": (future_game.get("status") or {}).get("category"),
                        "away_team_key": (future_game.get("away") or {}).get("team_key"),
                        "home_team_key": (future_game.get("home") or {}).get("team_key"),
                    }
                    selected_player = {
                        "player_id": player_id,
                        "player_name": player.get("full_name"),
                        "team_key": team_key,
                        "future_game_side": future_side,
                        "latest_completed_game_id": previous_game_id,
                        "latest_completed_game_minutes": _minutes(player),
                        "recent_game_count_exposed": len(history_games),
                    }
                    return selected_game, selected_player, history

    raise RuntimeError(
        "No upcoming-game player exposed enough certified recent history. "
        + "; ".join(diagnostics[:12])
    )


def main() -> int:
    probe._assert_off()
    started = datetime.now(timezone.utc)
    selected_game, selected_player, selected_history = _select_live_pregame_case()
    player_id = int(selected_player["player_id"])
    game_id = str(selected_game["game_id"])
    team_history_calls: list[dict[str, Any]] = []

    def recent_history(
        pid: int,
        season: int,
        *,
        season_type: str = "Regular Season",
    ) -> dict[str, Any]:
        if pid == player_id and season == SEASON and season_type == "Regular Season":
            return selected_history
        return probe.get_first_party_player_recent_game_log_dataset(
            pid,
            season,
            season_type=season_type,
        )

    def certified_team_history(
        team_key: str,
        season: int,
        *,
        season_type: str = "Regular Season",
        **kwargs: Any,
    ) -> dict[str, Any]:
        dataset = get_first_party_team_game_log_dataset(
            team_key,
            season,
            season_type=season_type,
            **kwargs,
        )
        verification = dataset.get("verification") or {}
        team_history_calls.append(
            {
                "team_key": team_key,
                "game_count": dataset.get("game_count"),
                "all_rows_mapped": verification.get("all_rows_mapped_to_registry"),
                "all_opponents_resolved": verification.get("all_opponent_team_keys_resolved"),
                "schedule_box_identity_match": verification.get("schedule_box_identity_match"),
                "schedule_box_score_match": verification.get("schedule_box_score_match"),
            }
        )
        return dataset

    # Process-local diagnostic injections only; no frozen source file is modified.
    probe.rotation._request_stats_json = probe._raise_rotation_transport_unavailable
    probe.rotation.get_player_game_log_dataset = recent_history
    probe.event_lineup.get_play_by_play_dataset = probe.get_first_party_play_by_play_dataset
    probe.event_features.get_player_game_log_dataset = recent_history
    probe.opportunity.get_player_role_context_dataset = probe._raise_optional_lineup_unavailable
    probe.opportunity.get_lineups_dataset = probe._raise_optional_lineup_unavailable
    probe.schedule_context._season_schedule_dataset = get_step7g_step4n_season_schedule_dataset
    probe.schedule_context.get_team_game_log_dataset = certified_team_history

    result = probe.readiness.get_player_game_model_input_readiness(
        player_id,
        game_id,
        SEASON,
        season_type="Regular Season",
        last_n_games=LAST_N_GAMES,
        require_current_availability=False,
        include_shot_context=False,
        include_advanced_context=False,
        include_officiating_context=False,
        include_snapshot=True,
    )

    summary = result.get("summary") or {}
    readiness = result.get("readiness")
    blocker_ids = list(summary.get("blocker_ids") or [])
    warning_ids = list(summary.get("warning_ids") or [])
    checks = {
        "real_step4x_returned": True,
        "readiness_is_startable": readiness in {"READY", "READY_WITH_WARNINGS"},
        "can_start_projection_true": result.get("can_start_projection") is True,
        "no_blockers": not blocker_ids,
        "warnings_are_optional_only": set(warning_ids).issubset(_ALLOWED_WARNING_IDS),
        "pregame_status_not_blocking": "pregame_status" not in blocker_ids,
        "tip_time_not_blocking": "game_tip_not_passed" not in blocker_ids,
        "certified_step4j_called": bool(team_history_calls),
        "all_step4j_calls_identity_safe": bool(team_history_calls)
        and all(
            row.get("all_rows_mapped") is True
            and row.get("all_opponents_resolved") is True
            and row.get("schedule_box_identity_match") is True
            and row.get("schedule_box_score_match") is True
            for row in team_history_calls
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]

    report = {
        "data_type": "wnba_step7g_live_pregame_readiness_cert_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": SEASON,
        "recent_window_games": LAST_N_GAMES,
        "selected_game": selected_game,
        "selected_player": selected_player,
        "readiness": readiness,
        "can_start_projection": result.get("can_start_projection"),
        "summary": summary,
        "verification": result.get("verification"),
        "step4j_team_history_calls": team_history_calls,
        "checks": checks,
        "failed_checks": failed,
        "certified": not failed,
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "production_activation_allowed": False,
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    probe._assert_off()
    if failed:
        raise RuntimeError(
            "Live pregame Step 4X certification failed: " + ", ".join(failed)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
