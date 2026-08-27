"""Multi-game certification for Step 7G period-aware WNBA rotations.

The gate intentionally covers a recent multi-day slate plus a known overtime
game. Every attempted completed game must produce one unique rotation solution
for both teams. No passing subset is cherry-picked.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api.wnba_schedule import get_daily_schedule_dataset
from sports_api.wnba_step7g_first_party_history import (
    get_first_party_game_box_score_dataset,
    get_first_party_play_by_play_dataset,
)
from sports_api.tools.wnba_step7g_rotation_reconstruction_probe import (
    PLAYER_TOLERANCE_SECONDS,
    TEAM_TOLERANCE_SECONDS,
    _final_period,
    _solve_side,
)

SEASON = 2026
DATES = ("2026-08-23", "2026-08-24", "2026-08-25", "2026-08-26")
KNOWN_OVERTIME_GAME_ID = "1022600261"  # Indiana @ Atlanta, Aug. 16, 2026
MIN_GAMES = 8
MIN_DISTINCT_TEAMS = 12
REPORT_PATH = Path("step7g-rotation-multigame-cert.json")
OFF_ENV = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_games() -> tuple[list[dict], list[dict]]:
    games: list[dict] = []
    schedule_evidence: list[dict] = []
    seen: set[str] = set()
    for target_date in DATES:
        dataset = get_daily_schedule_dataset(target_date, SEASON)
        finals = [
            game for game in dataset["games"]
            if game.get("status", {}).get("category") == "final"
            and isinstance(game.get("game_id"), str)
        ]
        schedule_evidence.append({
            "date": target_date,
            "source_url": dataset["source_url"],
            "source_variant": dataset["source_variant"],
            "official_game_count": dataset["game_count"],
            "final_game_count": len(finals),
            "game_ids": [game["game_id"] for game in finals],
        })
        for game in finals:
            game_id = game["game_id"]
            if game_id in seen:
                continue
            seen.add(game_id)
            games.append({
                "game_id": game_id,
                "date": target_date,
                "away_team_key": game.get("away", {}).get("team_key"),
                "home_team_key": game.get("home", {}).get("team_key"),
                "schedule_status": game.get("status"),
            })

    if KNOWN_OVERTIME_GAME_ID not in seen:
        games.append({
            "game_id": KNOWN_OVERTIME_GAME_ID,
            "date": "2026-08-16",
            "away_team_key": "indiana-fever",
            "home_team_key": "atlanta-dream",
            "schedule_status": {"category": "final", "text": "Final/OT"},
            "explicit_overtime_control": True,
        })
    return games, schedule_evidence


def _certify_game(meta: dict) -> dict:
    game_id = meta["game_id"]
    box = get_first_party_game_box_score_dataset(game_id, SEASON)
    pbp = get_first_party_play_by_play_dataset(game_id, SEASON)
    actions = pbp["actions"]
    final_period = _final_period(actions)
    away = _solve_side("away", box["away"], actions, final_period)
    home = _solve_side("home", box["home"], actions, final_period)
    passed = (
        box["verification"]["requested_game_id_matches_source"]
        and box["verification"]["player_ids_unique"]
        and pbp["verification"]["action_ids_unique_when_present"]
        and pbp["verification"]["all_team_events_mapped_to_registry"]
        and away["passed"]
        and home["passed"]
    )
    return {
        **meta,
        "passed": passed,
        "final_period": final_period,
        "overtime": final_period > 4,
        "source_action_count": pbp["source_action_count"],
        "away": {
            "team_key": box["away"]["team_key"],
            "passed": away["passed"],
            "unique_solution": away.get("unique_solution"),
            "accepted_solution_count": away.get("accepted_solution_count"),
            "combination_count": away.get("combination_count"),
            "max_abs_player_delta_seconds": away.get("best_max_abs_player_delta_seconds"),
            "official_team_total_within_source_precision": away.get("official_team_total_within_source_precision"),
            "period_lineups": away.get("period_lineups"),
            "parse_errors": away.get("parse_errors"),
            "failure_reason": away.get("failure_reason"),
        },
        "home": {
            "team_key": box["home"]["team_key"],
            "passed": home["passed"],
            "unique_solution": home.get("unique_solution"),
            "accepted_solution_count": home.get("accepted_solution_count"),
            "combination_count": home.get("combination_count"),
            "max_abs_player_delta_seconds": home.get("best_max_abs_player_delta_seconds"),
            "official_team_total_within_source_precision": home.get("official_team_total_within_source_precision"),
            "period_lineups": home.get("period_lineups"),
            "parse_errors": home.get("parse_errors"),
            "failure_reason": home.get("failure_reason"),
        },
        "source_urls": {
            "box_score": box["source_url"],
            "play_by_play": pbp["source_url"],
        },
    }


def main() -> None:
    off_state = {key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV}
    if not all(off_state.values()):
        raise RuntimeError("Multi-game rotation cert refused because production is not fully OFF.")

    candidates, schedule_evidence = _candidate_games()
    results = [_certify_game(game) for game in candidates]
    distinct_teams = sorted({
        side["team_key"]
        for result in results
        for side in (result["away"], result["home"])
        if side.get("team_key")
    })
    overtime_games = [result["game_id"] for result in results if result["overtime"]]
    failed_games = [result["game_id"] for result in results if not result["passed"]]
    max_delta = max(
        [
            float(side["max_abs_player_delta_seconds"])
            for result in results
            for side in (result["away"], result["home"])
            if side.get("max_abs_player_delta_seconds") is not None
        ] or [0.0]
    )
    gate = (
        len(results) >= MIN_GAMES
        and len(distinct_teams) >= MIN_DISTINCT_TEAMS
        and bool(overtime_games)
        and not failed_games
        and all(
            side.get("unique_solution") is True
            for result in results
            for side in (result["away"], result["home"])
        )
    )

    report = {
        "data_type": "wnba_step7g_rotation_multigame_certification",
        "created_at_utc": _now(),
        "read_only": True,
        "season": SEASON,
        "production_flags_off": off_state,
        "date_window": list(DATES),
        "known_overtime_control_game_id": KNOWN_OVERTIME_GAME_ID,
        "source": "WNBA Official Schedule + WNBA.com First-Party Page Data",
        "player_tolerance_seconds": PLAYER_TOLERANCE_SECONDS,
        "team_tolerance_seconds": TEAM_TOLERANCE_SECONDS,
        "schedule_evidence": schedule_evidence,
        "summary": {
            "attempted_game_count": len(results),
            "passed_game_count": sum(result["passed"] for result in results),
            "failed_game_ids": failed_games,
            "distinct_team_count": len(distinct_teams),
            "distinct_teams": distinct_teams,
            "overtime_game_count": len(overtime_games),
            "overtime_game_ids": overtime_games,
            "max_observed_player_delta_seconds": round(max_delta, 3),
            "minimum_games_required": MIN_GAMES,
            "minimum_distinct_teams_required": MIN_DISTINCT_TEAMS,
            "all_team_solutions_unique": all(
                side.get("unique_solution") is True
                for result in results
                for side in (result["away"], result["home"])
            ),
            "certification_gate_passed": gate,
        },
        "games": results,
        "decision": {
            "period_aware_rotation_reconstruction_multigame_certified": gate,
            "eligible_for_isolated_provider_fallback_integration": gate,
            "production_activation_allowed": False,
        },
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "attempted_games": len(results),
        "passed_games": sum(result["passed"] for result in results),
        "failed_games": failed_games,
        "distinct_teams": len(distinct_teams),
        "overtime_games": overtime_games,
        "max_player_delta_seconds": round(max_delta, 3),
        "gate_passed": gate,
        "production_activation_allowed": False,
    }, sort_keys=True))

    if not gate:
        raise RuntimeError("Step 7G multi-game rotation certification gate failed.")


if __name__ == "__main__":
    main()
