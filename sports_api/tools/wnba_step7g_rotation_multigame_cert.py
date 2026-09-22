"""Multi-game certification for Step 7G period-aware WNBA rotations.

This certification deliberately uses a fixed matrix of official completed WNBA
game IDs instead of performing schedule discovery at runtime. Schedule transport
and exact-rotation correctness are separate concerns; a CDN or stats-schedule
timeout must not prevent us from testing the rotation solver itself.

The matrix covers ten completed 2026 games, thirteen distinct teams, multiple
recent dates, and a known overtime control. Every attempted game must pass; no
passing subset is cherry-picked. Per-game exceptions are captured in the report
so CI always leaves useful diagnostic evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

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
MIN_GAMES = 8
MIN_DISTINCT_TEAMS = 12
KNOWN_OVERTIME_GAME_ID = "1022600261"
REPORT_PATH = Path("step7g-rotation-multigame-cert.json")
OFF_ENV = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)

# IDs independently verified against public WNBA.com game pages before this
# certification was frozen. Team identity is still taken from each fetched box
# payload, not trusted from these labels.
CERT_GAMES: tuple[dict[str, Any], ...] = (
    {
        "game_id": "1022600278",
        "date": "2026-08-23",
        "label": "Seattle Storm / Dallas Wings",
        "official_page": "https://www.wnba.com/game/sea-vs-dal-1022600278",
    },
    {
        "game_id": "1022600279",
        "date": "2026-08-23",
        "label": "Indiana Fever / Chicago Sky",
        "official_page": "https://www.wnba.com/game/1022600279/boxscore",
    },
    {
        "game_id": "1022600280",
        "date": "2026-08-23",
        "label": "Washington Mystics / Portland Fire",
        "official_page": "https://www.wnba.com/game/1022600280",
    },
    {
        "game_id": "1022600281",
        "date": "2026-08-23",
        "label": "Las Vegas Aces / Toronto Tempo",
        "official_page": "https://www.wnba.com/game/1022600281/LVA-vs-TOR",
    },
    {
        "game_id": "1022600282",
        "date": "2026-08-24",
        "label": "Golden State Valkyries / Minnesota Lynx",
        "official_page": "https://www.wnba.com/game/gsv-vs-min-1022600282",
    },
    {
        "game_id": "1022600284",
        "date": "2026-08-25",
        "label": "Chicago Sky / Connecticut Sun",
        "official_page": "https://www.wnba.com/game/chi-vs-con-1022600284",
    },
    {
        "game_id": "1022600285",
        "date": "2026-08-25",
        "label": "Portland Fire / Dallas Wings",
        "official_page": "https://www.wnba.com/game/pdx-vs-dal-1022600285",
    },
    {
        "game_id": "1022600286",
        "date": "2026-08-25",
        "label": "Washington Mystics / Phoenix Mercury",
        "official_page": "https://www.wnba.com/game/was-vs-phx-1022600286",
    },
    {
        "game_id": "1022600288",
        "date": "2026-08-26",
        "label": "Toronto Tempo / Seattle Storm",
        "official_page": "https://www.wnba.com/game/1022600288",
    },
    {
        "game_id": KNOWN_OVERTIME_GAME_ID,
        "date": "2026-08-16",
        "label": "Indiana Fever / Atlanta Dream",
        "official_page": "https://www.wnba.com/game/1022600261",
        "explicit_overtime_control": True,
    },
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _side_summary(side: dict[str, Any], team_key: str | None) -> dict[str, Any]:
    return {
        "team_key": team_key,
        "passed": side.get("passed"),
        "unique_solution": side.get("unique_solution"),
        "accepted_solution_count": side.get("accepted_solution_count"),
        "combination_count": side.get("combination_count"),
        "max_abs_player_delta_seconds": side.get("best_max_abs_player_delta_seconds"),
        "official_team_total_within_source_precision": side.get(
            "official_team_total_within_source_precision"
        ),
        "period_lineups": side.get("period_lineups"),
        "parse_errors": side.get("parse_errors"),
        "failure_reason": side.get("failure_reason"),
    }


def _certify_game(meta: dict[str, Any]) -> dict[str, Any]:
    game_id = str(meta["game_id"])
    base: dict[str, Any] = {**meta, "attempted": True}
    try:
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
            and away.get("passed") is True
            and home.get("passed") is True
        )
        return {
            **base,
            "passed": bool(passed),
            "final_period": final_period,
            "overtime": final_period > 4,
            "source_action_count": pbp["source_action_count"],
            "away": _side_summary(away, box["away"].get("team_key")),
            "home": _side_summary(home, box["home"].get("team_key")),
            "source_urls": {
                "box_score": box["source_url"],
                "play_by_play": pbp["source_url"],
            },
            "exception": None,
        }
    except Exception as exc:  # diagnostic certification must preserve evidence
        return {
            **base,
            "passed": False,
            "final_period": None,
            "overtime": False,
            "source_action_count": None,
            "away": {},
            "home": {},
            "source_urls": {},
            "exception": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }


def main() -> None:
    off_state = {
        key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV
    }
    if not all(off_state.values()):
        raise RuntimeError(
            "Multi-game rotation cert refused because production is not fully OFF."
        )

    results = [_certify_game(dict(game)) for game in CERT_GAMES]
    distinct_teams = sorted({
        side.get("team_key")
        for result in results
        for side in (result.get("away", {}), result.get("home", {}))
        if side.get("team_key")
    })
    overtime_games = [result["game_id"] for result in results if result.get("overtime")]
    failed_games = [result["game_id"] for result in results if not result.get("passed")]
    exceptions = {
        result["game_id"]: result["exception"]
        for result in results
        if result.get("exception") is not None
    }
    max_delta = max(
        [
            float(side["max_abs_player_delta_seconds"])
            for result in results
            for side in (result.get("away", {}), result.get("home", {}))
            if side.get("max_abs_player_delta_seconds") is not None
        ] or [0.0]
    )
    all_unique = all(
        side.get("unique_solution") is True
        for result in results
        if result.get("passed")
        for side in (result.get("away", {}), result.get("home", {}))
    )
    gate = (
        len(results) >= MIN_GAMES
        and len(distinct_teams) >= MIN_DISTINCT_TEAMS
        and KNOWN_OVERTIME_GAME_ID in overtime_games
        and not failed_games
        and all_unique
    )

    report = {
        "data_type": "wnba_step7g_rotation_multigame_certification",
        "created_at_utc": _now(),
        "read_only": True,
        "season": SEASON,
        "production_flags_off": off_state,
        "source": "Fixed official WNBA.com game-ID matrix + first-party page data",
        "runtime_schedule_discovery_used": False,
        "certification_matrix": list(CERT_GAMES),
        "known_overtime_control_game_id": KNOWN_OVERTIME_GAME_ID,
        "player_tolerance_seconds": PLAYER_TOLERANCE_SECONDS,
        "team_tolerance_seconds": TEAM_TOLERANCE_SECONDS,
        "summary": {
            "attempted_game_count": len(results),
            "passed_game_count": sum(bool(result.get("passed")) for result in results),
            "failed_game_ids": failed_games,
            "exceptions": exceptions,
            "distinct_team_count": len(distinct_teams),
            "distinct_teams": distinct_teams,
            "overtime_game_count": len(overtime_games),
            "overtime_game_ids": overtime_games,
            "max_observed_player_delta_seconds": round(max_delta, 3),
            "minimum_games_required": MIN_GAMES,
            "minimum_distinct_teams_required": MIN_DISTINCT_TEAMS,
            "all_passing_team_solutions_unique": all_unique,
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
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "attempted_games": len(results),
        "passed_games": sum(bool(result.get("passed")) for result in results),
        "failed_games": failed_games,
        "exception_game_ids": sorted(exceptions),
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
