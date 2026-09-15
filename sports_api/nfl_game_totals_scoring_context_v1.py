"""Descriptive NFL scoring context for Game Totals page Step 3.

This module intentionally stays independent from the frozen Moneyline model.
It uses completed ESPN regular-season team schedules to summarize points scored
and points allowed, then produces simple offense-vs-defense context labels.
Sportsbook data is never consumed here and has 0.0 projection influence.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any

import requests

ESPN_TEAM_SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/schedule"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Accept": "application/json,text/plain,*/*",
}
REQUEST_TIMEOUT_SECONDS = 8
PRIOR_GAMES = 6.0
LEAGUE_PPG_REF = 22.5
SPORTSBOOK_PROJECTION_WEIGHT = 0.0


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


def _completed_regular_games(team_abbr: str, season: int, cutoff_day: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return completed regular-season scoring rows, failing closed on bad data."""
    abbr = _safe(team_abbr).upper()
    diag = {
        "ok": False,
        "http": None,
        "error": "",
        "team": abbr,
        "season": int(season),
        "games": 0,
        "provider": "ESPN NFL team schedule",
    }
    if not abbr:
        diag["error"] = "missing team abbreviation"
        return [], diag

    try:
        response = requests.get(
            ESPN_TEAM_SCHEDULE.format(team=abbr.lower()),
            params={"season": int(season), "seasontype": 2},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        diag["http"] = int(response.status_code)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return [], diag

    try:
        cutoff = date.fromisoformat(str(cutoff_day)[:10])
    except ValueError:
        diag["error"] = "invalid cutoff day"
        return [], diag

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for event in payload.get("events", []) or []:
        status_type = ((event.get("status") or {}).get("type") or {})
        if not bool(status_type.get("completed")) and _safe(status_type.get("state")).lower() != "post":
            continue
        event_date = _safe(event.get("date"))[:10]
        try:
            event_day = date.fromisoformat(event_date)
        except ValueError:
            continue
        if event_day > cutoff:
            continue

        competitions = event.get("competitions") or []
        if not competitions:
            continue
        competitors = (competitions[0] or {}).get("competitors") or []
        ours = None
        opponent = None
        for competitor in competitors:
            team = competitor.get("team") or {}
            if _safe(team.get("abbreviation")).upper() == abbr:
                ours = competitor
            else:
                opponent = competitor
        if not ours or not opponent:
            continue

        points_for = _num(ours.get("score"))
        points_against = _num(opponent.get("score"))
        if not math.isfinite(points_for) or not math.isfinite(points_against):
            continue

        opponent_abbr = _safe((opponent.get("team") or {}).get("abbreviation")).upper()
        key = (event_day.isoformat(), opponent_abbr)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "date": event_day.isoformat(),
                "pf": float(points_for),
                "pa": float(points_against),
                "opponent_abbr": opponent_abbr,
            }
        )

    rows.sort(key=lambda row: row["date"])
    diag["ok"] = True
    diag["games"] = len(rows)
    return rows, diag


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

    prior_rows, prior_diag = _completed_regular_games(team_abbr, prior_year, f"{prior_year + 1}-02-28")
    current_rows, current_diag = _completed_regular_games(team_abbr, season_year, day_str)
    prior = _summarize_games(prior_rows)
    current = _summarize_games(current_rows)

    ready = bool(prior_diag.get("ok") and int(prior.get("games") or 0) >= 12)
    if not ready:
        return {
            "team": team_name,
            "abbr": _safe(team_abbr).upper(),
            "ready": False,
            "error": "insufficient completed prior regular-season scoring data",
            "provider": "ESPN NFL team schedule",
            "prior_diag": prior_diag,
            "current_diag": current_diag,
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
        "provider": "ESPN NFL team schedule",
        "prior_diag": prior_diag,
        "current_diag": current_diag,
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
    ready = bool(away_profile.get("ready") and home_profile.get("ready"))
    if not ready:
        return {
            "ready": False,
            "provider": "ESPN NFL team schedule",
            "descriptive_only": True,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
            "away": {},
            "home": {},
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
        "provider": "ESPN NFL team schedule",
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
        "diagnostics": [],
    }


__all__ = [
    "ESPN_TEAM_SCHEDULE",
    "LEAGUE_PPG_REF",
    "PRIOR_GAMES",
    "SPORTSBOOK_PROJECTION_WEIGHT",
    "build_matchup_scoring_context",
    "build_team_scoring_profile",
    "classify_scoring_matchup",
]
