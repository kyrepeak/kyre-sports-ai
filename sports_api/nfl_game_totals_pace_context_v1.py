"""Descriptive NFL pace + possession context for Game Totals page Step 4.

Uses the ESPN team-statistics endpoint and only the exact source fields certified
for this step: totalOffensivePlays and possessionTimeSeconds. The output is
context only. It does not consume sportsbook values and does not feed a model.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any

import requests

ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics"
TOTAL_OFFENSIVE_PLAYS = "totalOffensivePlays"
POSSESSION_TIME_SECONDS = "possessionTimeSeconds"
REQUEST_TIMEOUT_SECONDS = 8
OPPORTUNITY_PACE_REF = 64.0
OPPORTUNITY_PACE_BAND = 3.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 kyre-sports-ai/nfl-game-totals-step4",
}


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
    """Extract the two exact source-certified ESPN Step-4 fields."""
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
        "provider": "ESPN NFL team statistics",
        "ready": False,
        "plays_per_game": math.nan,
        "possession_seconds_per_game": math.nan,
        "possession_clock": "—",
        "pace_signal": "UNAVAILABLE",
        "diagnostics": [],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }
    if not abbr:
        base["diagnostics"] = ["missing team abbreviation"]
        return base

    try:
        response = requests.get(
            ESPN_TEAM_STATS.format(team=abbr.lower()),
            params={"season": int(season)},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        metrics = extract_pace_metrics(payload)
    except Exception as exc:
        base["diagnostics"] = [str(exc)[:220]]
        return base

    if metrics.get("ready") is not True:
        base["diagnostics"] = ["exact ESPN pace/possession fields unavailable"]
        return base

    plays = float(metrics["plays_per_game"])
    possession = float(metrics["possession_seconds_per_game"])
    base.update(
        {
            "ready": True,
            "plays_per_game": plays,
            "possession_seconds_per_game": possession,
            "possession_clock": format_possession_clock(possession),
            "pace_signal": classify_opportunity_pace(plays),
            "source_fields": metrics["source_fields"],
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
    ready = bool(away.get("ready") and home.get("ready"))
    if not ready:
        return {
            "ready": False,
            "provider": "ESPN NFL team statistics",
            "away": away,
            "home": home,
            "matchup": {},
            "diagnostics": ["one or both team pace profiles were unavailable"],
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    matchup_plays = (float(away["plays_per_game"]) + float(home["plays_per_game"])) / 2.0
    return {
        "ready": True,
        "provider": "ESPN NFL team statistics",
        "away": away,
        "home": home,
        "matchup": {
            "average_plays_per_game": matchup_plays,
            "pace_signal": classify_opportunity_pace(matchup_plays),
        },
        "diagnostics": [],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


__all__ = [
    "ESPN_TEAM_STATS",
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
]
