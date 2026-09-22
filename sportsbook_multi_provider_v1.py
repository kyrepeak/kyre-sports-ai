"""Kyre Sports AI sportsbook multi-provider adapter V1.

SportsGameOdds is the preferred sportsbook source when SPORTSGAMEODDS_API_KEY
is present in Streamlit Secrets/environment. Odds-API.io remains the fallback.

The adapter returns the SAME normalized MLB snapshot contract already consumed by
Slate V20.x and Daily Game Picks Run Line/Total. It does not alter any model math,
Monte Carlo depth, no-vig formula, market eligibility rule, or final-card scoring.
Only sportsbook transport/provider selection changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os

import requests
import streamlit as st

from live_odds_feed import _age_seconds, _same_team, get_api_key as get_legacy_api_key, get_bookmakers as get_legacy_bookmakers
from slate_odds_feed_v201 import _target_start, _window_for_games
from slate_odds_feed_v203 import _attach_best_and_movement
from slate_odds_feed_v205 import _normalize_snapshot, slate_snapshots_for_games_v205 as legacy_snapshots

SGO_BASE = "https://api.sportsgameodds.com/v2"
SGO_CACHE_TTL_SECONDS = 180
SGO_DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,caesars"

# Main full-game MLB markets only. SportsGameOdds oddID schema is
# {statID}-{statEntityID}-{periodID}-{betTypeID}-{sideID}.
SGO_MAIN_ODD_IDS = ",".join(
    [
        "points-away-game-ml-away",
        "points-home-game-ml-home",
        "points-away-game-sp-away",
        "points-home-game-sp-home",
        "points-all-game-ou-over",
        "points-all-game-ou-under",
    ]
)

_BOOK_ALIASES = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "espnbet": "ESPN BET",
    "fanatics": "Fanatics",
    "bet365": "bet365",
    "bovada": "Bovada",
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
    upper = key.upper()
    if any(x in upper for x in ("PASTE_YOUR_KEY_HERE", "YOUR_API_KEY", "YOUR_KEY_HERE", "API_KEY_HERE")):
        return None
    return key


def get_sgo_api_key():
    return _clean_key(
        st.session_state.get("ks_sportsgameodds_key")
        or _secret("SPORTSGAMEODDS_API_KEY")
        or os.getenv("SPORTSGAMEODDS_API_KEY")
        or os.getenv("SPORTSGAMEODDS_KEY")
    )


def _book_id(value):
    text = "".join(ch for ch in str(value or "").lower() if ch.isalnum())
    aliases = {
        "draftkings": "draftkings",
        "fanduel": "fanduel",
        "betmgm": "betmgm",
        "caesars": "caesars",
        "espnbet": "espnbet",
        "fanatics": "fanatics",
        "bet365": "bet365",
        "bovada": "bovada",
    }
    return aliases.get(text, text)


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


def get_display_bookmakers():
    if get_sgo_api_key():
        return ",".join(_BOOK_ALIASES.get(x, x) for x in get_sgo_bookmakers().split(",") if x)
    return get_legacy_bookmakers()


def has_any_provider():
    return bool(get_sgo_api_key() or _clean_key(get_legacy_api_key()))


def provider_name():
    if get_sgo_api_key():
        return "SportsGameOdds"
    if _clean_key(get_legacy_api_key()):
        return "Odds-API.io"
    return "Not connected"


def _float(value):
    try:
        return float(value)
    except Exception:
        return None


def _american(value):
    if value is None:
        return None
    try:
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        return int(round(float(text)))
    except Exception:
        return None


def _fmt_american(value):
    try:
        return f"{int(value):+d}"
    except Exception:
        return "—"


def _team_name(event, side):
    team = ((event or {}).get("teams") or {}).get(side) or {}
    names = team.get("names") or {}
    for field in ("long", "display", "medium", "short"):
        value = names.get(field)
        if value:
            return str(value)
    for field in ("name", "teamName"):
        value = team.get(field)
        if value:
            return str(value)
    return ""


def _event_start(event):
    value = (((event or {}).get("status") or {}).get("startsAt") or (event or {}).get("startTime") or (event or {}).get("date"))
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
        ea = _team_name(event, "away")
        eh = _team_name(event, "home")
        if _same_team(ea, away) and _same_team(eh, home):
            exact.append(event)
        elif _same_team(ea, home) and _same_team(eh, away):
            reverse.append(event)
    candidates = exact or reverse
    if not candidates:
        return None
    if len(candidates) == 1 or target is None:
        return candidates[0]

    def distance(event):
        dt = _event_start(event)
        return abs((dt - target).total_seconds()) if dt is not None else 10**12

    return min(candidates, key=distance)


def _new_row(book_id):
    return {
        "Book": _BOOK_ALIASES.get(str(book_id).lower(), str(book_id)),
        "Away ML": None,
        "Home ML": None,
        "Away RL": None,
        "Home RL": None,
        "Over": None,
        "Under": None,
        "away_rl_line": None,
        "home_rl_line": None,
        "away_rl_price": None,
        "home_rl_price": None,
        "total_line": None,
        "over_price": None,
        "under_price": None,
        "updatedAt": None,
    }


def _newer(current, candidate):
    if not candidate:
        return current
    if not current:
        return candidate
    try:
        a = datetime.fromisoformat(str(current).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(candidate).replace("Z", "+00:00"))
        return candidate if b > a else current
    except Exception:
        return candidate or current


def _parse_sgo_event(event):
    rows = {}
    odds = (event or {}).get("odds") or {}
    if not isinstance(odds, dict):
        odds = {}

    for odd in odds.values():
        if not isinstance(odd, dict):
            continue
        if str(odd.get("periodID") or "") != "game":
            continue
        bet_type = str(odd.get("betTypeID") or "").lower()
        side = str(odd.get("sideID") or "").lower()
        entity = str(odd.get("statEntityID") or "").lower()
        by_book = odd.get("byBookmaker") or {}
        if not isinstance(by_book, dict):
            continue

        for book_id, book_data in by_book.items():
            if not isinstance(book_data, dict) or book_data.get("available") is False:
                continue
            row = rows.setdefault(str(book_id), _new_row(book_id))
            row["updatedAt"] = _newer(row.get("updatedAt"), book_data.get("lastUpdatedAt"))
            price = _american(book_data.get("odds"))

            if bet_type == "ml" and side in {"away", "home"}:
                row["Away ML" if side == "away" else "Home ML"] = price

            elif bet_type == "sp" and side in {"away", "home"}:
                line = _float(book_data.get("spread"))
                if line is None:
                    continue
                if side == "away":
                    row["away_rl_line"] = line
                    row["away_rl_price"] = price
                    row["Away RL"] = f"{line:+g} ({_fmt_american(price)})"
                else:
                    row["home_rl_line"] = line
                    row["home_rl_price"] = price
                    row["Home RL"] = f"{line:+g} ({_fmt_american(price)})"

            elif bet_type == "ou" and entity == "all" and side in {"over", "under"}:
                line = _float(book_data.get("overUnder"))
                if line is None:
                    continue
                row["total_line"] = line
                if side == "over":
                    row["over_price"] = price
                    row["Over"] = f"O {line:g} ({_fmt_american(price)})"
                else:
                    row["under_price"] = price
                    row["Under"] = f"U {line:g} ({_fmt_american(price)})"

    row_list = list(rows.values())
    for row in row_list:
        row["age_seconds"] = _age_seconds(row.get("updatedAt"))

    away = _team_name(event, "away")
    home = _team_name(event, "home")
    event_id = (event or {}).get("eventID") or (event or {}).get("id")
    starts_at = (((event or {}).get("status") or {}).get("startsAt") or (event or {}).get("startTime"))
    parsed = {
        "rows": row_list,
        "away": away,
        "home": home,
        "event_id": event_id,
        "event_status": (event or {}).get("status"),
        "event_date": starts_at,
        "provider": "SportsGameOdds",
        "event": {
            "id": event_id,
            "away": away,
            "home": home,
            "date": starts_at,
            "status": (event or {}).get("status"),
        },
    }
    parsed = _attach_best_and_movement(parsed)
    parsed = _normalize_snapshot(parsed)
    parsed["provider"] = "SportsGameOdds"
    return parsed


@st.cache_data(ttl=SGO_CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_sgo_events(api_key, starts_after, starts_before, bookmakers):
    headers = {"x-api-key": str(api_key)}
    params = {
        "leagueID": "MLB",
        "oddsAvailable": "true",
        "startsAfter": str(starts_after),
        "startsBefore": str(starts_before),
        "oddID": SGO_MAIN_ODD_IDS,
        "bookmakerID": str(bookmakers),
        "limit": 50,
    }
    response = requests.get(f"{SGO_BASE}/events", params=params, headers=headers, timeout=20)

    # SportsGameOdds documents that very complex filter combinations can be slower.
    # If the focused request times out server-side, retry ONCE with fewer response
    # filters while preserving the exact slate window. No looping/retry storm.
    if response.status_code in {400, 504}:
        reduced = {
            "leagueID": "MLB",
            "oddsAvailable": "true",
            "startsAfter": str(starts_after),
            "startsBefore": str(starts_before),
            "limit": 50,
        }
        response = requests.get(f"{SGO_BASE}/events", params=reduced, headers=headers, timeout=20)

    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []


def sportsgameodds_snapshots(games_df):
    key = get_sgo_api_key()
    if not key or games_df is None or getattr(games_df, "empty", True):
        return {}
    start_iso, end_iso = _window_for_games(games_df)
    events = _fetch_sgo_events(key, start_iso, end_iso, get_sgo_bookmakers())
    out = {}
    for _, row in games_df.iterrows():
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        event = _match_event(events, row)
        if not event:
            continue
        snap = _parse_sgo_event(event)
        if snap.get("rows"):
            out[pk] = snap
    return out


def legacy_provider_snapshots(games_df):
    key = _clean_key(get_legacy_api_key())
    if not key:
        return {}
    return legacy_snapshots(games_df, key, get_legacy_bookmakers()) or {}


def snapshots_for_games_multi(games_df, fallback=True):
    """SportsGameOdds primary; Odds-API.io fallback. Never fabricates a line."""
    sgo_key = get_sgo_api_key()
    primary_error = None
    fallback_error = None

    if sgo_key:
        try:
            snaps = sportsgameodds_snapshots(games_df)
            if snaps:
                st.session_state["ks_sportsbook_provider_status"] = {
                    "provider": "SportsGameOdds",
                    "games": len(snaps),
                    "fallback_used": False,
                    "error": None,
                }
                return snaps
        except Exception as exc:
            primary_error = exc

    if fallback and _clean_key(get_legacy_api_key()):
        try:
            snaps = legacy_provider_snapshots(games_df)
            if snaps:
                st.session_state["ks_sportsbook_provider_status"] = {
                    "provider": "Odds-API.io",
                    "games": len(snaps),
                    "fallback_used": bool(sgo_key),
                    "error": type(primary_error).__name__ if primary_error else None,
                }
                return snaps
        except Exception as exc:
            fallback_error = exc

    st.session_state["ks_sportsbook_provider_status"] = {
        "provider": "Unavailable",
        "games": 0,
        "fallback_used": bool(sgo_key and _clean_key(get_legacy_api_key())),
        "error": type(primary_error or fallback_error).__name__ if (primary_error or fallback_error) else None,
    }

    if fallback_error is not None:
        raise fallback_error
    if primary_error is not None:
        raise primary_error
    return {}


def status_summary():
    state = st.session_state.get("ks_sportsbook_provider_status") or {}
    provider = state.get("provider") or provider_name()
    games = int(state.get("games", 0) or 0)
    fallback_used = bool(state.get("fallback_used"))
    suffix = " • automatic fallback used" if fallback_used else ""
    return f"{provider} • {games} matched game(s){suffix}"
