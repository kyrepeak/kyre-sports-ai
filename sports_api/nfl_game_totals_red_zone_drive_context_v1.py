"""Descriptive NFL red-zone and drive-sustainability context for Game Totals Step 6.

Acquisition is provider-neutral: the shared NFL data router prefers canonical
nflverse play-by-play derivation and retains ESPN team statistics as fallback.
The certified red-zone, third-down, first-down thresholds remain unchanged.
Real drive counts are additive context only and do not change Step-8 math.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any

import sports_api.nfl_data_espn_fallback_v1 as espn
import sports_api.nfl_data_nflverse_v1 as nflverse
from sports_api.nfl_data_router_v1 import route_metric

# Legacy/source-contract constants retained for compatibility and diagnostics.
ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/statistics"
RED_ZONE_TOUCHDOWN_PCT = "redzoneTouchdownPct"
THIRD_DOWN_CONV_PCT = "thirdDownConvPct"
FIRST_DOWNS = "firstDowns"
DRIVE_COUNT_FIELD_AVAILABLE = False
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MULTISOURCE_PROVIDER = "MULTI-SOURCE NFL DATA ROUTER"

RZ_TD_HIGH = 60.0
RZ_TD_LOW = 45.0
THIRD_DOWN_HIGH = 45.0
THIRD_DOWN_LOW = 35.0
FIRST_DOWNS_HIGH = 23.0
FIRST_DOWNS_LOW = 19.0


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
    """Legacy pure ESPN payload extractor retained for backward contracts."""
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
    """Extract exact legacy ESPN Step-6 fields and fail closed on ambiguity."""
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


def route_red_zone_drive(team_abbr: str, season: int) -> dict[str, Any]:
    """Route sustainability metrics through nflverse, then ESPN fallback."""
    return route_metric(
        "red_zone_drive",
        {"team_abbr": _safe(team_abbr).upper(), "season": int(season)},
        (nflverse.fetch_red_zone_drive, espn.fetch_red_zone_drive),
    )


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
        "provider": MULTISOURCE_PROVIDER,
        "ready": False,
        "red_zone_td_pct": math.nan,
        "third_down_conv_pct": math.nan,
        "first_downs_per_game": math.nan,
        "drives_per_game": math.nan,
        "drive_count_available": False,
        "signal": "UNAVAILABLE",
        "diagnostics": [],
        "provenance": {},
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }
    if not abbr:
        base["diagnostics"] = ["missing team abbreviation"]
        return base

    routed = route_red_zone_drive(abbr, season)
    base["provenance"] = routed
    base["diagnostics"] = list(routed.get("diagnostics") or [])
    if routed.get("ready") is not True:
        return base

    data = routed.get("data") if isinstance(routed.get("data"), dict) else {}
    rz = _num(data.get("red_zone_td_pct"))
    third = _num(data.get("third_down_conv_pct"))
    first = _num(data.get("first_downs_per_game"))
    if not (
        math.isfinite(rz)
        and 0.0 <= rz <= 100.0
        and math.isfinite(third)
        and 0.0 <= third <= 100.0
        and math.isfinite(first)
        and first >= 0.0
    ):
        base["diagnostics"] = list(base["diagnostics"]) + ["canonical red-zone or sustainability fields unavailable"]
        return base

    drives = _num(data.get("drives_per_game"))
    drive_count_available = bool(math.isfinite(drives) and drives > 0.0)
    base.update(
        {
            "ready": True,
            "red_zone_td_pct": float(rz),
            "third_down_conv_pct": float(third),
            "first_downs_per_game": float(first),
            "drives_per_game": float(drives) if drive_count_available else math.nan,
            "drive_count_available": drive_count_available,
            "signal": classify_drive_sustainability(rz, third, first),
            "source_fields": list(routed.get("fields_verified") or []),
            "quality": routed.get("quality") or "UNAVAILABLE",
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
            "drive_count_available": False,
            "provenance": provenance,
            "diagnostics": ["one or both team red-zone/sustainability profiles were unavailable"],
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    avg_rz = (float(away["red_zone_td_pct"]) + float(home["red_zone_td_pct"])) / 2.0
    avg_third = (float(away["third_down_conv_pct"]) + float(home["third_down_conv_pct"])) / 2.0
    avg_first = (float(away["first_downs_per_game"]) + float(home["first_downs_per_game"])) / 2.0
    drive_count_available = bool(
        away.get("drive_count_available")
        and home.get("drive_count_available")
        and math.isfinite(_num(away.get("drives_per_game")))
        and math.isfinite(_num(home.get("drives_per_game")))
    )

    matchup = {
        "average_red_zone_td_pct": avg_rz,
        "average_third_down_conv_pct": avg_third,
        "average_first_downs_per_game": avg_first,
        "signal": classify_drive_sustainability(avg_rz, avg_third, avg_first),
    }
    if drive_count_available:
        matchup["average_drives_per_game"] = (
            float(away["drives_per_game"]) + float(home["drives_per_game"])
        ) / 2.0

    return {
        "ready": True,
        "provider": MULTISOURCE_PROVIDER,
        "away": away,
        "home": home,
        "matchup": matchup,
        "drive_count_available": drive_count_available,
        "provenance": provenance,
        "diagnostics": [],
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


__all__ = [
    "DRIVE_COUNT_FIELD_AVAILABLE",
    "ESPN_TEAM_STATS",
    "FIRST_DOWNS",
    "MULTISOURCE_PROVIDER",
    "RED_ZONE_TOUCHDOWN_PCT",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "THIRD_DOWN_CONV_PCT",
    "build_matchup_red_zone_drive_context",
    "build_team_red_zone_drive_profile",
    "classify_drive_sustainability",
    "extract_red_zone_drive_metrics",
    "route_red_zone_drive",
]
