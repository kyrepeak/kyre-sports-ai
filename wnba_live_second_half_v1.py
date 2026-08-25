"""WNBA Live Games Step 4 historical second-half / quarter profile engine.

Read-only descriptive layer. Uses completed ESPN WNBA regular-season games strictly
before the current live snapshot. It does not read sportsbook prices and cannot
change any Step-1/2/3 state, projection, probability, qualification or pick.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

import wnba_data_v232 as data232

ET = ZoneInfo("America/New_York")
ESPN_SCOREBOARD = data232.ESPN_SCOREBOARD
MODEL_VERSION = "WNBA LIVE SECOND-HALF HISTORY V1"


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _safe_score(value):
    if isinstance(value, dict):
        value = value.get("displayValue", value.get("value"))
    try:
        return int(round(float(value)))
    except Exception:
        return None


def _team_id(team: dict) -> int:
    try:
        return int(data232._team_id(team or {}) or 0)
    except Exception:
        return 0


def _is_regular_season(event: dict) -> bool:
    season = event.get("season") or {}
    stype = str(season.get("type") or "").strip().lower()
    slug = str(season.get("slug") or "").strip().lower()
    name = str(season.get("name") or "").strip().lower()
    if stype:
        return stype == "2"
    if slug or name:
        text = f"{slug} {name}"
        return "regular" in text and "post" not in text and "pre" not in text
    return False


def _status_completed(event: dict, comp: dict) -> bool:
    status = event.get("status") or comp.get("status") or {}
    stype = status.get("type") or {}
    return bool(stype.get("completed")) or str(stype.get("state") or "").lower() in {"post", "final"}


def _lines(competitor: dict) -> dict[int, int]:
    out = {}
    for idx, item in enumerate(competitor.get("linescores") or [], 1):
        if not isinstance(item, dict):
            continue
        period = _safe_int(item.get("period"), idx)
        score = _safe_score(item.get("displayValue", item.get("value")))
        if period > 0 and score is not None:
            out[period] = score
    return out


def _event_dt(event: dict, comp: dict):
    value = event.get("date") or comp.get("date")
    if not value:
        return None
    try:
        return pd.to_datetime(value, utc=True)
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False, max_entries=4)
def _season_games(year: int):
    fetched_at = datetime.now(ET).isoformat()
    meta = {"fetched_at": fetched_at, "source": "ESPN WNBA season scoreboard", "error": "", "games": 0}
    try:
        response = requests.get(
            ESPN_SCOREBOARD,
            params={"dates": str(int(year)), "limit": 1000},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        meta["error"] = str(exc)[:220]
        return [], meta

    rows = []
    for event in (payload or {}).get("events") or []:
        if not _is_regular_season(event):
            continue
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        if not _status_completed(event, comp):
            continue

        sides = {}
        for c in comp.get("competitors") or []:
            sides[str(c.get("homeAway") or "").lower()] = c
        away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
        away_t, home_t = away_c.get("team") or {}, home_c.get("team") or {}
        away_id, home_id = _team_id(away_t), _team_id(home_t)
        if not away_id or not home_id:
            continue

        away_lines, home_lines = _lines(away_c), _lines(home_c)
        if any(p not in away_lines or p not in home_lines for p in (1, 2, 3, 4)):
            continue

        away_score = _safe_score(away_c.get("score"))
        home_score = _safe_score(home_c.get("score"))
        if away_score is None or home_score is None:
            continue

        dt = _event_dt(event, comp)
        if dt is None:
            continue

        rows.append({
            "event_id": str(event.get("id") or ""),
            "date_utc": dt.isoformat(),
            "game_date_et": dt.tz_convert(ET).strftime("%Y-%m-%d"),
            "away_team_id": away_id,
            "away_team": str(away_t.get("displayName") or away_t.get("shortDisplayName") or "Away"),
            "home_team_id": home_id,
            "home_team": str(home_t.get("displayName") or home_t.get("shortDisplayName") or "Home"),
            "away_score": away_score,
            "home_score": home_score,
            "away_lines": away_lines,
            "home_lines": home_lines,
        })
    rows.sort(key=lambda r: r["date_utc"], reverse=True)
    meta["games"] = len(rows)
    return rows, meta


def clear_cache():
    try:
        _season_games.clear()
    except Exception:
        st.cache_data.clear()


def _team_rows(team_id: int, season_rows: list[dict], cutoff, exclude_event_id: str = ""):
    out = []
    cutoff_ts = pd.to_datetime(cutoff, utc=True) if cutoff is not None else pd.Timestamp.now(tz="UTC")
    for g in season_rows:
        if exclude_event_id and str(g.get("event_id") or "") == str(exclude_event_id):
            continue
        dt = pd.to_datetime(g.get("date_utc"), utc=True, errors="coerce")
        if pd.isna(dt) or dt >= cutoff_ts:
            continue
        is_away = int(g.get("away_team_id") or 0) == int(team_id)
        is_home = int(g.get("home_team_id") or 0) == int(team_id)
        if not (is_away or is_home):
            continue

        if is_away:
            own, opp = g["away_lines"], g["home_lines"]
            own_final, opp_final = g["away_score"], g["home_score"]
            opp_name = g["home_team"]
            venue = "AWAY"
        else:
            own, opp = g["home_lines"], g["away_lines"]
            own_final, opp_final = g["home_score"], g["away_score"]
            opp_name = g["away_team"]
            venue = "HOME"

        h1_for, h1_against = own[1] + own[2], opp[1] + opp[2]
        q3_for, q3_against = own[3], opp[3]
        q4_for, q4_against = own[4], opp[4]
        h2_for, h2_against = q3_for + q4_for, q3_against + q4_against

        out.append({
            "date": g["game_date_et"],
            "opponent": opp_name,
            "venue": venue,
            "q3_for": q3_for, "q3_against": q3_against,
            "q4_for": q4_for, "q4_against": q4_against,
            "h2_for": h2_for, "h2_against": h2_against,
            "h2_margin": h2_for - h2_against,
            "halftime_margin": h1_for - h1_against,
            "final_margin": own_final - opp_final,
            "won": own_final > opp_final,
        })
    return out


def _avg(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def _rate(num, den):
    return (float(num) / float(den)) if den else None


def _reliability(n: int) -> str:
    if n >= 15:
        return "HIGH"
    if n >= 8:
        return "MEDIUM"
    if n >= 4:
        return "LOW"
    return "THIN"


def profile(team_id: int, season_rows: list[dict], cutoff, current_role: str, exclude_event_id: str = ""):
    rows = _team_rows(team_id, season_rows, cutoff, exclude_event_id)
    recent10, recent5 = rows[:10], rows[:5]
    role_rows = [r for r in rows if r.get("venue") == str(current_role).upper()]

    led = [r for r in rows if r["halftime_margin"] > 0]
    trailed = [r for r in rows if r["halftime_margin"] < 0]
    tied = [r for r in rows if r["halftime_margin"] == 0]

    return {
        "games": len(rows),
        "reliability": _reliability(len(rows)),
        "q3_for": _avg(rows, "q3_for"),
        "q3_against": _avg(rows, "q3_against"),
        "q3_margin": (_avg(rows, "q3_for") - _avg(rows, "q3_against")) if rows else None,
        "q4_for": _avg(rows, "q4_for"),
        "q4_against": _avg(rows, "q4_against"),
        "q4_margin": (_avg(rows, "q4_for") - _avg(rows, "q4_against")) if rows else None,
        "h2_for": _avg(rows, "h2_for"),
        "h2_against": _avg(rows, "h2_against"),
        "h2_margin": _avg(rows, "h2_margin"),
        "h2_win_rate": _rate(sum(1 for r in rows if r["h2_margin"] > 0), len(rows)),
        "l10_h2_margin": _avg(recent10, "h2_margin"),
        "l5_h2_margin": _avg(recent5, "h2_margin"),
        "venue_h2_margin": _avg(role_rows, "h2_margin"),
        "venue_games": len(role_rows),
        "lead_hold_rate": _rate(sum(1 for r in led if r["won"]), len(led)),
        "lead_sample": len(led),
        "comeback_rate": _rate(sum(1 for r in trailed if r["won"]), len(trailed)),
        "trail_sample": len(trailed),
        "tied_half_games": len(tied),
        "last5": recent5,
    }


def profiles_for_game(game: dict, season: int | None = None):
    year = int(season or pd.to_datetime(game.get("captured_at") or datetime.now(ET)).year)
    rows, meta = _season_games(year)
    cutoff = game.get("captured_at") or datetime.now(ET).isoformat()
    event_id = str(game.get("espn_event_id") or "")
    away_id = _safe_int(game.get("away_team_id"))
    home_id = _safe_int(game.get("home_team_id"))
    return {
        "away": profile(away_id, rows, cutoff, "AWAY", event_id) if away_id else {},
        "home": profile(home_id, rows, cutoff, "HOME", event_id) if home_id else {},
        "meta": meta,
    }
