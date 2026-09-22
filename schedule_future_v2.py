"""MLB verified slate schedule V2 — resilient official MLB fallback.

Keeps schedule_future's strict two-request verification first. If that path
returns empty unexpectedly, retry the official MLB schedule with a simpler
single-date parse. For today's slate only, engine.games_today is a final
same-official-API fallback. No other league/provider can enter the MLB slate.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests
import streamlit as st

import schedule_future as base
from engine import ET, MLB_API, games_today

current_selected_date = base.current_selected_date
render_slate_date_control = base.render_slate_date_control
MAX_FUTURE_DAYS = base.MAX_FUTURE_DAYS

COLUMNS = [
    "game_pk", "game_date", "verified", "venue_name",
    "away_team_id", "away_team", "home_team_id", "home_team",
    "away_pitcher_id", "away_pitcher", "home_pitcher_id", "home_pitcher",
    "first_pitch_et", "status",
]


def _empty():
    return pd.DataFrame(columns=COLUMNS)


def _parse_official_payload(payload, target_date):
    target = base._as_date(target_date)
    day = target.isoformat()
    rows, seen = [], set()
    for block in (payload or {}).get("dates", []) or []:
        if str(block.get("date") or "") != day:
            continue
        for game in block.get("games", []) or []:
            pk = game.get("gamePk")
            if pk is None or int(pk) in seen:
                continue
            try:
                game_time = datetime.fromisoformat(str(game.get("gameDate") or "").replace("Z", "+00:00")).astimezone(ET)
            except Exception:
                continue
            if game_time.date() != target:
                continue
            # MLB schedule endpoint is scoped to sportId=1. Accept regular-season
            # rows and tolerate a missing gameType field rather than deleting a
            # legitimate game from the slate.
            game_type = str(game.get("gameType") or "R").upper()
            if game_type != "R":
                continue
            away = (game.get("teams") or {}).get("away") or {}
            home = (game.get("teams") or {}).get("home") or {}
            away_team = away.get("team") or {}
            home_team = home.get("team") or {}
            if not away_team.get("id") or not home_team.get("id"):
                continue
            ap = away.get("probablePitcher") or {}
            hp = home.get("probablePitcher") or {}
            rows.append({
                "game_pk": int(pk),
                "game_date": day,
                "verified": True,
                "venue_name": (game.get("venue") or {}).get("name", "Unknown"),
                "away_team_id": int(away_team.get("id")),
                "away_team": away_team.get("name", "Unknown"),
                "home_team_id": int(home_team.get("id")),
                "home_team": home_team.get("name", "Unknown"),
                "away_pitcher_id": ap.get("id"),
                "away_pitcher": ap.get("fullName", "TBD"),
                "home_pitcher_id": hp.get("id"),
                "home_pitcher": hp.get("fullName", "TBD"),
                "first_pitch_et": game_time.strftime("%I:%M %p").lstrip("0"),
                "status": (game.get("status") or {}).get("detailedState", "Unknown"),
            })
            seen.add(int(pk))
    out = pd.DataFrame(rows, columns=COLUMNS)
    return out.reset_index(drop=True)


@st.cache_data(ttl=180, show_spinner=False)
def _simple_official_day(target_date):
    target = base._as_date(target_date)
    day = target.isoformat()
    params = {
        "sportId": 1,
        "date": day,
        "hydrate": "probablePitcher,team",
    }
    r = requests.get(f"{MLB_API}/schedule", params=params, timeout=18)
    r.raise_for_status()
    return _parse_official_payload(r.json(), day)


@st.cache_data(ttl=180, show_spinner=False)
def games_for_date(target_date):
    day = base._as_date(target_date).isoformat()
    # 1) Existing strict verified path.
    try:
        strict = base.games_for_date(day)
        if strict is not None and not strict.empty:
            strict = strict.copy()
            strict["verified"] = True
            return strict.reindex(columns=COLUMNS)
    except Exception:
        pass

    # 2) Simpler single-date request to the same official MLB Stats API.
    try:
        simple = _simple_official_day(day)
        if simple is not None and not simple.empty:
            return simple
    except Exception:
        pass

    # 3) Today's engine path also uses the official MLB Stats API and was the
    # original working production route before future-slate verification.
    if day == datetime.now(ET).date().isoformat():
        try:
            today_df, today = games_today()
            if today_df is not None and not today_df.empty and str(today) == day:
                out = today_df.copy()
                out["game_date"] = day
                out["verified"] = True
                for c in COLUMNS:
                    if c not in out.columns:
                        out[c] = None
                return out.reindex(columns=COLUMNS).reset_index(drop=True)
        except Exception:
            pass
    return _empty()


def clear_schedule_cache():
    for fn in (games_for_date, _simple_official_day):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        base.games_for_date.clear()
    except Exception:
        pass
