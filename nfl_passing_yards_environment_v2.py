"""NFL Passing Yards environment V2 — early-season pace bridge.

Wraps certified V1. Current event/venue/weather always remain current-game data.
Only season team pace/pass-tendency evidence may fall back to the immediately
prior regular season when the selected regular season has no usable sample yet.
No sportsbook data or synthetic travel/weather values are introduced.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import nfl_passing_yards_defense_v1 as defense
import nfl_passing_yards_early_season_v1 as early
import nfl_passing_yards_environment_v1 as base

MODEL_VERSION = "NFL PASSING YARDS ENVIRONMENT V2 • EARLY SEASON PACE BRIDGE"


def build_game_environment(game: dict, away_ctx: dict, home_ctx: dict, year: int, season_type: int, cutoff_date: str) -> dict:
    current = dict(base.build_game_environment(game, away_ctx, home_ctx, year, season_type, cutoff_date) or {})
    away_pace = dict(current.get("away_pace") or {})
    home_pace = dict(current.get("home_pace") or {})
    away_fallback = False
    home_fallback = False
    source_year = int(year)

    if early.allow_prior_regular_fallback(season_type) and (not away_pace.get("ready") or not home_pace.get("ready")):
        prior_year = early.prior_regular_year(year)
        away_id = str(current.get("away_team_id") or (away_ctx or {}).get("team_id") or "").strip()
        home_id = str(current.get("home_team_id") or (home_ctx or {}).get("team_id") or "").strip()
        with ThreadPoolExecutor(max_workers=2) as pool:
            away_future = pool.submit(defense._team_stats_payload, prior_year, 2, away_id)
            home_future = pool.submit(defense._team_stats_payload, prior_year, 2, home_id)
            away_payload, away_diag = away_future.result()
            home_payload, home_diag = home_future.result()

        if not away_pace.get("ready") and away_diag.get("ok"):
            prior_away = base.parse_team_pace(away_payload)
            if prior_away.get("ready"):
                away_pace = prior_away
                away_fallback = True
        if not home_pace.get("ready") and home_diag.get("ok"):
            prior_home = base.parse_team_pace(home_payload)
            if prior_home.get("ready"):
                home_pace = prior_home
                home_fallback = True
        if away_fallback or home_fallback:
            source_year = prior_year

    current["away_pace"] = away_pace
    current["home_pace"] = home_pace
    away_tendency, away_basis = base.pass_tendency_label(away_pace)
    home_tendency, home_basis = base.pass_tendency_label(home_pace)
    pace_label, pace_basis = base.pace_label(away_pace, home_pace)
    env_label, env_basis = base.environment_label(current.get("event") or {}, current.get("away_rest") or {}, current.get("home_rest") or {})
    current.update({
        "away_pass_tendency": away_tendency,
        "away_pass_tendency_basis": away_basis + (f" • {source_year} early-season baseline" if away_fallback else ""),
        "home_pass_tendency": home_tendency,
        "home_pass_tendency_basis": home_basis + (f" • {source_year} early-season baseline" if home_fallback else ""),
        "pace_label": pace_label,
        "pace_basis": pace_basis + (f" • {source_year} early-season baseline" if (away_fallback or home_fallback) else ""),
        "environment_label": env_label,
        "environment_basis": env_basis,
        "away_pace_early_season_fallback": away_fallback,
        "home_pace_early_season_fallback": home_fallback,
        "baseline_source_year": source_year,
        "early_season_fallback": bool(away_fallback or home_fallback),
        "baseline_provenance": (
            f"EARLY-SEASON PACE BASELINE • {source_year} REGULAR SEASON"
            if (away_fallback or home_fallback)
            else f"CURRENT-SEASON PACE • {int(year)}"
        ),
        "ready": bool(current.get("summary_http") and (away_pace.get("ready") or home_pace.get("ready"))),
        "reason": "" if (away_pace.get("ready") or home_pace.get("ready")) else current.get("reason", "pace evidence incomplete"),
        "projection_adjustment": 0.0,
        "sportsbook_influence": 0.0,
    })
    return current


parse_game_environment = base.parse_game_environment
parse_team_pace = base.parse_team_pace
pass_tendency_label = base.pass_tendency_label
pace_label = base.pace_label
rest_context = base.rest_context
weather_label = base.weather_label
environment_label = base.environment_label

__all__ = [
    "MODEL_VERSION",
    "build_game_environment",
    "environment_label",
    "pace_label",
    "parse_game_environment",
    "parse_team_pace",
    "pass_tendency_label",
    "rest_context",
    "weather_label",
]
