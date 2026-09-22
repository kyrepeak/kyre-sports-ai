"""WNBA Live Games Step-3 current-game flow + pace analytics.

Read-only context layer. It consumes the already verified ESPN live-game state
from the frozen Step-1 contract and optionally enriches it with ESPN's live
boxscore summary. It never consumes sportsbook prices and never creates a pick,
projection probability, Monte Carlo result, edge, EV, or qualification.
"""
from __future__ import annotations

from datetime import datetime
import math
import re
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

ET = ZoneInfo("America/New_York")
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"


def _num(value, default=None):
    try:
        x = float(str(value).replace("%", "").strip())
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _int(value, default=0):
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _clock_seconds(clock) -> int | None:
    text = str(clock or "").strip()
    if not text:
        return None
    try:
        if ":" in text:
            mm, ss = text.split(":", 1)
            return max(0, int(mm) * 60 + int(float(ss)))
        return max(0, int(float(text)))
    except Exception:
        return None


def elapsed_seconds(game: dict) -> int:
    """Elapsed competitive game time from verified period + clock."""
    period = max(0, _int(game.get("period"), 0))
    phase = str(game.get("phase") or "").upper()
    clock_left = _clock_seconds(game.get("clock"))

    if "HALF" in phase:
        return 20 * 60
    if period <= 0:
        return 0
    if period <= 4:
        left = 10 * 60 if clock_left is None else min(10 * 60, clock_left)
        return (period - 1) * 10 * 60 + (10 * 60 - left)

    # WNBA overtime periods are five minutes.
    left = 5 * 60 if clock_left is None else min(5 * 60, clock_left)
    return 40 * 60 + (period - 5) * 5 * 60 + (5 * 60 - left)


def regulation_seconds_remaining(game: dict) -> int:
    elapsed = elapsed_seconds(game)
    period = max(0, _int(game.get("period"), 0))
    if period > 4:
        return 0
    return max(0, 40 * 60 - min(40 * 60, elapsed))


@st.cache_data(ttl=8, show_spinner=False, max_entries=20)
def espn_summary(event_id: str):
    fetched = datetime.now(ET)
    meta = {"fetched_at": fetched.isoformat(), "http": None, "error": "", "available": False}
    try:
        response = requests.get(
            ESPN_SUMMARY,
            params={"event": str(event_id)},
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
            },
            timeout=8,
        )
        meta["http"] = int(response.status_code)
        response.raise_for_status()
        payload = response.json()
        meta["available"] = isinstance(payload, dict)
        return payload if isinstance(payload, dict) else {}, meta
    except Exception as exc:
        meta["error"] = str(exc)[:220]
        return {}, meta


def _stat_lookup(stats) -> dict[str, str]:
    out = {}
    for item in stats or []:
        if not isinstance(item, dict):
            continue
        value = item.get("displayValue")
        if value is None:
            value = item.get("value")
        for key in (item.get("name"), item.get("label"), item.get("displayName"), item.get("abbreviation")):
            nk = _norm(key)
            if nk and value is not None:
                out[nk] = str(value)
    return out


def _first_value(lookup: dict[str, str], aliases, default=None):
    for alias in aliases:
        key = _norm(alias)
        if key in lookup:
            return lookup[key]
    return default


def _made_attempted(value):
    text = str(value or "").strip()
    if not text:
        return None, None
    for sep in ("-", "/"):
        if sep in text:
            a, b = text.split(sep, 1)
            return _num(a), _num(b)
    return None, None


def _parse_team_stats(item: dict) -> dict:
    lookup = _stat_lookup((item or {}).get("statistics") or [])

    fgm, fga = _made_attempted(_first_value(lookup, ["fieldGoalsMade-fieldGoalsAttempted", "fieldGoals", "FG"]))
    tpm, tpa = _made_attempted(_first_value(lookup, ["threePointFieldGoalsMade-threePointFieldGoalsAttempted", "threePointFieldGoals", "3PT"]))
    ftm, fta = _made_attempted(_first_value(lookup, ["freeThrowsMade-freeThrowsAttempted", "freeThrows", "FT"]))

    fgm = fgm if fgm is not None else _num(_first_value(lookup, ["fieldGoalsMade", "fgm"]))
    fga = fga if fga is not None else _num(_first_value(lookup, ["fieldGoalsAttempted", "fga"]))
    tpm = tpm if tpm is not None else _num(_first_value(lookup, ["threePointFieldGoalsMade", "3pm"]))
    tpa = tpa if tpa is not None else _num(_first_value(lookup, ["threePointFieldGoalsAttempted", "3pa"]))
    ftm = ftm if ftm is not None else _num(_first_value(lookup, ["freeThrowsMade", "ftm"]))
    fta = fta if fta is not None else _num(_first_value(lookup, ["freeThrowsAttempted", "fta"]))

    return {
        "fgm": fgm,
        "fga": fga,
        "3pm": tpm,
        "3pa": tpa,
        "ftm": ftm,
        "fta": fta,
        "oreb": _num(_first_value(lookup, ["offensiveRebounds", "offRebounds", "oreb"])),
        "dreb": _num(_first_value(lookup, ["defensiveRebounds", "defRebounds", "dreb"])),
        "reb": _num(_first_value(lookup, ["totalRebounds", "rebounds", "reb"])),
        "ast": _num(_first_value(lookup, ["assists", "ast"])),
        "tov": _num(_first_value(lookup, ["turnovers", "totalTurnovers", "to"])),
        "stl": _num(_first_value(lookup, ["steals", "stl"])),
        "blk": _num(_first_value(lookup, ["blocks", "blk"])),
        "pf": _num(_first_value(lookup, ["fouls", "personalFouls", "pf"])),
    }


def summary_team_stats(payload: dict, game: dict) -> dict:
    teams = (((payload or {}).get("boxscore") or {}).get("teams") or [])
    parsed = {}
    away_name = str(game.get("away_team") or "Away")
    home_name = str(game.get("home_team") or "Home")
    away_abbr = str(game.get("away_abbr") or "")
    home_abbr = str(game.get("home_abbr") or "")

    for item in teams:
        if not isinstance(item, dict):
            continue
        team = item.get("team") or {}
        name = str(team.get("displayName") or team.get("shortDisplayName") or "")
        abbr = str(team.get("abbreviation") or "")
        stats = _parse_team_stats(item)
        if _norm(name) == _norm(away_name) or (away_abbr and _norm(abbr) == _norm(away_abbr)):
            parsed["away"] = stats
        elif _norm(name) == _norm(home_name) or (home_abbr and _norm(abbr) == _norm(home_abbr)):
            parsed["home"] = stats
    return parsed


def _quarter_points(game: dict, side: str, period: int) -> int:
    lines = game.get(f"{side}_lines") or {}
    return _int(lines.get(period), 0)


def _half_points(game: dict, side: str, half: int) -> int:
    periods = (1, 2) if half == 1 else (3, 4)
    return sum(_quarter_points(game, side, p) for p in periods)


def _safe_ratio(a, b):
    try:
        a, b = float(a), float(b)
        return a / b if b > 0 else None
    except Exception:
        return None


def _team_metrics(stats: dict, points: float, opp_stats: dict) -> dict:
    fgm, fga = stats.get("fgm"), stats.get("fga")
    tpm, fta = stats.get("3pm"), stats.get("fta")
    oreb, tov = stats.get("oreb"), stats.get("tov")
    opp_dreb = (opp_stats or {}).get("dreb")

    poss = None
    if all(v is not None for v in (fga, fta, oreb, tov)):
        poss = max(0.0, float(fga) + 0.44 * float(fta) - float(oreb) + float(tov))
    efg = None
    if fga is not None and fga > 0 and fgm is not None:
        efg = (float(fgm) + 0.5 * float(tpm or 0.0)) / float(fga)
    ts = None
    if fga is not None and fta is not None:
        denom = 2.0 * (float(fga) + 0.44 * float(fta))
        ts = float(points) / denom if denom > 0 else None
    ftr = _safe_ratio(fta, fga)
    tov_rate = _safe_ratio(tov, poss)
    oreb_rate = None
    if oreb is not None and opp_dreb is not None:
        oreb_rate = _safe_ratio(oreb, float(oreb) + float(opp_dreb))
    ppp = _safe_ratio(points, poss)
    return {
        **stats,
        "poss": poss,
        "efg": efg,
        "ts": ts,
        "ftr": ftr,
        "tov_rate": tov_rate,
        "oreb_rate": oreb_rate,
        "ppp": ppp,
    }


def analyze_game(game: dict) -> dict:
    event_id = str(game.get("espn_event_id") or "")
    payload, summary_meta = espn_summary(event_id) if event_id else ({}, {"available": False, "error": "missing event id"})
    team_stats = summary_team_stats(payload, game) if payload else {}

    away_pts = float(_int(game.get("away_score"), 0))
    home_pts = float(_int(game.get("home_score"), 0))
    total_pts = away_pts + home_pts
    elapsed = elapsed_seconds(game)
    remaining = regulation_seconds_remaining(game)
    elapsed_min = elapsed / 60.0 if elapsed > 0 else 0.0

    score_pace_total = (total_pts / elapsed_min * 40.0) if elapsed_min > 0 else None
    current_q = max(1, _int(game.get("period"), 1))
    current_q_total = _quarter_points(game, "away", current_q) + _quarter_points(game, "home", current_q)
    if current_q <= 4:
        q_elapsed = max(0, elapsed - (current_q - 1) * 600)
        q_rate_final_total = (current_q_total / q_elapsed * 600.0) if q_elapsed > 0 else None
    else:
        q_elapsed = max(0, elapsed - 2400 - (current_q - 5) * 300)
        q_rate_final_total = (current_q_total / q_elapsed * 300.0) if q_elapsed > 0 else None

    away_raw = team_stats.get("away") or {}
    home_raw = team_stats.get("home") or {}
    away_m = _team_metrics(away_raw, away_pts, home_raw) if away_raw else {}
    home_m = _team_metrics(home_raw, home_pts, away_raw) if home_raw else {}

    poss_values = [m.get("poss") for m in (away_m, home_m) if m.get("poss") is not None]
    blended_poss = sum(poss_values) / len(poss_values) if poss_values else None
    pace40 = (blended_poss / elapsed_min * 40.0) if blended_poss is not None and elapsed_min > 0 else None
    remaining_poss = (pace40 * (remaining / 2400.0)) if pace40 is not None else None

    first_half_away = _half_points(game, "away", 1)
    first_half_home = _half_points(game, "home", 1)
    second_half_away = sum(_quarter_points(game, "away", p) for p in range(3, min(current_q, 4) + 1))
    second_half_home = sum(_quarter_points(game, "home", p) for p in range(3, min(current_q, 4) + 1))

    quality = "HIGH" if away_m and home_m and blended_poss is not None else "SCORE/CLOCK ONLY"
    return {
        "event_id": event_id,
        "summary_meta": summary_meta,
        "data_quality": quality,
        "elapsed_seconds": elapsed,
        "regulation_remaining_seconds": remaining,
        "total_points": total_pts,
        "score_pace_total": score_pace_total,
        "current_period": current_q,
        "current_quarter_total": current_q_total,
        "current_quarter_scoring_pace": q_rate_final_total,
        "first_half_away": first_half_away,
        "first_half_home": first_half_home,
        "second_half_away": second_half_away,
        "second_half_home": second_half_home,
        "away": away_m,
        "home": home_m,
        "blended_possessions": blended_poss,
        "pace40": pace40,
        "remaining_possessions": remaining_poss,
    }


def clear_cache():
    try:
        espn_summary.clear()
    except Exception:
        pass


__all__ = [
    "ESPN_SUMMARY", "analyze_game", "clear_cache", "elapsed_seconds",
    "espn_summary", "regulation_seconds_remaining", "summary_team_stats",
]
