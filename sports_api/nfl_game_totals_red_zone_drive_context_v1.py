"""Descriptive NFL red-zone and drive-sustainability context for Game Totals Step 6.

Uses source-certified ESPN team-statistics fields only:
- redzoneTouchdownPct
- thirdDownConvPct
- firstDowns (perGameValue)

The certified ESPN team-stat endpoint did not expose a trustworthy drive-count
field, so drive count is explicitly unavailable. Third-down conversion and
first-down volume are used only as descriptive sustainability context.
Sportsbook data is never consumed here and has 0.0 projection influence.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any

import requests

ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics"
RED_ZONE_TOUCHDOWN_PCT = "redzoneTouchdownPct"
THIRD_DOWN_CONV_PCT = "thirdDownConvPct"
FIRST_DOWNS = "firstDowns"
DRIVE_COUNT_FIELD_AVAILABLE = False
REQUEST_TIMEOUT_SECONDS = 8
SPORTSBOOK_PROJECTION_WEIGHT = 0.0

RZ_TD_HIGH = 60.0
RZ_TD_LOW = 45.0
THIRD_DOWN_HIGH = 45.0
THIRD_DOWN_LOW = 35.0
FIRST_DOWNS_HIGH = 23.0
FIRST_DOWNS_LOW = 19.0

HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 kyre-sports-ai/nfl-game-totals-step6",
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


def _misc_stats(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results") or {}
    stats_root = results.get("stats") if isinstance(results, dict) else {}
    categories = stats_root.get("categories") if isinstance(stats_root, dict) else []
    if not isinstance(categories, list):
        return []

    matches = [
        category
        for category in categories
        if isinstance(category, dict)
        and _safe(category.get("name")).lower() == "miscellaneous"
    ]
    if len(matches) != 1:
        return []
    stats = matches[0].get("stats") or []
    return [stat for stat in stats if isinstance(stat, dict)] if isinstance(stats, list) else []


def _single_stat(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    matches = [row for row in rows if _safe(row.get("name")) == name]
    return matches[0] if len(matches) == 1 else None


def extract_red_zone_drive_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract exact ESPN Step-6 fields and fail closed on ambiguity/bad data."""
    rows = _misc_stats(payload if isinstance(payload, dict) else {})
    rz_row = _single_stat(rows, RED_ZONE_TOUCHDOWN_PCT)
    third_row = _single_stat(rows, THIRD_DOWN_CONV_PCT)
    first_row = _single_stat(rows, FIRST_DOWNS)

    rz_td_pct = _num((rz_row or {}).get("value"))
    third_down_pct = _num((third_row or {}).get("value"))
    first_downs_per_game = _num((first_row or {}).get("perGameValue"))

    ready = bool(
        math.isfinite(rz_td_pct)
        and 0.0 <= rz_td_pct <= 100.0
        and math.isfinite(third_down_pct)
        and 0.0 <= third_down_pct <= 100.0
        and math.isfinite(first_downs_per_game)
        and first_downs_per_game >= 0.0
    )

    return {
        "ready": ready,
        "red_zone_td_pct": float(rz_td_pct) if math.isfinite(rz_td_pct) else math.nan,
        "third_down_conv_pct": float(third_down_pct) if math.isfinite(third_down_pct) else math.nan,
        "first_downs_per_game": float(first_downs_per_game) if math.isfinite(first_downs_per_game) else math.nan,
        "drive_count_available": DRIVE_COUNT_FIELD_AVAILABLE,
        "source_fields": [RED_ZONE_TOUCHDOWN_PCT, THIRD_DOWN_CONV_PCT, FIRST_DOWNS],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


def classify_drive_sustainability(
    red_zone_td_pct: Any,
    third_down_conv_pct: Any,
    first_downs_per_game: Any,
) -> str:
    """Classify descriptive scoring/drive sustainability without projecting a total."""
    rz = _num(red_zone_td_pct)
    third = _num(third_down_conv_pct)
    first = _num(first_downs_per_game)
    if not all(math.isfinite(value) for value in (rz, third, first)):
        return "UNAVAILABLE"

    score = 0
    if rz >= RZ_TD_HIGH:
        score += 1
    elif rz <= RZ_TD_LOW:
        score -= 1

    if third >= THIRD_DOWN_HIGH:
        score += 1
    elif third <= THIRD_DOWN_LOW:
        score -= 1

    if first >= FIRST_DOWNS_HIGH:
        score += 1
    elif first <= FIRST_DOWNS_LOW:
        score -= 1

    if score >= 2:
        return "HIGH"
    if score <= -2:
        return "LOW"
    return "BALANCED"


def build_team_red_zone_drive_profile(team_abbr: str, team_name: str, day_str: str) -> dict[str, Any]:
    abbr = _safe(team_abbr).upper()
    season = _season_year_for_day(day_str)
    base = {
        "team": team_name,
        "abbr": abbr,
        "season": season,
        "provider": "ESPN NFL team statistics",
        "ready": False,
        "red_zone_td_pct": math.nan,
        "third_down_conv_pct": math.nan,
        "first_downs_per_game": math.nan,
        "drive_count_available": DRIVE_COUNT_FIELD_AVAILABLE,
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
        metrics = extract_red_zone_drive_metrics(response.json())
    except Exception as exc:
        base["diagnostics"] = [str(exc)[:220]]
        return base

    if metrics.get("ready") is not True:
        base["diagnostics"] = ["exact ESPN red-zone or sustainability fields unavailable"]
        return base

    rz = float(metrics["red_zone_td_pct"])
    third = float(metrics["third_down_conv_pct"])
    first = float(metrics["first_downs_per_game"])
    base.update(
        {
            "ready": True,
            "red_zone_td_pct": rz,
            "third_down_conv_pct": third,
            "first_downs_per_game": first,
            "signal": classify_drive_sustainability(rz, third, first),
            "source_fields": metrics["source_fields"],
        }
    )
    return base


def build_matchup_red_zone_drive_context(
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
            cache[key] = build_team_red_zone_drive_profile(key, name, day_str)
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
            "drive_count_available": DRIVE_COUNT_FIELD_AVAILABLE,
            "diagnostics": ["one or both team red-zone/sustainability profiles were unavailable"],
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    avg_rz = (float(away["red_zone_td_pct"]) + float(home["red_zone_td_pct"])) / 2.0
    avg_third = (float(away["third_down_conv_pct"]) + float(home["third_down_conv_pct"])) / 2.0
    avg_first = (float(away["first_downs_per_game"]) + float(home["first_downs_per_game"])) / 2.0
    return {
        "ready": True,
        "provider": "ESPN NFL team statistics",
        "away": away,
        "home": home,
        "matchup": {
            "average_red_zone_td_pct": avg_rz,
            "average_third_down_conv_pct": avg_third,
            "average_first_downs_per_game": avg_first,
            "signal": classify_drive_sustainability(avg_rz, avg_third, avg_first),
        },
        "drive_count_available": DRIVE_COUNT_FIELD_AVAILABLE,
        "diagnostics": [],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


__all__ = [
    "DRIVE_COUNT_FIELD_AVAILABLE",
    "ESPN_TEAM_STATS",
    "FIRST_DOWNS",
    "RED_ZONE_TOUCHDOWN_PCT",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "THIRD_DOWN_CONV_PCT",
    "build_matchup_red_zone_drive_context",
    "build_team_red_zone_drive_profile",
    "classify_drive_sustainability",
    "extract_red_zone_drive_metrics",
]
