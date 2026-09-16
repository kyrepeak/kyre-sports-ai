"""Descriptive NFL scoring context for Game Totals page Step 3.

Acquisition is provider-neutral: the shared NFL data router tries certified
free/open sources in priority order, with ESPN retained only as fallback.
Existing prior/current blending and matchup classification are preserved.
Sportsbook data is never consumed here and has 0.0 projection influence.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any

import sports_api.nfl_data_espn_fallback_v1 as espn
import sports_api.nfl_data_nflverse_v1 as nflverse
from sports_api.nfl_data_router_v1 import route_metric

# Compatibility constants retained for older Step-3 source-contract readers.
# Transport now lives in provider adapters; this module performs no HTTP calls.
ESPN_TEAM_SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/schedule"
ESPN_COMPAT_PARAMS = {"seasontype": 2}
PRIOR_GAMES = 6.0
LEAGUE_PPG_REF = 22.5
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


def route_scoring_games(team_abbr: str, season: int, cutoff_day: str) -> dict[str, Any]:
    """Route one team's completed regular-season scoring rows through free sources."""
    return route_metric(
        "scoring_games",
        {
            "team_abbr": _safe(team_abbr).upper(),
            "season": int(season),
            "cutoff_day": str(cutoff_day)[:10],
        },
        (nflverse.fetch_scoring_games, espn.fetch_scoring_games),
    )


def _route_diag(result: dict[str, Any], *, team: str, season: int, games: int) -> dict[str, Any]:
    diagnostics = [str(item) for item in (result.get("diagnostics") or []) if str(item).strip()]
    return {
        "ok": result.get("ready") is True,
        "http": None,
        "error": "; ".join(diagnostics),
        "team": _safe(team).upper(),
        "season": int(season),
        "games": int(games),
        "provider": result.get("provider_used") or MULTISOURCE_PROVIDER,
        "fallback_rank": int(result.get("fallback_rank") or 0),
        "quality": result.get("quality") or "UNAVAILABLE",
        "data_freshness": result.get("data_freshness") or "",
    }


def _completed_regular_games(
    team_abbr: str,
    season: int,
    cutoff_day: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compatibility wrapper around the canonical multi-source scoring route."""
    result = route_scoring_games(team_abbr, season, cutoff_day)
    data = result.get("data") if isinstance(result, dict) else {}
    rows = data.get("games") if isinstance(data, dict) else []
    rows = [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    return rows, _route_diag(result, team=team_abbr, season=season, games=len(rows))


def _summarize_games(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"games": 0, "ppg": math.nan, "papg": math.nan}
    games = float(len(rows))
    return {
        "games": len(rows),
        "ppg": float(sum(float(row["pf"]) for row in rows) / games),
        "papg": float(sum(float(row["pa"]) for row in rows) / games),
    }


def _blend(prior: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Blend current scoring with a six-game prior so early-season context is stable."""
    current_games = float(current.get("games") or 0)
    if current_games <= 0:
        return {
            "games": 0,
            "ppg": _num(prior.get("ppg")),
            "papg": _num(prior.get("papg")),
            "blend_current_weight": 0.0,
            "source_mode": "PRIOR SEASON CARRYOVER",
        }

    prior_weight = PRIOR_GAMES
    out = {
        "games": int(current_games),
        "blend_current_weight": float(current_games / (prior_weight + current_games)),
        "source_mode": "SHRUNK CURRENT + PRIOR",
    }
    for key in ("ppg", "papg"):
        prior_value = _num(prior.get(key))
        current_value = _num(current.get(key))
        if math.isfinite(prior_value) and math.isfinite(current_value):
            out[key] = float((prior_weight * prior_value + current_games * current_value) / (prior_weight + current_games))
        elif math.isfinite(current_value):
            out[key] = float(current_value)
        else:
            out[key] = float(prior_value) if math.isfinite(prior_value) else math.nan
    return out


def classify_scoring_matchup(offense_ppg: Any, opponent_papg: Any) -> str:
    """Classify descriptive scoring pressure without making a projection."""
    offense = _num(offense_ppg)
    defense_allowed = _num(opponent_papg)
    if not math.isfinite(offense) or not math.isfinite(defense_allowed):
        return "UNAVAILABLE"
    matchup_scoring_level = (offense + defense_allowed) / 2.0
    if matchup_scoring_level >= LEAGUE_PPG_REF + 2.0:
        return "FAVORABLE"
    if matchup_scoring_level <= LEAGUE_PPG_REF - 2.0:
        return "TOUGH"
    return "MEDIUM"


def build_team_scoring_profile(team_abbr: str, team_name: str, day_str: str) -> dict[str, Any]:
    season_year = _season_year_for_day(day_str)
    prior_year = season_year - 1

    prior_result = route_scoring_games(team_abbr, prior_year, f"{prior_year + 1}-02-28")
    current_result = route_scoring_games(team_abbr, season_year, day_str)

    prior_data = prior_result.get("data") if isinstance(prior_result, dict) else {}
    current_data = current_result.get("data") if isinstance(current_result, dict) else {}
    prior_rows = prior_data.get("games") if isinstance(prior_data, dict) else []
    current_rows = current_data.get("games") if isinstance(current_data, dict) else []
    prior_rows = [dict(row) for row in prior_rows if isinstance(row, dict)] if isinstance(prior_rows, list) else []
    current_rows = [dict(row) for row in current_rows if isinstance(row, dict)] if isinstance(current_rows, list) else []

    prior = _summarize_games(prior_rows)
    current = _summarize_games(current_rows)
    prior_diag = _route_diag(prior_result, team=team_abbr, season=prior_year, games=len(prior_rows))
    current_diag = _route_diag(current_result, team=team_abbr, season=season_year, games=len(current_rows))
    provenance = {"prior": prior_result, "current": current_result}

    ready = bool(prior_result.get("ready") is True and int(prior.get("games") or 0) >= 12)
    if not ready:
        return {
            "team": team_name,
            "abbr": _safe(team_abbr).upper(),
            "ready": False,
            "error": "insufficient completed prior regular-season scoring data",
            "provider": MULTISOURCE_PROVIDER,
            "prior_diag": prior_diag,
            "current_diag": current_diag,
            "provenance": provenance,
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        }

    blended = _blend(prior, current)
    return {
        "team": team_name,
        "abbr": _safe(team_abbr).upper(),
        "ready": bool(math.isfinite(_num(blended.get("ppg"))) and math.isfinite(_num(blended.get("papg")))),
        "prior_year": prior_year,
        "season_year": season_year,
        "prior": prior,
        "current": current,
        "blended": blended,
        "quality": "HIGH" if int(prior.get("games") or 0) >= 16 else "MEDIUM",
        "provider": MULTISOURCE_PROVIDER,
        "prior_diag": prior_diag,
        "current_diag": current_diag,
        "provenance": provenance,
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
    }


def build_matchup_scoring_context(
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
            cache[key] = build_team_scoring_profile(key, name, day_str)
        return cache[key]

    away_profile = profile(away_abbr, away_team)
    home_profile = profile(home_abbr, home_team)
    provenance = {
        "away": away_profile.get("provenance", {}),
        "home": home_profile.get("provenance", {}),
    }
    ready = bool(away_profile.get("ready") and home_profile.get("ready"))
    if not ready:
        return {
            "ready": False,
            "provider": MULTISOURCE_PROVIDER,
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
            "away": {},
            "home": {},
            "provenance": provenance,
            "diagnostics": ["one or both team scoring profiles were unavailable"],
        }

    away_blended = away_profile["blended"]
    home_blended = home_profile["blended"]
    away_offense = float(away_blended["ppg"])
    home_offense = float(home_blended["ppg"])
    away_defense_allowed = float(away_blended["papg"])
    home_defense_allowed = float(home_blended["papg"])

    return {
        "ready": True,
        "provider": MULTISOURCE_PROVIDER,
        "descriptive_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "away": {
            "team": away_team,
            "abbr": _safe(away_abbr).upper(),
            "offense_ppg": away_offense,
            "opponent_defense_papg": home_defense_allowed,
            "signal": classify_scoring_matchup(away_offense, home_defense_allowed),
            "quality": away_profile.get("quality"),
        },
        "home": {
            "team": home_team,
            "abbr": _safe(home_abbr).upper(),
            "offense_ppg": home_offense,
            "opponent_defense_papg": away_defense_allowed,
            "signal": classify_scoring_matchup(home_offense, away_defense_allowed),
            "quality": home_profile.get("quality"),
        },
        "provenance": provenance,
        "diagnostics": [],
    }


__all__ = [
    "ESPN_TEAM_SCHEDULE",
    "LEAGUE_PPG_REF",
    "MULTISOURCE_PROVIDER",
    "PRIOR_GAMES",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "build_matchup_scoring_context",
    "build_team_scoring_profile",
    "classify_scoring_matchup",
    "route_scoring_games",
]
