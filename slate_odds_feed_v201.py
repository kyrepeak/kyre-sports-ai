"""Pregame + live sportsbook snapshots for the MLB Slate command center.

This module keeps the existing live odds feed untouched and adds date-scoped
prematch event discovery for the selected verified MLB slate. Event matching is
team-name based and, when there are doubleheaders, prefers the odds event whose
start time is closest to MLB's verified first pitch.
"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from live_odds_feed import ODDS_BASE, fetch_multi_odds, parse_event_odds, _same_team

ET = ZoneInfo("America/New_York")


def _event_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("data")
        return rows if isinstance(rows, list) else []
    return []


@st.cache_data(ttl=120, show_spinner=False)
def fetch_mlb_events(api_key, start_iso, end_iso):
    """Fetch pending + live MLB events for a narrow UTC window."""
    params = {
        "apiKey": str(api_key),
        "sport": "baseball",
        "league": "usa-mlb",
        "status": "pending,live",
        "from": str(start_iso),
        "to": str(end_iso),
    }
    response = requests.get(f"{ODDS_BASE}/events", params=params, timeout=15)

    # Some account/config combinations may not accept the league filter even
    # though baseball events are available. Fall back to sport-only discovery.
    if response.status_code >= 400:
        params.pop("league", None)
        response = requests.get(f"{ODDS_BASE}/events", params=params, timeout=15)

    response.raise_for_status()
    return _event_list(response.json())


def _parse_day(value):
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _window_for_games(games_df):
    days = [_parse_day(x) for x in games_df.get("game_date", pd.Series(dtype=str)).dropna().tolist()]
    days = [x for x in days if x is not None]
    if not days:
        today = datetime.now(ET).date()
        days = [today]

    start_local = datetime.combine(min(days), time.min, tzinfo=ET)
    end_local = datetime.combine(max(days) + timedelta(days=1), time.min, tzinfo=ET)
    return (
        start_local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        end_local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


def _target_start(row):
    try:
        d = date.fromisoformat(str(row.get("game_date")))
        t = datetime.strptime(str(row.get("first_pitch_et")), "%I:%M %p").time()
        return datetime.combine(d, t, tzinfo=ET).astimezone(timezone.utc)
    except Exception:
        return None


def _event_dt(event):
    value = (event or {}).get("date")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _match_event(events, row):
    away = row.get("away_team")
    home = row.get("home_team")
    target = _target_start(row)

    exact = []
    reverse = []
    for event in events or []:
        if _same_team(event.get("away"), away) and _same_team(event.get("home"), home):
            exact.append(event)
        elif _same_team(event.get("away"), home) and _same_team(event.get("home"), away):
            reverse.append(event)

    candidates = exact or reverse
    if not candidates:
        return None
    if len(candidates) == 1 or target is None:
        return candidates[0]

    def distance(event):
        dt = _event_dt(event)
        return abs((dt - target).total_seconds()) if dt is not None else 10**12

    return min(candidates, key=distance)


def slate_snapshots_for_games(games_df, api_key, bookmakers):
    """Return pregame/live odds snapshots keyed by MLB gamePk."""
    if not api_key or games_df is None or getattr(games_df, "empty", True):
        return {}

    start_iso, end_iso = _window_for_games(games_df)
    events = fetch_mlb_events(api_key, start_iso, end_iso)

    matches = {}
    event_ids = []
    for _, row in games_df.iterrows():
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        event = _match_event(events, row)
        if not event or event.get("id") is None:
            continue
        matches[pk] = event
        event_ids.append(event.get("id"))

    if not event_ids:
        return {}

    odds_payloads = fetch_multi_odds(api_key, tuple(event_ids), bookmakers)
    by_id = {
        str(x.get("id")): x
        for x in odds_payloads
        if isinstance(x, dict) and x.get("id") is not None
    }

    out = {}
    for pk, event in matches.items():
        payload = by_id.get(str(event.get("id")))
        if not payload:
            continue
        parsed = parse_event_odds(payload)
        parsed["event"] = event
        parsed["event_status"] = event.get("status")
        parsed["event_date"] = event.get("date")
        out[pk] = parsed
    return out
