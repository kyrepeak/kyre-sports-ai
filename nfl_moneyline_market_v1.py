"""NFL-only Step-5 Moneyline sportsbook transport.

SportsGameOdds is primary and the existing Odds-API.io account is the fallback.
This module transports pregame full-game Moneyline prices only. It never changes
Step-4C probabilities or enables edge/EV, Monte Carlo, or recommendations.

Freshness: FRESH <=60s, AGING <=180s, STALE >180s. Only timestamped, non-stale
same-book Away/Home pairs are eligible for no-vig market summaries.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
import re
import unicodedata

import numpy as np
import pandas as pd
import requests
import streamlit as st

import nfl_hub_v1 as foundation

MODEL_VERSION = "NFL MONEYLINE MARKET V1 • SGO PRIMARY • ODDS-API.IO FALLBACK"
SGO_BASE = "https://api.sportsgameodds.com/v2"
ODDS_BASE = "https://api.odds-api.io/v3"
SGO_ODD_IDS = "points-away-game-ml-away,points-home-game-ml-home"
SGO_DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,caesars"
LEGACY_DEFAULT_BOOKMAKERS = "FanDuel,DraftKings"
CACHE_TTL_SECONDS = 45
FRESH_SECONDS = 60
STALE_SECONDS = 180

_BOOKS = {
    "draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM",
    "caesars": "Caesars", "espnbet": "ESPN BET", "fanatics": "Fanatics",
    "bet365": "bet365", "pinnacle": "Pinnacle", "circa": "Circa",
}


def _secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _clean_key(value):
    key = str(value or "").strip()
    if not key:
        return None
    if any(x in key.upper() for x in ("PASTE_YOUR_KEY_HERE", "YOUR_API_KEY", "YOUR_KEY_HERE", "API_KEY_HERE")):
        return None
    return key


def get_sgo_api_key():
    return _clean_key(
        st.session_state.get("ks_sportsgameodds_key")
        or _secret("SPORTSGAMEODDS_API_KEY")
        or os.getenv("SPORTSGAMEODDS_API_KEY")
        or os.getenv("SPORTSGAMEODDS_KEY")
    )


def get_legacy_api_key():
    return _clean_key(
        st.session_state.get("ks_odds_api_key")
        or _secret("ODDS_API_IO_KEY")
        or os.getenv("ODDS_API_IO_KEY")
        or os.getenv("ODDS_API_KEY")
    )


def _book_id(value):
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def get_sgo_bookmakers():
    raw = (
        st.session_state.get("ks_sportsgameodds_bookmakers")
        or _secret("SPORTSGAMEODDS_BOOKMAKERS")
        or os.getenv("SPORTSGAMEODDS_BOOKMAKERS")
        or SGO_DEFAULT_BOOKMAKERS
    )
    books = []
    for value in str(raw).split(","):
        book = _book_id(value)
        if book and book not in books:
            books.append(book)
    return ",".join(books[:8]) or SGO_DEFAULT_BOOKMAKERS


def get_legacy_bookmakers():
    raw = (
        st.session_state.get("ks_odds_bookmakers")
        or _secret("ODDS_BOOKMAKERS")
        or os.getenv("ODDS_BOOKMAKERS")
        or LEGACY_DEFAULT_BOOKMAKERS
    )
    books = [x.strip() for x in str(raw).split(",") if x.strip()]
    return ",".join(books[:4]) or LEGACY_DEFAULT_BOOKMAKERS


def connection_state():
    return {
        "sgo": bool(get_sgo_api_key()),
        "legacy": bool(get_legacy_api_key()),
        "sgo_books": get_sgo_bookmakers(),
        "legacy_books": get_legacy_bookmakers(),
    }


def _ascii(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _team_key(value):
    parts = re.findall(r"[a-z0-9]+", _ascii(value).lower())
    if not parts:
        return ""
    token = parts[-1]
    return "commanders" if token == "footballteam" else token


def _american(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(round(float(str(value).replace(",", ""))))
    except Exception:
        return None


def _decimal_to_american(value):
    try:
        d = float(value)
    except Exception:
        return None
    if d <= 1.0:
        return None
    return int(round((d - 1.0) * 100.0)) if d >= 2.0 else int(round(-100.0 / (d - 1.0)))


def implied_probability(american):
    try:
        a = float(american)
    except Exception:
        return None
    if a == 0:
        return None
    return (-a) / ((-a) + 100.0) if a < 0 else 100.0 / (a + 100.0)


def _iso_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _age_seconds(value):
    dt = _iso_dt(value)
    return None if dt is None else max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))


def _newer(current, candidate):
    a, b = _iso_dt(current), _iso_dt(candidate)
    return candidate if b is not None and (a is None or b > a) else current


def freshness_label(age):
    if age is None:
        return "UNKNOWN"
    try:
        n = int(age)
    except Exception:
        return "UNKNOWN"
    return "FRESH" if n <= FRESH_SECONDS else "AGING" if n <= STALE_SECONDS else "STALE"


def _enrich(row):
    row = dict(row or {})
    row["freshness"] = freshness_label(row.get("age_seconds"))
    away_p = implied_probability(row.get("away_ml"))
    home_p = implied_probability(row.get("home_ml"))
    pair = away_p is not None and home_p is not None and (away_p + home_p) > 0
    row["away_implied"], row["home_implied"] = away_p, home_p
    row["overround"] = away_p + home_p - 1.0 if pair else None
    row["away_no_vig"] = away_p / (away_p + home_p) if pair else None
    row["home_no_vig"] = home_p / (away_p + home_p) if pair else None
    row["complete_pair"] = bool(pair)
    age = row.get("age_seconds")
    row["usable"] = bool(pair and age is not None and int(age) <= STALE_SECONDS)
    return row


def _slate_window(day_str):
    start = pd.Timestamp(day_str).tz_localize(foundation.ET)
    a = (start - pd.Timedelta(hours=6)).tz_convert("UTC")
    b = (start + pd.Timedelta(days=1, hours=10)).tz_convert("UTC")
    return a.isoformat().replace("+00:00", "Z"), b.isoformat().replace("+00:00", "Z")


def _scheduled_start(game):
    day, tip = str(game.get("game_date") or ""), str(game.get("tip_et") or "")
    if not day or not tip or tip.upper() == "TBD":
        return None
    clean = tip.replace(" ET", "").replace(" EDT", "").replace(" EST", "").strip()
    try:
        ts = pd.to_datetime(f"{day} {clean}")
        if ts.tzinfo is None:
            ts = ts.tz_localize(foundation.ET)
        return ts.tz_convert("UTC").to_pydatetime()
    except Exception:
        return None


def _event_start(event):
    return _iso_dt(
        ((event or {}).get("status") or {}).get("startsAt")
        or (event or {}).get("startTime")
        or (event or {}).get("date")
    )


def _sgo_team(event, side):
    team = ((event or {}).get("teams") or {}).get(side) or {}
    names = team.get("names") or {}
    for field in ("long", "display", "medium", "short"):
        if names.get(field):
            return str(names[field])
    return str(team.get("name") or team.get("teamName") or "")


def _match_event(events, game, sgo=True):
    away_key, home_key = _team_key(game.get("away_team")), _team_key(game.get("home_team"))
    target = _scheduled_start(game)
    matches = []
    for event in events or []:
        away = _sgo_team(event, "away") if sgo else event.get("away")
        home = _sgo_team(event, "home") if sgo else event.get("home")
        if _team_key(away) == away_key and _team_key(home) == home_key:
            matches.append(event)
    if not matches:
        return None
    if len(matches) == 1 or target is None:
        return matches[0]
    def distance(event):
        dt = _event_start(event)
        return abs((dt - target).total_seconds()) if dt else 10**12
    return min(matches, key=distance)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_sgo(api_key, starts_after, starts_before, bookmakers):
    headers = {"x-api-key": str(api_key)}
    params = {
        "leagueID": "NFL", "oddsAvailable": "true", "startsAfter": starts_after,
        "startsBefore": starts_before, "oddID": SGO_ODD_IDS,
        "bookmakerID": bookmakers, "includeAltLines": "false", "limit": 50,
    }
    r = requests.get(f"{SGO_BASE}/events", params=params, headers=headers, timeout=20)
    if r.status_code in {400, 504}:
        params.pop("oddID", None)
        r = requests.get(f"{SGO_BASE}/events", params=params, headers=headers, timeout=20)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, list) else []


def _parse_sgo(event, game_id):
    rows = {}
    odds = (event or {}).get("odds") or {}
    for odd in odds.values() if isinstance(odds, dict) else []:
        if not isinstance(odd, dict):
            continue
        if str(odd.get("periodID") or "").lower() != "game" or str(odd.get("betTypeID") or "").lower() != "ml":
            continue
        side = str(odd.get("sideID") or "").lower()
        if side not in {"away", "home"}:
            continue
        by_book = odd.get("byBookmaker") or {}
        for raw_book, data in by_book.items() if isinstance(by_book, dict) else []:
            if not isinstance(data, dict) or data.get("available") is False:
                continue
            key = _book_id(raw_book)
            row = rows.setdefault(key, {
                "game_id": str(game_id), "book": _BOOKS.get(key, str(raw_book)),
                "away_ml": None, "home_ml": None, "updated_at": None,
                "provider": "SportsGameOdds",
            })
            row[f"{side}_ml"] = _american(data.get("odds"))
            row["updated_at"] = _newer(row.get("updated_at"), data.get("lastUpdatedAt"))
    out = []
    for row in rows.values():
        row["age_seconds"] = _age_seconds(row.get("updated_at"))
        out.append(_enrich(row))
    return sorted(out, key=lambda x: str(x.get("book")))


def _event_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    return []


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _legacy_search(api_key, query):
    r = requests.get(f"{ODDS_BASE}/events/search", params={"apiKey": api_key, "query": query}, timeout=15)
    r.raise_for_status()
    return _event_list(r.json())


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _legacy_multi(api_key, event_ids, bookmakers):
    ids = [str(x) for x in event_ids if x is not None]
    if not ids:
        return []
    out = []
    for start in range(0, len(ids), 10):
        r = requests.get(
            f"{ODDS_BASE}/odds/multi",
            params={"apiKey": api_key, "eventIds": ",".join(ids[start:start+10]), "bookmakers": bookmakers},
            timeout=15,
        )
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, list):
            out.extend(payload)
        elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
            out.extend(payload["data"])
        elif isinstance(payload, dict) and payload.get("id") is not None:
            out.append(payload)
    return out


def _parse_legacy(payload, game_id):
    out = []
    books = (payload or {}).get("bookmakers") or {}
    for raw_book, markets in books.items() if isinstance(books, dict) else []:
        row = {
            "game_id": str(game_id), "book": str(raw_book), "away_ml": None,
            "home_ml": None, "updated_at": None, "provider": "Odds-API.io",
        }
        for market in markets or []:
            key = " ".join(str((market or {}).get("name") or "").lower().replace("_", " ").replace("/", " ").split())
            if key not in {"ml", "moneyline", "money line", "match winner"}:
                continue
            odds = (market or {}).get("odds") or []
            first = next((x for x in odds if isinstance(x, dict)), {})
            row["away_ml"] = _decimal_to_american(first.get("away"))
            row["home_ml"] = _decimal_to_american(first.get("home"))
            row["updated_at"] = _newer(row.get("updated_at"), (market or {}).get("updatedAt"))
        row["age_seconds"] = _age_seconds(row.get("updated_at"))
        out.append(_enrich(row))
    return sorted(out, key=lambda x: str(x.get("book")))


def _merge(primary, fallback):
    merged = {_book_id(x.get("book")): dict(x) for x in primary or []}
    for row in fallback or []:
        merged.setdefault(_book_id(row.get("book")), dict(row))
    return sorted(merged.values(), key=lambda x: str(x.get("book")))


def _summary(rows):
    rows = [dict(x) for x in rows or []]
    usable = [x for x in rows if x.get("usable")]
    nv = [float(x["away_no_vig"]) for x in usable if x.get("away_no_vig") is not None]
    away_nv = float(np.median(nv)) if nv else None
    away_prices = [(int(x["away_ml"]), str(x.get("book"))) for x in usable if x.get("away_ml") is not None]
    home_prices = [(int(x["home_ml"]), str(x.get("book"))) for x in usable if x.get("home_ml") is not None]
    ba = max(away_prices, key=lambda z: z[0]) if away_prices else None
    bh = max(home_prices, key=lambda z: z[0]) if home_prices else None
    n = len(usable)
    return {
        "rows": rows, "usable_rows": usable, "usable_books": n,
        "quality": "HIGH" if n >= 3 else "MEDIUM" if n == 2 else "LIMITED" if n == 1 else "UNAVAILABLE",
        "consensus_away_no_vig": away_nv,
        "consensus_home_no_vig": 1.0 - away_nv if away_nv is not None else None,
        "best_away": {"price": ba[0], "book": ba[1]} if ba else None,
        "best_home": {"price": bh[0], "book": bh[1]} if bh else None,
        "disagreement": max(nv) - min(nv) if len(nv) >= 2 else None,
        "freshest_age": min([int(x["age_seconds"]) for x in rows if x.get("age_seconds") is not None], default=None),
        "providers": sorted({str(x.get("provider")) for x in rows if x.get("provider")}),
        "ready": bool(n >= 1),
    }


def fetch_nfl_moneyline_markets(pregame: pd.DataFrame, day_str: str):
    state = connection_state()
    snapshots = {}
    diag = {
        "sgo_connected": state["sgo"], "fallback_connected": state["legacy"],
        "sgo_error": "", "fallback_error": "", "games_requested": int(len(pregame)) if pregame is not None else 0,
        "games_with_market": 0,
    }
    if pregame is None or pregame.empty:
        return snapshots, diag

    sgo_events = []
    if state["sgo"]:
        try:
            start, end = _slate_window(day_str)
            sgo_events = _fetch_sgo(get_sgo_api_key(), start, end, state["sgo_books"])
        except Exception as exc:
            diag["sgo_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"

    missing = []
    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = str(game.get("game_id") or f"{game.get('away_abbr')}@{game.get('home_abbr')}")
        event = _match_event(sgo_events, game, sgo=True) if sgo_events else None
        rows = _parse_sgo(event, gid) if event else []
        snapshots[gid] = {"game": game, "rows": rows, "primary_matched": bool(event), "fallback_used": False}
        if not any(x.get("complete_pair") for x in rows):
            missing.append((gid, game))

    if missing and state["legacy"]:
        try:
            found, event_ids = {}, []
            for gid, game in missing:
                query = str(game.get("away_team") or "").strip()
                event = _match_event(_legacy_search(get_legacy_api_key(), query), game, sgo=False) if query else None
                if event and event.get("id") is not None:
                    found[gid] = event
                    event_ids.append(event["id"])
            payloads = _legacy_multi(get_legacy_api_key(), tuple(event_ids), state["legacy_books"]) if event_ids else []
            by_id = {str(x.get("id")): x for x in payloads if isinstance(x, dict) and x.get("id") is not None}
            for gid, event in found.items():
                fallback_rows = _parse_legacy(by_id.get(str(event.get("id"))), gid)
                snapshots[gid]["rows"] = _merge(snapshots[gid].get("rows"), fallback_rows)
                snapshots[gid]["fallback_used"] = bool(fallback_rows)
        except Exception as exc:
            diag["fallback_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"

    for gid, snap in list(snapshots.items()):
        snap.update(_summary(snap.get("rows")))
        snapshots[gid] = snap
    diag["games_with_market"] = sum(1 for x in snapshots.values() if x.get("ready"))
    return snapshots, diag


def fmt_american(value):
    try:
        return f"{int(value):+d}"
    except Exception:
        return "—"


def fmt_pct(value, digits=1):
    try:
        return f"{100.0 * float(value):.{digits}f}%"
    except Exception:
        return "—"


def fmt_age(age):
    if age is None:
        return "—"
    try:
        n = int(age)
    except Exception:
        return "—"
    return f"{n}s" if n < 60 else f"{n // 60}m {n % 60:02d}s"


__all__ = [
    "MODEL_VERSION", "FRESH_SECONDS", "STALE_SECONDS", "fetch_nfl_moneyline_markets",
    "connection_state", "freshness_label", "fmt_american", "fmt_pct", "fmt_age",
]
