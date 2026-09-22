"""Descriptive NFL explosive-play context for Game Totals page Step 5.

Acquisition is provider-neutral: the shared NFL data router prefers canonical
nflverse play-by-play derivation and keeps the existing ESPN statistics fields
as a fallback. The certified 20+ yard explosive definition/classifier and
projection-facing output stay unchanged. Sportsbook data is never consumed.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any

import sports_api.nfl_data_espn_fallback_v1 as espn
import sports_api.nfl_data_nflverse_v1 as nflverse
from sports_api.nfl_data_router_v1 import route_metric

# Legacy/source-contract constants remain for compatibility and diagnostics.
ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics"
RUSHING_BIG_PLAYS = "rushingBigPlays"
RECEIVING_BIG_PLAYS = "receivingBigPlays"
GAMES_PLAYED = "gamesPlayed"
EXPLOSIVE_HIGH_REF = 4.0
EXPLOSIVE_LOW_REF = 2.0
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
    """Legacy pure ESPN extractor retained for backward contract tests."""
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
    """Extract exact legacy ESPN 20+ yard counts and normalize by games played."""
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


def route_explosive(team_abbr: str, season: int) -> dict[str, Any]:
    """Route canonical explosive metrics through nflverse then ESPN fallback."""
    return route_metric(
        "explosive",
        {"team_abbr": _safe(team_abbr).upper(), "season": int(season)},
        (nflverse.fetch_explosive, espn.fetch_explosive),
    )


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
        "provider": MULTISOURCE_PROVIDER,
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
        "provenance": {},
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }
    if not abbr:
        base["diagnostics"] = ["missing team abbreviation"]
        return base

    routed = route_explosive(abbr, season)
    base["provenance"] = routed
    base["diagnostics"] = list(routed.get("diagnostics") or [])
    if routed.get("ready") is not True:
        return base

    data = routed.get("data") if isinstance(routed.get("data"), dict) else {}
    required = (
        "games_played",
        "rushing_big_plays",
        "receiving_big_plays",
        "total_big_plays",
        "rushing_big_plays_per_game",
        "receiving_big_plays_per_game",
        "explosive_plays_per_game",
    )
    numbers = {key: _num(data.get(key)) for key in required}
    if not all(math.isfinite(value) for value in numbers.values()):
        base["diagnostics"] = list(base["diagnostics"]) + ["canonical explosive-play fields unavailable"]
        return base

    rate = float(numbers["explosive_plays_per_game"])
    base.update(
        {
            "ready": True,
            "games_played": float(numbers["games_played"]),
            "rushing_big_plays": float(numbers["rushing_big_plays"]),
            "receiving_big_plays": float(numbers["receiving_big_plays"]),
            "total_big_plays": float(numbers["total_big_plays"]),
            "rushing_big_plays_per_game": float(numbers["rushing_big_plays_per_game"]),
            "receiving_big_plays_per_game": float(numbers["receiving_big_plays_per_game"]),
            "explosive_plays_per_game": rate,
            "signal": classify_explosive_scoring(rate),
            "source_fields": list(routed.get("fields_verified") or []),
            "quality": routed.get("quality") or "UNAVAILABLE",
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
            "diagnostics": ["one or both team explosive profiles were unavailable"],
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    average_rate = (
        float(away["explosive_plays_per_game"]) + float(home["explosive_plays_per_game"])
    ) / 2.0
    return {
        "ready": True,
        "provider": MULTISOURCE_PROVIDER,
        "away": away,
        "home": home,
        "matchup": {
            "average_explosive_plays_per_game": average_rate,
            "signal": classify_explosive_scoring(average_rate),
        },
        "provenance": provenance,
        "diagnostics": [],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


__all__ = [
    "ESPN_TEAM_STATS",
    "EXPLOSIVE_HIGH_REF",
    "EXPLOSIVE_LOW_REF",
    "GAMES_PLAYED",
    "MULTISOURCE_PROVIDER",
    "RECEIVING_BIG_PLAYS",
    "RUSHING_BIG_PLAYS",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "build_matchup_explosive_context",
    "build_team_explosive_profile",
    "classify_explosive_scoring",
    "extract_explosive_metrics",
    "route_explosive",
]
