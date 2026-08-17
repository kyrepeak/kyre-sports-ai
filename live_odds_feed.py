"""Live sportsbook market feed for Kyre Sports AI.

Uses Odds-API.io when an API key is supplied through Streamlit secrets,
environment variables, or a temporary per-session password field. The free
plan can cover live MLB moneyline, spread and total markets from two selected
recreational books, so this module deliberately polls conservatively.
"""

from datetime import datetime, timezone
import math
import os
import re

import numpy as np
import pandas as pd
import requests
import streamlit as st

ODDS_BASE = "https://api.odds-api.io/v3"
DEFAULT_BOOKMAKERS = "FanDuel,DraftKings"


def _secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def get_api_key():
    return (
        st.session_state.get("ks_odds_api_key")
        or _secret("ODDS_API_IO_KEY")
        or os.getenv("ODDS_API_IO_KEY")
        or os.getenv("ODDS_API_KEY")
    )


def get_bookmakers():
    value = (
        st.session_state.get("ks_odds_bookmakers")
        or _secret("ODDS_BOOKMAKERS")
        or os.getenv("ODDS_BOOKMAKERS")
        or DEFAULT_BOOKMAKERS
    )
    return ",".join([x.strip() for x in str(value).split(",") if x.strip()][:2]) or DEFAULT_BOOKMAKERS


def render_connection_setup(prefix="live_odds"):
    key = get_api_key()
    if key:
        return key

    st.info(
        "📡 Live sportsbook prices are ready to connect. Add a free Odds-API.io key to pull live MLB moneyline, spread and total prices. "
        "The model itself still works without the key."
    )
    with st.expander("🔑 Connect free live odds", expanded=False):
        temp_key = st.text_input(
            "Odds-API.io API key",
            type="password",
            key=f"{prefix}_key_input",
            help="Stored only in this Streamlit session unless you later add it to Streamlit Secrets.",
        )
        books = st.text_input(
            "Two sportsbooks",
            value=DEFAULT_BOOKMAKERS,
            key=f"{prefix}_books_input",
            help="Free accounts can select two recreational books. Example: FanDuel,DraftKings",
        )
        if st.button("CONNECT LIVE ODDS", use_container_width=True, key=f"{prefix}_connect"):
            if temp_key.strip():
                st.session_state["ks_odds_api_key"] = temp_key.strip()
                st.session_state["ks_odds_bookmakers"] = books.strip() or DEFAULT_BOOKMAKERS
                st.rerun()
            else:
                st.warning("Paste the API key first.")
    return None


def _norm(value):
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    aliases = {
        "oakland athletics": "athletics",
        "the athletics": "athletics",
    }
    return aliases.get(text, text)


def _same_team(a, b):
    aa, bb = _norm(a), _norm(b)
    return aa == bb or (aa and bb and (aa in bb or bb in aa))


def _event_match(events, away, home):
    exact = []
    reverse = []
    for event in events or []:
        if _same_team(event.get("away"), away) and _same_team(event.get("home"), home):
            exact.append(event)
        elif _same_team(event.get("away"), home) and _same_team(event.get("home"), away):
            reverse.append(event)
    return exact[0] if exact else reverse[0] if reverse else None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_events(api_key):
    response = requests.get(
        f"{ODDS_BASE}/events/live",
        params={"apiKey": str(api_key)},
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []


@st.cache_data(ttl=55, show_spinner=False)
def fetch_multi_odds(api_key, event_ids, bookmakers):
    ids = [str(x) for x in event_ids if x is not None]
    if not ids:
        return []
    all_rows = []
    for start in range(0, len(ids), 10):
        chunk = ids[start:start + 10]
        response = requests.get(
            f"{ODDS_BASE}/odds/multi",
            params={
                "apiKey": str(api_key),
                "eventIds": ",".join(chunk),
                "bookmakers": str(bookmakers),
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            all_rows.extend(payload)
        elif isinstance(payload, dict):
            rows = payload.get("data")
            if isinstance(rows, list):
                all_rows.extend(rows)
            elif payload.get("id") is not None:
                all_rows.append(payload)
    return all_rows


def decimal_to_american(value):
    try:
        d = float(value)
    except Exception:
        return None
    if d <= 1.0:
        return None
    if d >= 2.0:
        return int(round((d - 1.0) * 100))
    return int(round(-100.0 / (d - 1.0)))


def _iso_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _age_seconds(value):
    dt = _iso_dt(value)
    if dt is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))


def _first_odds(market):
    odds = (market or {}).get("odds") or []
    return odds[0] if odds and isinstance(odds[0], dict) else {}


def parse_event_odds(payload):
    rows = []
    bookmakers = payload.get("bookmakers") or {}
    if not isinstance(bookmakers, dict):
        return {"rows": [], "home_spread": None, "total_line": None}

    for book, markets in bookmakers.items():
        item = {
            "Book": str(book),
            "Away ML": None,
            "Home ML": None,
            "Away RL": None,
            "Home RL": None,
            "Over": None,
            "Under": None,
            "updatedAt": None,
        }
        home_hdp = None
        total_line = None
        newest = None
        for market in markets or []:
            name = str((market or {}).get("name", "")).strip().lower()
            odds0 = _first_odds(market)
            updated = (market or {}).get("updatedAt")
            if updated:
                dt = _iso_dt(updated)
                if dt and (newest is None or dt > newest):
                    newest = dt
                    item["updatedAt"] = updated
            if name == "ml":
                item["Away ML"] = decimal_to_american(odds0.get("away"))
                item["Home ML"] = decimal_to_american(odds0.get("home"))
            elif name == "spread":
                try:
                    home_hdp = float(odds0.get("hdp"))
                except Exception:
                    home_hdp = None
                if home_hdp is not None:
                    away_line = -home_hdp
                    item["Away RL"] = f"{away_line:+g} ({_fmt_american(decimal_to_american(odds0.get('away')))})"
                    item["Home RL"] = f"{home_hdp:+g} ({_fmt_american(decimal_to_american(odds0.get('home')))})"
            elif name == "totals":
                try:
                    total_line = float(odds0.get("max"))
                except Exception:
                    total_line = None
                if total_line is not None:
                    item["Over"] = f"O {total_line:g} ({_fmt_american(decimal_to_american(odds0.get('over')))})"
                    item["Under"] = f"U {total_line:g} ({_fmt_american(decimal_to_american(odds0.get('under')))})"
        item["home_hdp"] = home_hdp
        item["total_line"] = total_line
        item["age_seconds"] = _age_seconds(item.get("updatedAt"))
        rows.append(item)

    home_spreads = [r["home_hdp"] for r in rows if r.get("home_hdp") is not None]
    totals = [r["total_line"] for r in rows if r.get("total_line") is not None]
    return {
        "rows": rows,
        "home_spread": float(np.median(home_spreads)) if home_spreads else None,
        "total_line": float(np.median(totals)) if totals else None,
        "away": payload.get("away"),
        "home": payload.get("home"),
        "event_id": payload.get("id"),
    }


def _fmt_american(value):
    if value is None:
        return "—"
    return f"{int(value):+d}"


def snapshots_for_games(games_df, api_key=None, bookmakers=None):
    key = api_key or get_api_key()
    if not key or games_df is None or getattr(games_df, "empty", True):
        return {}
    books = bookmakers or get_bookmakers()
    events = fetch_live_events(key)

    matches = {}
    event_ids = []
    for _, row in games_df.iterrows():
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        event = _event_match(events, row.get("away_team"), row.get("home_team"))
        if not event:
            continue
        eid = event.get("id")
        if eid is None:
            continue
        matches[pk] = event
        event_ids.append(eid)

    if not event_ids:
        return {}
    odds_rows = fetch_multi_odds(key, tuple(event_ids), books)
    by_id = {str(x.get("id")): x for x in odds_rows if isinstance(x, dict) and x.get("id") is not None}

    out = {}
    for pk, event in matches.items():
        payload = by_id.get(str(event.get("id")))
        if payload:
            parsed = parse_event_odds(payload)
            parsed["event"] = event
            out[pk] = parsed
    return out


def render_snapshot(snapshot, title="📈 Live Sportsbook Market", compact=False):
    if not snapshot:
        st.warning("Live game found, but current sportsbook markets were not returned by the selected books.")
        return
    rows = snapshot.get("rows") or []
    if not rows:
        st.warning("The selected sportsbooks do not currently have usable live ML / spread / total markets for this game.")
        return

    ages = [r.get("age_seconds") for r in rows if r.get("age_seconds") is not None]
    freshest = min(ages) if ages else None
    age_text = f"{freshest}s old" if freshest is not None else "timestamp unavailable"
    st.markdown(f"### {title}")
    st.caption(f"Auto-polls about once per minute on the free-data configuration • {get_bookmakers()} • freshest quote {age_text}")

    display = []
    for r in rows:
        display.append({
            "Book": r.get("Book"),
            "Away ML": _fmt_american(r.get("Away ML")),
            "Home ML": _fmt_american(r.get("Home ML")),
            "Away RL": r.get("Away RL") or "—",
            "Home RL": r.get("Home RL") or "—",
            "Over": r.get("Over") or "—",
            "Under": r.get("Under") or "—",
            "Age": f"{r.get('age_seconds')}s" if r.get("age_seconds") is not None else "—",
        })
    st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)


def render_live_slate_board(games_df, title="📈 Live Sportsbook Odds"):
    key = render_connection_setup("slate_odds")
    if not key:
        return {}
    try:
        snaps = snapshots_for_games(games_df, key, get_bookmakers())
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status in {401, 403}:
            st.error("Live odds API rejected the key or selected bookmakers. Check the free Odds-API.io account settings.")
        elif status == 429:
            st.warning("Live odds quota is temporarily exhausted. The MLB live-state model will keep running, and odds will resume after the quota resets.")
        else:
            st.warning(f"Live sportsbook feed is temporarily unavailable ({status or 'network error'}).")
        return {}
    except Exception as exc:
        st.warning(f"Live sportsbook feed is temporarily unavailable: {exc}")
        return {}

    if not snaps:
        st.caption("📡 No matching live sportsbook events were returned for the verified MLB slate right now.")
        return {}

    st.markdown(f"## {title}")
    for _, row in games_df.iterrows():
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        snap = snaps.get(pk)
        if snap:
            st.markdown(f"**{row.get('away_team')} @ {row.get('home_team')}**")
            render_snapshot(snap, title="Current ML • Run Line • Total", compact=True)
    return snaps
