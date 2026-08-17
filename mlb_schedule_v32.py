"""MLB Schedule V3.2 — MLB-only independent recovery + diagnostics.

This file is intentionally isolated from WNBA. It bypasses the older slate bootstrap
and can load a selected MLB date directly. Primary source is the official MLB Stats
API. ESPN MLB is a schedule-only rescue source. urllib is used as an additional
transport path so a requests-specific failure does not collapse the slate.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import requests
import streamlit as st

from engine import ET, MLB_API
import mlb_schedule_v31 as legacy31

current_selected_date = legacy31.current_selected_date
render_slate_date_control = legacy31.render_slate_date_control
MAX_FUTURE_DAYS = legacy31.MAX_FUTURE_DAYS

COLUMNS = legacy31.COLUMNS
ESPN = legacy31.base.ESPN_MLB_SCOREBOARD
MLB_TEAM_IDS = legacy31.base.MLB_TEAM_IDS
MLB_IDS = legacy31.base.MLB_IDS
NAME_IDS = legacy31.base.NAME_IDS


def _empty():
    return pd.DataFrame(columns=COLUMNS)


def _day(value):
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception:
        return str(value)[:10]


def _first_pitch(raw):
    try:
        return pd.to_datetime(raw, utc=True).tz_convert(ET).strftime("%I:%M %p").lstrip("0")
    except Exception:
        return "TBD"


def _urllib_json(url, params, timeout=18):
    full = url + ("?" + urlencode(params, doseq=True) if params else "")
    req = Request(full, headers={
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Cache-Control": "no-cache",
    })
    with urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw.decode("utf-8")), {"http": getattr(r, "status", 200), "bytes": len(raw), "url": full}


def _team_id_espn(team):
    team = team or {}
    abbr = str(team.get("abbreviation") or "").upper().strip()
    name = str(team.get("displayName") or team.get("shortDisplayName") or "").strip()
    return MLB_IDS.get(abbr) or NAME_IDS.get(name)


def _synthetic(event_id):
    text = str(event_id or "")
    if text.isdigit():
        return -int(text[-9:])
    return -int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)


def _parse_mlb(payload, target_day):
    target_day = _day(target_day)
    rows = []
    seen = set()
    for block in (payload or {}).get("dates", []) or []:
        block_day = str(block.get("date") or "")[:10]
        for g in block.get("games", []) or []:
            official_day = str(g.get("officialDate") or block_day)[:10]
            if official_day != target_day:
                continue
            try:
                pk = int(g.get("gamePk"))
            except Exception:
                continue
            if pk in seen:
                continue
            teams = g.get("teams") or {}
            away = teams.get("away") or {}
            home = teams.get("home") or {}
            at = away.get("team") or {}
            ht = home.get("team") or {}
            try:
                aid, hid = int(at.get("id")), int(ht.get("id"))
            except Exception:
                continue
            if aid not in MLB_TEAM_IDS or hid not in MLB_TEAM_IDS:
                continue
            ap = away.get("probablePitcher") or {}
            hp = home.get("probablePitcher") or {}
            rows.append({
                "game_pk": pk,
                "game_date": target_day,
                "verified": True,
                "venue_name": str((g.get("venue") or {}).get("name") or "Venue TBD"),
                "away_team_id": aid,
                "away_team": str(at.get("name") or "Away"),
                "home_team_id": hid,
                "home_team": str(ht.get("name") or "Home"),
                "away_pitcher_id": ap.get("id"),
                "away_pitcher": str(ap.get("fullName") or "TBD"),
                "home_pitcher_id": hp.get("id"),
                "home_pitcher": str(hp.get("fullName") or "TBD"),
                "first_pitch_et": _first_pitch(g.get("gameDate")),
                "status": str((g.get("status") or {}).get("detailedState") or "Scheduled"),
                "schedule_source": "MLB Stats API V3.2",
                "external_game_id": "",
            })
            seen.add(pk)
    return pd.DataFrame(rows, columns=COLUMNS) if rows else _empty()


def _parse_espn(payload, target_day):
    target_day = _day(target_day)
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
        ac, hc = sides.get("away") or {}, sides.get("home") or {}
        at, ht = ac.get("team") or {}, hc.get("team") or {}
        aid, hid = _team_id_espn(at), _team_id_espn(ht)
        if aid not in MLB_TEAM_IDS or hid not in MLB_TEAM_IDS:
            continue
        status = ((event.get("status") or {}).get("type") or {})
        eid = str(event.get("id") or "")
        rows.append({
            "game_pk": _synthetic(eid),
            "game_date": target_day,
            "verified": True,
            "venue_name": str((comp.get("venue") or {}).get("fullName") or "Venue TBD"),
            "away_team_id": int(aid),
            "away_team": str(at.get("displayName") or at.get("shortDisplayName") or "Away"),
            "home_team_id": int(hid),
            "home_team": str(ht.get("displayName") or ht.get("shortDisplayName") or "Home"),
            "away_pitcher_id": None,
            "away_pitcher": "TBD",
            "home_pitcher_id": None,
            "home_pitcher": "TBD",
            "first_pitch_et": _first_pitch(event.get("date") or comp.get("date")),
            "status": str(status.get("description") or status.get("detail") or status.get("shortDetail") or "Scheduled"),
            "schedule_source": "ESPN MLB V3.2 recovery",
            "external_game_id": eid,
        })
    if not rows:
        return _empty()
    return pd.DataFrame(rows, columns=COLUMNS).drop_duplicates(
        subset=["away_team_id", "home_team_id", "first_pitch_et"], keep="first"
    ).reset_index(drop=True)


@st.cache_data(ttl=45, show_spinner=False)
def load_with_diagnostics(target_date):
    day = _day(target_date)
    stamp = pd.Timestamp.utcnow().strftime("%Y%m%d%H%M%S")
    attempts = []

    # 1. Official MLB via requests.
    params = {"sportId": 1, "date": day, "hydrate": "probablePitcher,team,venue", "_": stamp}
    try:
        r = requests.get(f"{MLB_API}/schedule", params=params, timeout=18, headers={"User-Agent":"KyreSportsAI/3.2","Accept":"application/json"})
        meta = {"provider":"MLB requests", "http":int(r.status_code), "bytes":len(r.content or b""), "error":""}
        r.raise_for_status()
        frame = _parse_mlb(r.json(), day)
        meta["games"] = len(frame); attempts.append(meta)
        if not frame.empty:
            return frame.reset_index(drop=True), {"version":"V3.2","date":day,"source":"MLB Stats API requests","games":len(frame),"attempts":attempts}
    except Exception as exc:
        attempts.append({"provider":"MLB requests","http":None,"bytes":0,"games":0,"error":f"{type(exc).__name__}: {exc}"[:240]})

    # 2. Official MLB via urllib transport.
    try:
        payload, wire = _urllib_json(f"{MLB_API}/schedule", {"sportId":1,"date":day,"hydrate":"probablePitcher,team,venue","_":stamp})
        frame = _parse_mlb(payload, day)
        attempts.append({"provider":"MLB urllib","http":wire.get("http"),"bytes":wire.get("bytes"),"games":len(frame),"error":""})
        if not frame.empty:
            return frame.reset_index(drop=True), {"version":"V3.2","date":day,"source":"MLB Stats API urllib","games":len(frame),"attempts":attempts}
    except Exception as exc:
        attempts.append({"provider":"MLB urllib","http":None,"bytes":0,"games":0,"error":f"{type(exc).__name__}: {exc}"[:240]})

    # 3. ESPN date-scoped via requests. Request date is authoritative for rescue.
    eparams = {"dates": pd.to_datetime(day).strftime("%Y%m%d"), "limit": 200, "_": stamp}
    try:
        r = requests.get(ESPN, params=eparams, timeout=18, headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
        meta = {"provider":"ESPN requests", "http":int(r.status_code), "bytes":len(r.content or b""), "error":""}
        r.raise_for_status()
        frame = _parse_espn(r.json(), day)
        meta["games"] = len(frame); attempts.append(meta)
        if not frame.empty:
            return frame.reset_index(drop=True), {"version":"V3.2","date":day,"source":"ESPN MLB requests recovery","games":len(frame),"attempts":attempts}
    except Exception as exc:
        attempts.append({"provider":"ESPN requests","http":None,"bytes":0,"games":0,"error":f"{type(exc).__name__}: {exc}"[:240]})

    # 4. ESPN via urllib.
    try:
        payload, wire = _urllib_json(ESPN, eparams)
        frame = _parse_espn(payload, day)
        attempts.append({"provider":"ESPN urllib","http":wire.get("http"),"bytes":wire.get("bytes"),"games":len(frame),"error":""})
        if not frame.empty:
            return frame.reset_index(drop=True), {"version":"V3.2","date":day,"source":"ESPN MLB urllib recovery","games":len(frame),"attempts":attempts}
    except Exception as exc:
        attempts.append({"provider":"ESPN urllib","http":None,"bytes":0,"games":0,"error":f"{type(exc).__name__}: {exc}"[:240]})

    return _empty(), {"version":"V3.2","date":day,"source":"none","games":0,"attempts":attempts}


@st.cache_data(ttl=45, show_spinner=False)
def games_for_date(target_date):
    frame, _ = load_with_diagnostics(target_date)
    return frame


def schedule_diagnostics(target_date):
    _, diag = load_with_diagnostics(target_date)
    return diag


def clear_schedule_cache():
    for fn in (games_for_date, load_with_diagnostics):
        try: fn.clear()
        except Exception: pass
