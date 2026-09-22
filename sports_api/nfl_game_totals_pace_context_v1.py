"""Descriptive NFL pace + possession context for Game Totals page Step 4.

Acquisition is provider-neutral: the shared NFL data router prefers certified
free/open data and retains ESPN only as fallback. The existing pace classifier,
possession display, and public output fields remain unchanged. Sportsbook data
is never consumed here and has 0.0 projection influence.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any

import sports_api.nfl_data_espn_fallback_v1 as espn
import sports_api.nfl_data_nflverse_v1 as nflverse
from sports_api.nfl_data_router_v1 import route_metric

# Compatibility constants retained for older Step-4 extraction tests/readers.
ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics"
TOTAL_OFFENSIVE_PLAYS = "totalOffensivePlays"
POSSESSION_TIME_SECONDS = "possessionTimeSeconds"
OPPORTUNITY_PACE_REF = 64.0
OPPORTUNITY_PACE_BAND = 3.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MULTISOURCE_PROVIDER = "MULTI-SOURCE NFL DATA ROUTER"


def _safe(value: Any, default: str = "") -> str:
    try:
        text = str(value if value is not None else "").strip()
    except Exception:
        text = ""
    return text or default


def _num(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _season_year_for_day(day_str: str) -> int:
    parsed = date.fromisoformat(str(day_str)[:10])
    return parsed.year - 1 if parsed.month <= 2 else parsed.year


def _stat_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Legacy pure extractor retained for source-contract compatibility."""
    results = payload.get("results") or {}
    stats_root = results.get("stats") if isinstance(results, dict) else {}
    categories = stats_root.get("categories") if isinstance(stats_root, dict) else []
    if not isinstance(categories, list):
        return []
    rows: list[dict[str, Any]] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        stats = category.get("stats") or []
        if isinstance(stats, list):
            rows.extend(stat for stat in stats if isinstance(stat, dict))
    return rows


def _per_game_stat(rows: list[dict[str, Any]], name: str) -> float:
    matches = [row for row in rows if _safe(row.get("name")) == name]
    if len(matches) != 1:
        return math.nan
    value = _num(matches[0].get("perGameValue"))
    return value if math.isfinite(value) else math.nan


def extract_pace_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """Legacy pure ESPN payload extractor; transport now lives in the fallback adapter."""
    rows = _stat_rows(payload if isinstance(payload, dict) else {})
    plays = _per_game_stat(rows, TOTAL_OFFENSIVE_PLAYS)
    possession = _per_game_stat(rows, POSSESSION_TIME_SECONDS)
    ready = bool(math.isfinite(plays) and plays > 0 and math.isfinite(possession) and possession > 0)
    return {
        "ready": ready,
        "plays_per_game": float(plays) if math.isfinite(plays) else math.nan,
        "possession_seconds_per_game": float(possession) if math.isfinite(possession) else math.nan,
        "source_fields": [TOTAL_OFFENSIVE_PLAYS, POSSESSION_TIME_SECONDS],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


def route_pace(team_abbr: str, season: int) -> dict[str, Any]:
    """Route one team's pace metric through nflverse, then ESPN fallback."""
    return route_metric(
        "pace",
        {"team_abbr": _safe(team_abbr).upper(), "season": int(season)},
        (nflverse.fetch_pace, espn.fetch_pace),
    )


def classify_opportunity_pace(plays_per_game: Any) -> str:
    """Simple descriptive opportunity-volume band; not a model projection."""
    plays = _num(plays_per_game)
    if not math.isfinite(plays):
        return "UNAVAILABLE"
    if plays >= OPPORTUNITY_PACE_REF + OPPORTUNITY_PACE_BAND:
        return "HIGH"
    if plays <= OPPORTUNITY_PACE_REF - OPPORTUNITY_PACE_BAND:
        return "LOW"
    return "BALANCED"


def format_possession_clock(seconds: Any) -> str:
    value = _num(seconds)
    if not math.isfinite(value) or value < 0:
        return "—"
    total_seconds = int(round(value))
    minutes, remaining = divmod(total_seconds, 60)
    return f"{minutes}:{remaining:02d}"


def build_team_pace_profile(team_abbr: str, team_name: str, day_str: str) -> dict[str, Any]:
    abbr = _safe(team_abbr).upper()
    season = _season_year_for_day(day_str)
    base = {
        "team": team_name,
        "abbr": abbr,
        "season": season,
        "provider": MULTISOURCE_PROVIDER,
        "ready": False,
        "plays_per_game": math.nan,
        "possession_seconds_per_game": math.nan,
        "possession_clock": "—",
        "pace_signal": "UNAVAILABLE",
        "diagnostics": [],
        "provenance": {},
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }
    if not abbr:
        base["diagnostics"] = ["missing team abbreviation"]
        return base

    routed = route_pace(abbr, season)
    base["provenance"] = routed
    base["diagnostics"] = list(routed.get("diagnostics") or [])
    if routed.get("ready") is not True:
        return base

    data = routed.get("data") if isinstance(routed.get("data"), dict) else {}
    plays = _num(data.get("plays_per_game"))
    possession = _num(data.get("possession_seconds_per_game"))
    if not math.isfinite(plays) or plays <= 0 or not math.isfinite(possession) or possession <= 0:
        base["diagnostics"] = list(base["diagnostics"]) + ["canonical pace/possession fields unavailable"]
        return base

    base.update(
        {
            "ready": True,
            "plays_per_game": float(plays),
            "possession_seconds_per_game": float(possession),
            "possession_clock": format_possession_clock(possession),
            "pace_signal": classify_opportunity_pace(plays),
            "source_fields": list(routed.get("fields_verified") or []),
            "quality": routed.get("quality") or "UNAVAILABLE",
        }
    )
    return base


def build_matchup_pace_context(
    away_abbr: str,
    away_team: str,
    home_abbr: str,
    home_team: str,
    day_str: str,
    *,
    profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cache = profiles if profiles is not None else {}

    def profile(abbr: str, name: str) -> dict[str, Any]:
        key = _safe(abbr).upper()
        if key not in cache:
            cache[key] = build_team_pace_profile(key, name, day_str)
        return cache[key]

    away = profile(away_abbr, away_team)
    home = profile(home_abbr, home_team)
    provenance = {
        "away": away.get("provenance", {}),
        "home": home.get("provenance", {}),
    }
    ready = bool(away.get("ready") and home.get("ready"))
    if not ready:
        return {
            "ready": False,
            "provider": MULTISOURCE_PROVIDER,
            "away": away,
            "home": home,
            "matchup": {},
            "provenance": provenance,
            "diagnostics": ["one or both team pace profiles were unavailable"],
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    matchup_plays = (float(away["plays_per_game"]) + float(home["plays_per_game"])) / 2.0
    return {
        "ready": True,
        "provider": MULTISOURCE_PROVIDER,
        "away": away,
        "home": home,
        "matchup": {
            "average_plays_per_game": matchup_plays,
            "pace_signal": classify_opportunity_pace(matchup_plays),
        },
        "provenance": provenance,
        "diagnostics": [],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


__all__ = [
    "ESPN_TEAM_STATS",
    "MULTISOURCE_PROVIDER",
    "OPPORTUNITY_PACE_BAND",
    "OPPORTUNITY_PACE_REF",
    "POSSESSION_TIME_SECONDS",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "TOTAL_OFFENSIVE_PLAYS",
    "build_matchup_pace_context",
    "build_team_pace_profile",
    "classify_opportunity_pace",
    "extract_pace_metrics",
    "format_possession_clock",
    "route_pace",
]
