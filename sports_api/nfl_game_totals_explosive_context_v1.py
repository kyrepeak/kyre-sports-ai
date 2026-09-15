"""Descriptive NFL explosive-play context for Game Totals page Step 5.

Uses source-certified ESPN team-statistics fields only: rushingBigPlays,
receivingBigPlays, and gamesPlayed. The 20+ yard big-play counts are normalized
per game. This layer is descriptive context only, not projection math.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any

import requests

ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics"
RUSHING_BIG_PLAYS = "rushingBigPlays"
RECEIVING_BIG_PLAYS = "receivingBigPlays"
GAMES_PLAYED = "gamesPlayed"
REQUEST_TIMEOUT_SECONDS = 8
EXPLOSIVE_HIGH_REF = 4.0
EXPLOSIVE_LOW_REF = 2.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 kyre-sports-ai/nfl-game-totals-step5",
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
        category_name = _safe(category.get("name")).lower()
        stats = category.get("stats") or []
        if not isinstance(stats, list):
            continue
        for stat in stats:
            if isinstance(stat, dict):
                row = dict(stat)
                row["_category_name"] = category_name
                rows.append(row)
    return rows


def _single_total(rows: list[dict[str, Any]], name: str, *, category: str | None = None) -> float:
    matches = [
        row for row in rows
        if _safe(row.get("name")) == name
        and (category is None or _safe(row.get("_category_name")).lower() == category.lower())
    ]
    if len(matches) != 1:
        return math.nan
    return _num(matches[0].get("value"))


def extract_explosive_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract exact ESPN 20+ yard counts and normalize them by games played."""
    rows = _stat_rows(payload if isinstance(payload, dict) else {})
    rushing_big = _single_total(rows, RUSHING_BIG_PLAYS, category="rushing")
    receiving_big = _single_total(rows, RECEIVING_BIG_PLAYS, category="receiving")
    games = _single_total(rows, GAMES_PLAYED, category="general")
    ready = bool(
        math.isfinite(games)
        and games > 0
        and math.isfinite(rushing_big)
        and rushing_big >= 0
        and math.isfinite(receiving_big)
        and receiving_big >= 0
    )
    total_big = rushing_big + receiving_big if ready else math.nan
    rush_per_game = rushing_big / games if ready else math.nan
    receive_per_game = receiving_big / games if ready else math.nan
    total_per_game = total_big / games if ready else math.nan
    return {
        "ready": ready,
        "games_played": float(games) if math.isfinite(games) else math.nan,
        "rushing_big_plays": float(rushing_big) if math.isfinite(rushing_big) else math.nan,
        "receiving_big_plays": float(receiving_big) if math.isfinite(receiving_big) else math.nan,
        "total_big_plays": float(total_big) if math.isfinite(total_big) else math.nan,
        "rushing_big_plays_per_game": float(rush_per_game) if math.isfinite(rush_per_game) else math.nan,
        "receiving_big_plays_per_game": float(receive_per_game) if math.isfinite(receive_per_game) else math.nan,
        "explosive_plays_per_game": float(total_per_game) if math.isfinite(total_per_game) else math.nan,
        "source_fields": [RUSHING_BIG_PLAYS, RECEIVING_BIG_PLAYS, GAMES_PLAYED],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


def classify_explosive_scoring(explosive_plays_per_game: Any) -> str:
    """Classify descriptive explosive volume; this is not a total projection."""
    rate = _num(explosive_plays_per_game)
    if not math.isfinite(rate):
        return "UNAVAILABLE"
    if rate >= EXPLOSIVE_HIGH_REF:
        return "HIGH"
    if rate <= EXPLOSIVE_LOW_REF:
        return "LOW"
    return "BALANCED"


def build_team_explosive_profile(team_abbr: str, team_name: str, day_str: str) -> dict[str, Any]:
    abbr = _safe(team_abbr).upper()
    season = _season_year_for_day(day_str)
    base = {
        "team": team_name,
        "abbr": abbr,
        "season": season,
        "provider": "ESPN NFL team statistics",
        "ready": False,
        "games_played": math.nan,
        "rushing_big_plays": math.nan,
        "receiving_big_plays": math.nan,
        "total_big_plays": math.nan,
        "rushing_big_plays_per_game": math.nan,
        "receiving_big_plays_per_game": math.nan,
        "explosive_plays_per_game": math.nan,
        "signal": "UNAVAILABLE",
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
        metrics = extract_explosive_metrics(response.json())
    except Exception as exc:
        base["diagnostics"] = [str(exc)[:220]]
        return base

    if metrics.get("ready") is not True:
        base["diagnostics"] = ["exact ESPN explosive-play or games-played fields unavailable"]
        return base

    rate = float(metrics["explosive_plays_per_game"])
    base.update(
        {
            "ready": True,
            "games_played": float(metrics["games_played"]),
            "rushing_big_plays": float(metrics["rushing_big_plays"]),
            "receiving_big_plays": float(metrics["receiving_big_plays"]),
            "total_big_plays": float(metrics["total_big_plays"]),
            "rushing_big_plays_per_game": float(metrics["rushing_big_plays_per_game"]),
            "receiving_big_plays_per_game": float(metrics["receiving_big_plays_per_game"]),
            "explosive_plays_per_game": rate,
            "signal": classify_explosive_scoring(rate),
            "source_fields": metrics["source_fields"],
        }
    )
    return base


def build_matchup_explosive_context(
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
            cache[key] = build_team_explosive_profile(key, name, day_str)
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
            "diagnostics": ["one or both team explosive profiles were unavailable"],
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    average_rate = (
        float(away["explosive_plays_per_game"]) + float(home["explosive_plays_per_game"])
    ) / 2.0
    return {
        "ready": True,
        "provider": "ESPN NFL team statistics",
        "away": away,
        "home": home,
        "matchup": {
            "average_explosive_plays_per_game": average_rate,
            "signal": classify_explosive_scoring(average_rate),
        },
        "diagnostics": [],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


__all__ = [
    "ESPN_TEAM_STATS",
    "EXPLOSIVE_HIGH_REF",
    "EXPLOSIVE_LOW_REF",
    "GAMES_PLAYED",
    "RECEIVING_BIG_PLAYS",
    "RUSHING_BIG_PLAYS",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "build_matchup_explosive_context",
    "build_team_explosive_profile",
    "classify_explosive_scoring",
    "extract_explosive_metrics",
]
