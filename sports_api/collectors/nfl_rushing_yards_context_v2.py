"""Performance-only orchestration for certified NFL Rushing Yards context.

V2 preserves the exact ``nfl_rushing_yards_context_v1`` payload contract and
reuses the frozen V1 parser/identity helpers. It changes only I/O orchestration:
team roster/baseline reads are concurrent, schedule results are reused once per
team, and unique historical game books are fetched concurrently.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from sports_api.collectors import nfl_rushing_yards_context_v1 as frozen

MODEL_VERSION = frozen.MODEL_VERSION
FAST_COLLECTOR_VERSION = "NFL RUSHING YARDS CONTEXT COLLECTOR V2 FAST"
MAX_IO_WORKERS = 6

NFLRushingYardsContextError = frozen.NFLRushingYardsContextError


def _player_profiles_from_games(
    team_id: str,
    baseline_season: int,
    game_ids: list[str],
    roster: dict[str, dict[str, str]],
    summaries: dict[str, dict[str, Any]],
) -> tuple[int, int, list[dict[str, Any]]]:
    agg: dict[str, dict[str, float]] = {}
    for game_id in game_ids:
        game = summaries[game_id]
        for row in frozen._rushing_rows(game, team_id):
            athlete_id = row["official_athlete_id"]
            if athlete_id not in roster:
                continue
            slot = agg.setdefault(
                athlete_id,
                {"attempts": 0.0, "yards": 0.0, "touchdowns": 0.0, "games": 0.0},
            )
            slot["attempts"] += row["attempts"]
            slot["yards"] += row["yards"]
            slot["touchdowns"] += row["touchdowns"]
            slot["games"] += 1.0

    profiles: list[dict[str, Any]] = []
    for athlete_id, totals in agg.items():
        attempts = int(totals["attempts"])
        if attempts <= 0:
            continue
        games = max(1, int(totals["games"]))
        yards = int(totals["yards"])
        info = roster[athlete_id]
        profiles.append(
            {
                "official_athlete_id": athlete_id,
                "official_team_id": team_id,
                "player_name": info["player_name"],
                "position": info["position"],
                "sample_games": games,
                "carries": attempts,
                "rushing_yards": yards,
                "yards_per_carry": round(yards / attempts, 2),
                "carries_per_game": round(attempts / games, 2),
                "rushing_yards_per_game": round(yards / games, 2),
                "rushing_touchdowns": int(totals["touchdowns"]),
                "baseline_season": baseline_season,
            }
        )
    profiles.sort(
        key=lambda x: (x["carries_per_game"], x["rushing_yards_per_game"]),
        reverse=True,
    )
    return baseline_season, len(game_ids), profiles


def _run_front_from_games(
    defense_team_id: str,
    baseline_season: int,
    game_ids: list[str],
    summaries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    attempts = yards = touchdowns = 0.0
    valid_games = 0
    for game_id in game_ids:
        game = summaries[game_id]
        header = game.get("header") or {}
        competitions = header.get("competitions") or []
        comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
        competitors = comp.get("competitors") or []
        opponent_ids = [
            frozen._text(((row.get("team") or {}).get("id")))
            for row in competitors
            if frozen._text(((row.get("team") or {}).get("id"))) != defense_team_id
        ]
        opponent_id = next((value for value in opponent_ids if value.isdigit()), "")
        if not opponent_id:
            continue
        stats = frozen._team_stat_map(game, opponent_id)
        att = stats.get("rushingattempts")
        yds = stats.get("rushingyards")
        td = stats.get("rushingtouchdowns", 0.0)
        if att is None or yds is None:
            continue
        attempts += att
        yards += yds
        touchdowns += td
        valid_games += 1

    if valid_games == 0 or attempts <= 0:
        return {
            "baseline_season": baseline_season,
            "sample_games": 0,
            "rush_attempts_allowed_per_game": None,
            "rush_yards_allowed_per_game": None,
            "yards_per_carry_allowed": None,
            "rushing_touchdowns_allowed_per_game": None,
            "data_available": False,
        }
    return {
        "baseline_season": baseline_season,
        "sample_games": valid_games,
        "rush_attempts_allowed_per_game": round(attempts / valid_games, 2),
        "rush_yards_allowed_per_game": round(yards / valid_games, 2),
        "yards_per_carry_allowed": round(yards / attempts, 2),
        "rushing_touchdowns_allowed_per_game": round(touchdowns / valid_games, 2),
        "data_available": True,
    }


def _fetch_summary(event_id: str) -> dict[str, Any]:
    return frozen._get_json(f"{frozen.ESPN_SITE_BASE}/summary", {"event": event_id})


def collect_nfl_rushing_yards_context_fast(event_id: str) -> dict[str, Any]:
    event_id = frozen._text(event_id)
    if not event_id.isdigit():
        raise NFLRushingYardsContextError(
            "event_id must be an official numeric ESPN NFL event ID"
        )

    event = _fetch_summary(event_id)
    season, teams = frozen._event_identity(event, event_id)
    team_ids = [row["official_team_id"] for row in teams]

    rosters: dict[str, dict[str, dict[str, str]]] = {}
    baselines: dict[str, tuple[int, list[str]]] = {}
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="rush-context-seed") as pool:
        roster_futures = {
            team_id: pool.submit(frozen._roster, team_id) for team_id in team_ids
        }
        baseline_futures = {
            team_id: pool.submit(frozen._baseline_game_ids, team_id, season)
            for team_id in team_ids
        }
        for team_id in team_ids:
            rosters[team_id] = roster_futures[team_id].result()
            baselines[team_id] = baseline_futures[team_id].result()

    unique_game_ids = list(
        dict.fromkeys(
            game_id
            for team_id in team_ids
            for game_id in baselines[team_id][1]
        )
    )
    summaries: dict[str, dict[str, Any]] = {}
    if unique_game_ids:
        with ThreadPoolExecutor(
            max_workers=min(MAX_IO_WORKERS, len(unique_game_ids)),
            thread_name_prefix="rush-context-game",
        ) as pool:
            futures = {
                game_id: pool.submit(_fetch_summary, game_id)
                for game_id in unique_game_ids
            }
            for game_id in unique_game_ids:
                summaries[game_id] = futures[game_id].result()

    team_blocks: list[dict[str, Any]] = []
    total_profiles = 0
    for row in teams:
        team_id = row["official_team_id"]
        opponent_id = next(value for value in team_ids if value != team_id)
        baseline_season, game_ids = baselines[team_id]
        _, sample_games, profiles = _player_profiles_from_games(
            team_id,
            baseline_season,
            game_ids,
            rosters[team_id],
            summaries,
        )
        total_profiles += len(profiles)

        opponent_baseline_season, opponent_game_ids = baselines[opponent_id]
        team_blocks.append(
            {
                **row,
                "opponent_official_team_id": opponent_id,
                "player_baseline_season": baseline_season,
                "player_sample_games": sample_games,
                "players": profiles,
                "opponent_run_front": {
                    "official_team_id": opponent_id,
                    **_run_front_from_games(
                        opponent_id,
                        opponent_baseline_season,
                        opponent_game_ids,
                        summaries,
                    ),
                },
            }
        )

    return {
        "schema_version": MODEL_VERSION,
        "ready": total_profiles > 0,
        "official_event_id": event_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "official_authority": "ESPN",
        "season": season,
        "teams": team_blocks,
        "identity": {
            "official_event_id_required": True,
            "official_athlete_id_required": True,
            "official_team_id_required": True,
            "player_name_display_only": True,
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "semantics": {
            "model_enabled": False,
            "projection_enabled": False,
            "market_enabled": False,
            "sportsbook_influence": 0.0,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
        "source_note": (
            "Recent completed regular-season ESPN game books; if the current season has no "
            "completed games, the prior regular season is used as an explicitly labeled "
            "baseline and current-roster exact athlete IDs remain authoritative."
        ),
    }


__all__ = [
    "FAST_COLLECTOR_VERSION",
    "MAX_IO_WORKERS",
    "MODEL_VERSION",
    "NFLRushingYardsContextError",
    "collect_nfl_rushing_yards_context_fast",
]
