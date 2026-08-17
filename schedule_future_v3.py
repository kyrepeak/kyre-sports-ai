"""MLB schedule V3 — official-first with resilient ESPN MLB fallback.

Priority:
1) Existing strict MLB Stats API verification.
2) Existing simpler MLB Stats API retry/today fallback from V2.
3) ESPN MLB selected-date scoreboard as a schedule-only recovery path when the
   MLB Stats API is temporarily unreachable from Streamlit Cloud.

ESPN recovery rows are clearly tagged. They use stable synthetic negative game
keys so the slate UI can render without pretending an ESPN event id is an MLB
gamePk. Deep MLB-feed enrichment may remain partial until MLB Stats API recovers.
"""
from __future__ import annotations

from datetime import datetime
import hashlib

import pandas as pd
import requests
import streamlit as st

import schedule_future_v2 as base
from engine import ET

current_selected_date = base.current_selected_date
render_slate_date_control = base.render_slate_date_control
MAX_FUTURE_DAYS = base.MAX_FUTURE_DAYS
COLUMNS = base.COLUMNS

ESPN_MLB_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"

MLB_IDS = {
    "ARI": 109, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112,
    "CHW": 145, "CWS": 145, "CIN": 113, "CLE": 114, "COL": 115,
    "DET": 116, "HOU": 117, "KC": 118, "KCR": 118, "LAA": 108,
    "LAD": 119, "MIA": 146, "MIL": 158, "MIN": 142, "NYM": 121,
    "NYY": 147, "ATH": 133, "OAK": 133, "PHI": 143, "PIT": 134,
    "SD": 135, "SDP": 135, "SEA": 136, "SF": 137, "SFG": 137,
    "STL": 138, "TB": 139, "TBR": 139, "TEX": 140, "TOR": 141,
    "WSH": 120, "WSN": 120,
}

NAME_IDS = {
    "Arizona Diamondbacks":109, "Atlanta Braves":144, "Baltimore Orioles":110,
    "Boston Red Sox":111, "Chicago Cubs":112, "Chicago White Sox":145,
    "Cincinnati Reds":113, "Cleveland Guardians":114, "Colorado Rockies":115,
    "Detroit Tigers":116, "Houston Astros":117, "Kansas City Royals":118,
    "Los Angeles Angels":108, "Los Angeles Dodgers":119, "Miami Marlins":146,
    "Milwaukee Brewers":158, "Minnesota Twins":142, "New York Mets":121,
    "New York Yankees":147, "Athletics":133, "Oakland Athletics":133,
    "Philadelphia Phillies":143, "Pittsburgh Pirates":134, "San Diego Padres":135,
    "Seattle Mariners":136, "San Francisco Giants":137, "St. Louis Cardinals":138,
    "Tampa Bay Rays":139, "Texas Rangers":140, "Toronto Blue Jays":141,
    "Washington Nationals":120,
}


def _empty():
    out = pd.DataFrame(columns=COLUMNS + ["schedule_source", "external_game_id"])
    return out


def _team_id(team: dict):
    abbr = str((team or {}).get("abbreviation") or "").upper().strip()
    name = str((team or {}).get("displayName") or (team or {}).get("shortDisplayName") or "").strip()
    return MLB_IDS.get(abbr) or NAME_IDS.get(name)


def _synthetic_pk(event_id: str) -> int:
    text = str(event_id or "")
    if text.isdigit():
        return -int(text[-9:])
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return -int(digest, 16)


def _probable(competitor: dict):
    for p in (competitor or {}).get("probables") or []:
        athlete = p.get("athlete") if isinstance(p, dict) else None
        if isinstance(athlete, dict):
            return athlete.get("id"), athlete.get("displayName") or athlete.get("fullName") or "TBD"
    return None, "TBD"


def _status_text(event: dict, comp: dict):
    stype = ((event.get("status") or {}).get("type") or {}) if isinstance(event, dict) else {}
    return str(stype.get("description") or stype.get("detail") or stype.get("shortDetail") or "Scheduled")


@st.cache_data(ttl=120, show_spinner=False)
def _espn_day(target_date):
    target = base.base._as_date(target_date)
    day = target.isoformat()
    params = {"dates": target.strftime("%Y%m%d"), "limit": 100}
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
    }
    r = requests.get(ESPN_MLB_SCOREBOARD, params=params, headers=headers, timeout=12)
    r.raise_for_status()
    payload = r.json()
    rows = []
    for event in payload.get("events", []) or []:
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        sides = {}
        for c in comp.get("competitors", []) or []:
            if isinstance(c, dict):
                sides[str(c.get("homeAway") or "").lower()] = c
        away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
        away_t, home_t = away_c.get("team") or {}, home_c.get("team") or {}
        away_id, home_id = _team_id(away_t), _team_id(home_t)
        if not away_id or not home_id:
            continue
        raw_dt = event.get("date") or comp.get("date")
        try:
            tip = pd.to_datetime(raw_dt, utc=True).tz_convert(ET)
        except Exception:
            continue
        if tip.date() != target:
            continue
        apid, ap = _probable(away_c)
        hpid, hp = _probable(home_c)
        eid = str(event.get("id") or "")
        rows.append({
            "game_pk": _synthetic_pk(eid),
            "game_date": day,
            "verified": True,
            "venue_name": str((comp.get("venue") or {}).get("fullName") or "Venue TBD"),
            "away_team_id": int(away_id),
            "away_team": str(away_t.get("displayName") or away_t.get("shortDisplayName") or "Away"),
            "home_team_id": int(home_id),
            "home_team": str(home_t.get("displayName") or home_t.get("shortDisplayName") or "Home"),
            "away_pitcher_id": int(apid) if str(apid or "").isdigit() else None,
            "away_pitcher": str(ap or "TBD"),
            "home_pitcher_id": int(hpid) if str(hpid or "").isdigit() else None,
            "home_pitcher": str(hp or "TBD"),
            "first_pitch_et": tip.strftime("%I:%M %p").lstrip("0"),
            "status": _status_text(event, comp),
            "schedule_source": "ESPN MLB schedule recovery",
            "external_game_id": eid,
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=120, show_spinner=False)
def games_for_date(target_date):
    day = base.base._as_date(target_date).isoformat()
    try:
        official = base.games_for_date(day)
        if official is not None and not official.empty:
            out = official.copy()
            out["schedule_source"] = "MLB Stats API verified"
            out["external_game_id"] = ""
            return out
    except Exception:
        pass

    try:
        espn = _espn_day(day)
        if espn is not None and not espn.empty:
            return espn.reset_index(drop=True)
    except Exception:
        pass
    return _empty()


def schedule_diagnostics(target_date):
    day = base.base._as_date(target_date).isoformat()
    out = {"date": day, "source": "none", "games": 0}
    try:
        official = base.games_for_date(day)
        if official is not None and not official.empty:
            return {"date": day, "source": "MLB Stats API verified", "games": int(len(official))}
    except Exception as exc:
        out["official_error"] = type(exc).__name__
    try:
        espn = _espn_day(day)
        if espn is not None and not espn.empty:
            return {"date": day, "source": "ESPN MLB schedule recovery", "games": int(len(espn))}
    except Exception as exc:
        out["espn_error"] = type(exc).__name__
    return out


def clear_schedule_cache():
    for fn in (games_for_date, _espn_day):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        base.clear_schedule_cache()
    except Exception:
        pass
