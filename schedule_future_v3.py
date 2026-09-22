"""MLB isolated schedule recovery — official-first, multi-path verification.

This module is MLB-only. It intentionally does not import or modify any WNBA
module. The app can keep importing schedule_future_v3 while this implementation
hardens the MLB slate path.

Priority:
1) MLB Stats API exact-date schedule.
2) MLB Stats API start/end-date schedule.
3) MLB Stats API season schedule filtered to the selected official date.
4) ESPN MLB selected-date scoreboard (schedule-only recovery).
5) ESPN MLB season scoreboard filtered to the selected date.

Official MLB rows keep their real gamePk. ESPN rescue rows use negative synthetic
keys and are clearly tagged; they are never presented as MLB gamePk values.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

import schedule_future_v2 as legacy
from engine import ET, MLB_API

current_selected_date = legacy.current_selected_date
render_slate_date_control = legacy.render_slate_date_control
MAX_FUTURE_DAYS = legacy.MAX_FUTURE_DAYS

COLUMNS = [
    "game_pk", "game_date", "verified", "venue_name",
    "away_team_id", "away_team", "home_team_id", "home_team",
    "away_pitcher_id", "away_pitcher", "home_pitcher_id", "home_pitcher",
    "first_pitch_et", "status", "schedule_source", "external_game_id",
]

ESPN_MLB_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"

MLB_TEAM_IDS = {
    108,109,110,111,112,113,114,115,116,117,118,119,120,121,133,134,
    135,136,137,138,139,140,141,142,143,144,145,146,147,158,
}

MLB_IDS = {
    "ARI":109,"ATL":144,"BAL":110,"BOS":111,"CHC":112,"CHW":145,
    "CWS":145,"CIN":113,"CLE":114,"COL":115,"DET":116,"HOU":117,
    "KC":118,"KCR":118,"LAA":108,"LAD":119,"MIA":146,"MIL":158,
    "MIN":142,"NYM":121,"NYY":147,"ATH":133,"OAK":133,"PHI":143,
    "PIT":134,"SD":135,"SDP":135,"SEA":136,"SF":137,"SFG":137,
    "STL":138,"TB":139,"TBR":139,"TEX":140,"TOR":141,"WSH":120,
    "WSN":120,
}

NAME_IDS = {
    "Arizona Diamondbacks":109,"Atlanta Braves":144,"Baltimore Orioles":110,
    "Boston Red Sox":111,"Chicago Cubs":112,"Chicago White Sox":145,
    "Cincinnati Reds":113,"Cleveland Guardians":114,"Colorado Rockies":115,
    "Detroit Tigers":116,"Houston Astros":117,"Kansas City Royals":118,
    "Los Angeles Angels":108,"Los Angeles Dodgers":119,"Miami Marlins":146,
    "Milwaukee Brewers":158,"Minnesota Twins":142,"New York Mets":121,
    "New York Yankees":147,"Athletics":133,"Oakland Athletics":133,
    "Philadelphia Phillies":143,"Pittsburgh Pirates":134,"San Diego Padres":135,
    "Seattle Mariners":136,"San Francisco Giants":137,"St. Louis Cardinals":138,
    "Tampa Bay Rays":139,"Texas Rangers":140,"Toronto Blue Jays":141,
    "Washington Nationals":120,
}


def _as_date(value):
    return legacy.base._as_date(value)


def _empty():
    return pd.DataFrame(columns=COLUMNS)


def _request_json(provider, url, *, params=None, timeout=12, attempts=2):
    meta = {
        "provider": provider, "host": urlparse(url).netloc, "http": None,
        "json": False, "bytes": 0, "error": "", "request_ok": False,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    last = None
    for n in range(max(1, int(attempts))):
        try:
            call_params = dict(params or {})
            if n:
                call_params["_"] = pd.Timestamp.utcnow().strftime("%Y%m%d%H%M%S")
            r = requests.get(url, params=call_params or None, headers=headers, timeout=timeout)
            meta["http"] = int(r.status_code)
            meta["bytes"] = len(r.content or b"")
            r.raise_for_status()
            text = (r.text or "").lstrip()
            if not text.startswith(("{", "[")):
                raise ValueError("empty/non-JSON response")
            payload = r.json()
            meta["json"] = True
            meta["request_ok"] = True
            return payload, meta
        except Exception as exc:
            last = exc
    meta["error"] = f"{type(last).__name__}: {last}"[:220] if last else "request failed"
    return None, meta


def _official_game_date(game, block_date=""):
    # officialDate is the authoritative MLB calendar date for slate membership.
    value = str(game.get("officialDate") or block_date or "")
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return value[:10]


def _first_pitch_et(raw):
    try:
        ts = pd.to_datetime(raw, utc=True).tz_convert(ET)
        return ts.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return "TBD"


def _parse_official(payload, day):
    day = _as_date(day).isoformat()
    rows, seen = [], set()
    for block in (payload or {}).get("dates", []) or []:
        block_date = str(block.get("date") or "")
        for game in block.get("games", []) or []:
            pk = game.get("gamePk")
            if pk is None:
                continue
            try:
                pk = int(pk)
            except Exception:
                continue
            if pk in seen:
                continue
            if _official_game_date(game, block_date) != day:
                continue
            game_type = str(game.get("gameType") or "R").upper()
            if game_type != "R":
                continue
            teams = game.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}
            away_team = away.get("team") or {}
            home_team = home.get("team") or {}
            try:
                away_id = int(away_team.get("id"))
                home_id = int(home_team.get("id"))
            except Exception:
                continue
            if away_id not in MLB_TEAM_IDS or home_id not in MLB_TEAM_IDS or away_id == home_id:
                continue
            ap = away.get("probablePitcher") or {}
            hp = home.get("probablePitcher") or {}
            rows.append({
                "game_pk": pk,
                "game_date": day,
                "verified": True,
                "venue_name": str((game.get("venue") or {}).get("name") or "Venue TBD"),
                "away_team_id": away_id,
                "away_team": str(away_team.get("name") or "Away"),
                "home_team_id": home_id,
                "home_team": str(home_team.get("name") or "Home"),
                "away_pitcher_id": ap.get("id"),
                "away_pitcher": str(ap.get("fullName") or "TBD"),
                "home_pitcher_id": hp.get("id"),
                "home_pitcher": str(hp.get("fullName") or "TBD"),
                "first_pitch_et": _first_pitch_et(game.get("gameDate")),
                "status": str((game.get("status") or {}).get("detailedState") or "Scheduled"),
                "schedule_source": "MLB Stats API",
                "external_game_id": "",
            })
            seen.add(pk)
    return pd.DataFrame(rows, columns=COLUMNS)


def _espn_team_id(team):
    team = team or {}
    abbr = str(team.get("abbreviation") or "").upper().strip()
    name = str(team.get("displayName") or team.get("shortDisplayName") or "").strip()
    return MLB_IDS.get(abbr) or NAME_IDS.get(name)


def _synthetic_pk(event_id):
    text = str(event_id or "")
    if text.isdigit():
        return -int(text[-9:])
    return -int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)


def _espn_probable(comp):
    for p in (comp or {}).get("probables") or []:
        athlete = p.get("athlete") if isinstance(p, dict) else None
        if isinstance(athlete, dict):
            pid = athlete.get("id")
            return (int(pid) if str(pid or "").isdigit() else None,
                    str(athlete.get("displayName") or athlete.get("fullName") or "TBD"))
    return None, "TBD"


def _parse_espn(payload, day, source):
    day = _as_date(day).isoformat()
    rows = []
    for event in (payload or {}).get("events", []) or []:
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
        away_id, home_id = _espn_team_id(away_t), _espn_team_id(home_t)
        if away_id not in MLB_TEAM_IDS or home_id not in MLB_TEAM_IDS:
            continue
        raw_dt = event.get("date") or comp.get("date")
        try:
            event_day = pd.to_datetime(raw_dt, utc=True).tz_convert(ET).strftime("%Y-%m-%d")
        except Exception:
            event_day = ""
        if event_day != day:
            continue
        apid, ap = _espn_probable(away_c)
        hpid, hp = _espn_probable(home_c)
        status = ((event.get("status") or {}).get("type") or {})
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
            "away_pitcher_id": apid,
            "away_pitcher": ap,
            "home_pitcher_id": hpid,
            "home_pitcher": hp,
            "first_pitch_et": _first_pitch_et(raw_dt),
            "status": str(status.get("description") or status.get("detail") or status.get("shortDetail") or "Scheduled"),
            "schedule_source": source,
            "external_game_id": eid,
        })
    if not rows:
        return _empty()
    out = pd.DataFrame(rows, columns=COLUMNS)
    return out.drop_duplicates(subset=["away_team_id","home_team_id","first_pitch_et"], keep="first").reset_index(drop=True)


def _choose(candidates):
    for priority, frame, source in sorted(candidates, key=lambda x: x[0]):
        if frame is not None and not frame.empty:
            out = frame.copy()
            if "schedule_source" not in out.columns:
                out["schedule_source"] = source
            out["verified"] = True
            return out.reindex(columns=COLUMNS).reset_index(drop=True), source
    return _empty(), "none"


@st.cache_data(ttl=120, show_spinner=False)
def _verified_schedule(day):
    day = _as_date(day).isoformat()
    year = pd.to_datetime(day).year
    candidates = []
    attempts = []

    official_calls = [
        (0, "MLB exact date", {"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue"}),
        (1, "MLB date range", {"sportId":1,"startDate":day,"endDate":day,"hydrate":"probablePitcher,team,venue"}),
        (2, "MLB season", {"sportId":1,"season":year,"gameTypes":"R","hydrate":"probablePitcher,team,venue"}),
    ]
    for priority, provider, params in official_calls:
        payload, meta = _request_json(provider, f"{MLB_API}/schedule", params=params, timeout=15 if priority < 2 else 22, attempts=2)
        frame = _parse_official(payload, day) if payload is not None else _empty()
        meta["selected_games"] = int(len(frame))
        attempts.append(meta)
        if not frame.empty:
            frame = frame.copy()
            frame["schedule_source"] = provider
            candidates.append((priority, frame, provider))
            # Exact-date official data is enough; avoid the heavy season call when possible.
            if priority == 0:
                break

    # If exact official worked, choose now. Otherwise add ESPN recovery paths.
    if candidates and candidates[0][0] == 0:
        chosen, source = _choose(candidates)
        return chosen, {"date":day,"state":"VERIFIED","source":source,"games":len(chosen),"attempts":attempts}

    espn_calls = [
        (3, "ESPN MLB daily recovery", {"dates":pd.to_datetime(day).strftime("%Y%m%d"),"limit":100}),
        (4, "ESPN MLB season recovery", {"dates":str(year),"limit":1000}),
    ]
    for priority, provider, params in espn_calls:
        payload, meta = _request_json(provider, ESPN_MLB_SCOREBOARD, params=params, timeout=12, attempts=2)
        frame = _parse_espn(payload, day, provider) if payload is not None else _empty()
        meta["selected_games"] = int(len(frame))
        attempts.append(meta)
        if not frame.empty:
            candidates.append((priority, frame, provider))

    chosen, source = _choose(candidates)
    state = "VERIFIED" if not chosen.empty else "PROVIDER_FAILURE"
    return chosen, {"date":day,"state":state,"source":source,"games":int(len(chosen)),"attempts":attempts}


@st.cache_data(ttl=120, show_spinner=False)
def games_for_date(target_date):
    frame, _ = _verified_schedule(_as_date(target_date).isoformat())
    return frame


def schedule_diagnostics(target_date):
    _, diag = _verified_schedule(_as_date(target_date).isoformat())
    return diag


def clear_schedule_cache():
    for fn in (games_for_date, _verified_schedule):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        legacy.clear_schedule_cache()
    except Exception:
        pass
