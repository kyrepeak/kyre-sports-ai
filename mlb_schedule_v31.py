"""MLB Schedule V3.1 — isolated fresh-import recovery path.

MLB ONLY. This module does not import or modify any WNBA package.

Purpose:
- Force Streamlit to load a new module name after schedule hotfixes.
- Keep the V3 official-first verifier as primary.
- If V3 is empty, retry ESPN's date-scoped MLB scoreboard without applying a
  second timezone/date rejection. Because the request itself is scoped to the
  selected YYYYMMDD, returned MLB events are accepted for that slate.
- Preserve real MLB gamePk values when official MLB data is available.
- ESPN rescue rows use negative synthetic keys and are labeled as recovery data.
"""
from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

import schedule_future_v3 as base

current_selected_date = base.current_selected_date
render_slate_date_control = base.render_slate_date_control
MAX_FUTURE_DAYS = base.MAX_FUTURE_DAYS
COLUMNS = base.COLUMNS


def _empty():
    return pd.DataFrame(columns=COLUMNS)


@st.cache_data(ttl=60, show_spinner=False)
def _espn_date_scoped_recovery(target_date):
    day = base._as_date(target_date).isoformat()
    params = {
        "dates": pd.to_datetime(day).strftime("%Y%m%d"),
        "limit": 200,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Cache-Control": "no-cache",
    }
    response = requests.get(base.ESPN_MLB_SCOREBOARD, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    payload = response.json()

    rows = []
    for event in payload.get("events", []) or []:
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        comp = competitions[0]
        sides = {}
        for competitor in comp.get("competitors", []) or []:
            if isinstance(competitor, dict):
                sides[str(competitor.get("homeAway") or "").lower()] = competitor

        away_c = sides.get("away") or {}
        home_c = sides.get("home") or {}
        away_t = away_c.get("team") or {}
        home_t = home_c.get("team") or {}
        away_id = base._espn_team_id(away_t)
        home_id = base._espn_team_id(home_t)
        if away_id not in base.MLB_TEAM_IDS or home_id not in base.MLB_TEAM_IDS:
            continue

        raw_dt = event.get("date") or comp.get("date")
        apid, ap = base._espn_probable(away_c)
        hpid, hp = base._espn_probable(home_c)
        status = ((event.get("status") or {}).get("type") or {})
        eid = str(event.get("id") or "")

        rows.append({
            "game_pk": base._synthetic_pk(eid),
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
            "first_pitch_et": base._first_pitch_et(raw_dt),
            "status": str(status.get("description") or status.get("detail") or status.get("shortDetail") or "Scheduled"),
            "schedule_source": "ESPN MLB date-scoped recovery",
            "external_game_id": eid,
        })

    if not rows:
        return _empty()
    out = pd.DataFrame(rows, columns=COLUMNS)
    out = out.drop_duplicates(subset=["away_team_id", "home_team_id", "first_pitch_et"], keep="first")
    return out.reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False)
def games_for_date(target_date):
    day = base._as_date(target_date).isoformat()

    # Primary: V3's official-first multi-path verifier.
    try:
        official_first = base.games_for_date(day)
        if official_first is not None and not official_first.empty:
            return official_first.reindex(columns=COLUMNS).reset_index(drop=True)
    except Exception:
        pass

    # Recovery: the ESPN request is already scoped to YYYYMMDD. Do not reject
    # returned events a second time because of UTC/ET conversion edge cases.
    try:
        recovered = _espn_date_scoped_recovery(day)
        if recovered is not None and not recovered.empty:
            return recovered.reindex(columns=COLUMNS).reset_index(drop=True)
    except Exception:
        pass

    return _empty()


def schedule_diagnostics(target_date):
    day = base._as_date(target_date).isoformat()
    details = {
        "date": day,
        "version": "MLB Schedule V3.1",
        "games": 0,
        "source": "none",
    }
    try:
        _, diag = base._verified_schedule(day)
        details["v3"] = diag
        if int((diag or {}).get("games") or 0) > 0:
            details["games"] = int(diag.get("games") or 0)
            details["source"] = str(diag.get("source") or "MLB V3")
            return details
    except Exception as exc:
        details["v3_error"] = f"{type(exc).__name__}: {exc}"[:220]

    try:
        recovered = _espn_date_scoped_recovery(day)
        details["espn_date_scoped_games"] = int(len(recovered))
        if not recovered.empty:
            details["games"] = int(len(recovered))
            details["source"] = "ESPN MLB date-scoped recovery"
    except Exception as exc:
        details["espn_error"] = f"{type(exc).__name__}: {exc}"[:220]
    return details


def clear_schedule_cache():
    for fn in (games_for_date, _espn_date_scoped_recovery):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        base.clear_schedule_cache()
    except Exception:
        pass
