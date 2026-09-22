"""WNBA SportsGameOdds bridge V1.

WNBA-only sportsbook transport for Kyre Sports AI.

Purpose
-------
- Reuse the existing SPORTSGAMEODDS_API_KEY without touching MLB transport/model files.
- Pull WNBA full-game moneyline, spread and total markets.
- Pull WNBA player Points, Rebounds, Assists and PRA over/under props.
- Normalize sportsbook lines into a stable contract for later WNBA projection grading.
- Fail soft: missing keys, plan coverage, empty markets or provider errors never break
  the existing official WNBA schedule/player/minutes model.

This module is transport/verification only. It intentionally does NOT change any
WNBA probability, minutes, usage, matchup or Monte Carlo math.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import re
import unicodedata
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

import wnba_schedule_v24 as schedule_engine

SGO_BASE = "https://api.sportsgameodds.com/v2"
SGO_LEAGUE_ID = "WNBA"
SGO_CACHE_TTL_SECONDS = 180
SGO_DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,caesars"
ET = ZoneInfo("America/New_York")

TEAM_ODD_IDS = (
    "points-away-game-ml-away",
    "points-home-game-ml-home",
    "points-away-game-sp-away",
    "points-home-game-sp-home",
    "points-all-game-ou-over",
    "points-all-game-ou-under",
)

PROP_STATS = {
    "points": "Points",
    "rebounds": "Rebounds",
    "assists": "Assists",
    "points+rebounds+assists": "PRA",
}

PROP_ODD_IDS = tuple(
    f"{stat}-PLAYER_ID-game-ou-{side}"
    for stat in PROP_STATS
    for side in ("over", "under")
)
WNBA_ODD_IDS = ",".join((*TEAM_ODD_IDS, *PROP_ODD_IDS))

_BOOK_ALIASES = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "espnbet": "ESPN BET",
    "fanatics": "Fanatics",
    "bet365": "bet365",
    "bovada": "Bovada",
    "pinnacle": "Pinnacle",
    "circa": "Circa",
}

# Stable canonical keys let WNBA official/ESPN team labels match provider labels
# without importing any MLB matching helper.
_WNBA_TEAM_ALIASES = {
    "atlanta dream": "dream", "dream": "dream", "atl": "dream",
    "chicago sky": "sky", "sky": "sky", "chi": "sky",
    "connecticut sun": "sun", "sun": "sun", "con": "sun",
    "dallas wings": "wings", "wings": "wings", "dal": "wings",
    "golden state valkyries": "valkyries", "valkyries": "valkyries", "gsv": "valkyries",
    "indiana fever": "fever", "fever": "fever", "ind": "fever",
    "las vegas aces": "aces", "aces": "aces", "lva": "aces",
    "los angeles sparks": "sparks", "sparks": "sparks", "la sparks": "sparks", "las": "sparks",
    "minnesota lynx": "lynx", "lynx": "lynx", "min": "lynx",
    "new york liberty": "liberty", "liberty": "liberty", "nyl": "liberty",
    "phoenix mercury": "mercury", "mercury": "mercury", "phx": "mercury",
    "seattle storm": "storm", "storm": "storm", "sea": "storm",
    "washington mystics": "mystics", "mystics": "mystics", "was": "mystics",
    "portland fire": "fire", "fire": "fire", "por": "fire",
    "toronto tempo": "tempo", "tempo": "tempo", "tor": "tempo",
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


def get_api_key():
    """Read the same SportsGameOdds secret used by the MLB side."""
    return _clean_key(
        st.session_state.get("ks_sportsgameodds_key")
        or _secret("SPORTSGAMEODDS_API_KEY")
        or os.getenv("SPORTSGAMEODDS_API_KEY")
        or os.getenv("SPORTSGAMEODDS_KEY")
    )


def _book_id(value):
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def get_bookmakers():
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


def _ascii(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _norm(value):
    return " ".join(re.findall(r"[a-z0-9]+", _ascii(value).lower()))


def _team_key(value):
    norm = _norm(value)
    if norm in _WNBA_TEAM_ALIASES:
        return _WNBA_TEAM_ALIASES[norm]
    parts = norm.split()
    return parts[-1] if parts else ""


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


def _age_seconds(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return None


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


def _event_team_name(event, side):
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
    value = (
        ((event or {}).get("status") or {}).get("startsAt")
        or (event or {}).get("startTime")
        or (event or {}).get("date")
    )
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _slate_window(day):
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    local_start = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=ET)
    starts_after = (local_start - timedelta(hours=6)).astimezone(timezone.utc)
    starts_before = (local_start + timedelta(days=1, hours=10)).astimezone(timezone.utc)
    return starts_after.isoformat().replace("+00:00", "Z"), starts_before.isoformat().replace("+00:00", "Z")


@st.cache_data(ttl=SGO_CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_events(api_key, starts_after, starts_before, bookmakers):
    headers = {"x-api-key": str(api_key)}
    params = {
        "leagueID": SGO_LEAGUE_ID,
        "oddsAvailable": "true",
        "startsAfter": str(starts_after),
        "startsBefore": str(starts_before),
        "oddID": WNBA_ODD_IDS,
        "bookmakerID": str(bookmakers),
        "includeAltLines": "false",
        "limit": 50,
    }
    response = requests.get(f"{SGO_BASE}/events", params=params, headers=headers, timeout=20)

    # One reduced retry only. This protects Streamlit from a retry storm if a
    # complex wildcard market filter is temporarily rejected by the provider.
    if response.status_code in {400, 504}:
        reduced = {
            "leagueID": SGO_LEAGUE_ID,
            "oddsAvailable": "true",
            "startsAfter": str(starts_after),
            "startsBefore": str(starts_before),
            "bookmakerID": str(bookmakers),
            "includeAltLines": "false",
            "limit": 50,
        }
        response = requests.get(f"{SGO_BASE}/events", params=reduced, headers=headers, timeout=20)

    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []


def _match_event(events, schedule_row):
    away_key = _team_key(schedule_row.get("away_team") or schedule_row.get("away_tricode"))
    home_key = _team_key(schedule_row.get("home_team") or schedule_row.get("home_tricode"))
    exact = []
    reverse = []
    for event in events or []:
        ea = _team_key(_event_team_name(event, "away"))
        eh = _team_key(_event_team_name(event, "home"))
        if ea == away_key and eh == home_key:
            exact.append(event)
        elif ea == home_key and eh == away_key:
            reverse.append(event)
    candidates = exact or reverse
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    tip = str(schedule_row.get("first_tip_et") or "").strip()
    target = None
    if tip and ":" in tip:
        try:
            day_str = pd.to_datetime(schedule_row.get("game_date")).strftime("%Y-%m-%d")
            target = datetime.strptime(f"{day_str} {tip}", "%Y-%m-%d %I:%M %p").replace(tzinfo=ET).astimezone(timezone.utc)
        except Exception:
            target = None
    if target is None:
        return candidates[0]

    def distance(event):
        dt = _event_start(event)
        return abs((dt - target).total_seconds()) if dt is not None else 10**12

    return min(candidates, key=distance)


def _player_name_from_event(event, player_id, market_name=""):
    players = (event or {}).get("players") or {}
    candidate = None
    if isinstance(players, dict):
        candidate = players.get(player_id)
        if candidate is None:
            for value in players.values():
                if isinstance(value, dict) and str(value.get("playerID") or value.get("id") or "") == str(player_id):
                    candidate = value
                    break
    elif isinstance(players, list):
        for value in players:
            if isinstance(value, dict) and str(value.get("playerID") or value.get("id") or "") == str(player_id):
                candidate = value
                break
    if isinstance(candidate, dict):
        names = candidate.get("names") or {}
        for field in ("long", "display", "medium", "short"):
            if names.get(field):
                return str(names.get(field))
        for field in ("name", "displayName", "fullName"):
            if candidate.get(field):
                return str(candidate.get(field))

    name = str(market_name or "").strip()
    suffixes = (
        " Points + Rebounds + Assists Over/Under",
        " Points + Rebounds + Assists",
        " Points Over/Under",
        " Rebounds Over/Under",
        " Assists Over/Under",
        " PRA Over/Under",
    )
    for suffix in suffixes:
        if name.lower().endswith(suffix.lower()):
            return name[: -len(suffix)].strip()
    if name:
        return name.split(" Over/Under", 1)[0].strip()

    raw = str(player_id or "")
    raw = re.sub(r"_\d+_WNBA$", "", raw, flags=re.I)
    return raw.replace("_", " ").title()


def _parse_game_lines(event, game_id):
    by_book = {}
    odds = (event or {}).get("odds") or {}
    if not isinstance(odds, dict):
        return []

    for odd in odds.values():
        if not isinstance(odd, dict):
            continue
        if str(odd.get("periodID") or "") != "game":
            continue
        stat_entity = str(odd.get("statEntityID") or "").lower()
        if stat_entity not in {"all", "home", "away"}:
            continue
        bet_type = str(odd.get("betTypeID") or "").lower()
        side = str(odd.get("sideID") or "").lower()
        by_bookmaker = odd.get("byBookmaker") or {}
        if not isinstance(by_bookmaker, dict):
            continue

        for book_id, book_data in by_bookmaker.items():
            if not isinstance(book_data, dict) or book_data.get("available") is False:
                continue
            book_key = _book_id(book_id)
            row = by_book.setdefault(
                book_key,
                {
                    "game_id": str(game_id or ""),
                    "book": _BOOK_ALIASES.get(book_key, str(book_id)),
                    "away_ml": None,
                    "home_ml": None,
                    "away_spread": None,
                    "home_spread": None,
                    "away_spread_price": None,
                    "home_spread_price": None,
                    "total": None,
                    "over_price": None,
                    "under_price": None,
                    "updated_at": None,
                    "age_seconds": None,
                },
            )
            row["updated_at"] = _newer(row.get("updated_at"), book_data.get("lastUpdatedAt"))
            price = _american(book_data.get("odds"))

            if bet_type == "ml" and side in {"away", "home"}:
                row[f"{side}_ml"] = price
            elif bet_type == "sp" and side in {"away", "home"}:
                line = _float(book_data.get("spread"))
                row[f"{side}_spread"] = line
                row[f"{side}_spread_price"] = price
            elif bet_type == "ou" and stat_entity == "all" and side in {"over", "under"}:
                line = _float(book_data.get("overUnder"))
                if line is not None:
                    row["total"] = line
                row[f"{side}_price"] = price

    rows = list(by_book.values())
    for row in rows:
        row["age_seconds"] = _age_seconds(row.get("updated_at"))
    return rows


def _parse_props(event, game_id):
    rows = []
    odds = (event or {}).get("odds") or {}
    if not isinstance(odds, dict):
        return rows

    for odd in odds.values():
        if not isinstance(odd, dict):
            continue
        stat_id = str(odd.get("statID") or "")
        if stat_id not in PROP_STATS:
            continue
        if str(odd.get("periodID") or "") != "game":
            continue
        if str(odd.get("betTypeID") or "").lower() != "ou":
            continue
        side = str(odd.get("sideID") or "").lower()
        if side not in {"over", "under"}:
            continue
        player_id = str(odd.get("playerID") or odd.get("statEntityID") or "")
        if not player_id or player_id.lower() in {"all", "home", "away"}:
            continue

        player_name = _player_name_from_event(event, player_id, odd.get("marketName"))
        by_bookmaker = odd.get("byBookmaker") or {}
        if not isinstance(by_bookmaker, dict):
            continue
        for book_id, book_data in by_bookmaker.items():
            if not isinstance(book_data, dict) or book_data.get("available") is False:
                continue
            line = _float(book_data.get("overUnder"))
            price = _american(book_data.get("odds"))
            if line is None and price is None:
                continue
            book_key = _book_id(book_id)
            updated = book_data.get("lastUpdatedAt")
            rows.append(
                {
                    "game_id": str(game_id or ""),
                    "event_id": str((event or {}).get("eventID") or (event or {}).get("id") or ""),
                    "player_id": player_id,
                    "player_name": player_name,
                    "player_key": _norm(player_name),
                    "stat_id": stat_id,
                    "market": PROP_STATS[stat_id],
                    "side": side,
                    "line": line,
                    "odds": price,
                    "book": _BOOK_ALIASES.get(book_key, str(book_id)),
                    "updated_at": updated,
                    "age_seconds": _age_seconds(updated),
                    "fair_odds": _american(odd.get("fairOdds")),
                    "fair_line": _float(odd.get("fairOverUnder")),
                }
            )
    return rows


def _empty_result(day, state, error=None):
    return {
        "selected_date": pd.to_datetime(day).strftime("%Y-%m-%d"),
        "provider": "SportsGameOdds",
        "league": SGO_LEAGUE_ID,
        "state": state,
        "events_received": 0,
        "schedule_games": 0,
        "matched_games": 0,
        "unmatched_games": [],
        "game_lines": pd.DataFrame(),
        "player_props": pd.DataFrame(),
        "error": error,
        "bookmakers": get_bookmakers(),
    }


def market_snapshot(day):
    """Return a normalized, WNBA-only SportsGameOdds snapshot for the selected date."""
    key = get_api_key()
    if not key:
        return _empty_result(day, "NO_API_KEY")

    try:
        schedule = schedule_engine.schedule_for_date(day)
    except Exception as exc:
        return _empty_result(day, "SCHEDULE_ERROR", f"{type(exc).__name__}: {exc}")

    if schedule is None or schedule.empty:
        out = _empty_result(day, "NO_WNBA_GAMES")
        out["schedule_games"] = 0
        return out

    starts_after, starts_before = _slate_window(day)
    try:
        events = _fetch_events(key, starts_after, starts_before, get_bookmakers())
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", None)
        label = f"HTTP {code}" if code else type(exc).__name__
        out = _empty_result(day, "PROVIDER_ERROR", label)
        out["schedule_games"] = int(len(schedule))
        return out
    except Exception as exc:
        out = _empty_result(day, "PROVIDER_ERROR", f"{type(exc).__name__}: {exc}")
        out["schedule_games"] = int(len(schedule))
        return out

    game_rows = []
    prop_rows = []
    unmatched = []
    matched = 0

    for _, row in schedule.iterrows():
        event = _match_event(events, row)
        if event is None:
            unmatched.append(f"{row.get('away_team','Away')} @ {row.get('home_team','Home')}")
            continue
        matched += 1
        game_id = row.get("game_id")
        game_rows.extend(_parse_game_lines(event, game_id))
        prop_rows.extend(_parse_props(event, game_id))

    game_df = pd.DataFrame(game_rows)
    prop_df = pd.DataFrame(prop_rows)
    state = "CONNECTED" if matched else ("NO_OPEN_WNBA_MARKETS" if not events else "MATCH_FAILURE")
    return {
        "selected_date": pd.to_datetime(day).strftime("%Y-%m-%d"),
        "provider": "SportsGameOdds",
        "league": SGO_LEAGUE_ID,
        "state": state,
        "events_received": len(events),
        "schedule_games": int(len(schedule)),
        "matched_games": matched,
        "unmatched_games": unmatched,
        "game_lines": game_df,
        "player_props": prop_df,
        "error": None,
        "bookmakers": get_bookmakers(),
    }


def best_prop_lines(day, market=None):
    """Convenience contract for later model grading: best price at each player/stat/side/line."""
    snap = market_snapshot(day)
    frame = snap.get("player_props")
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    if market:
        out = out.loc[out["market"].astype(str).str.upper().eq(str(market).upper())].copy()
    if out.empty:
        return out
    out["_price_sort"] = pd.to_numeric(out["odds"], errors="coerce").fillna(-100000)
    out = (
        out.sort_values(["player_key", "stat_id", "side", "line", "_price_sort"], ascending=[True, True, True, True, False])
        .drop_duplicates(subset=["player_key", "stat_id", "side", "line"], keep="first")
        .drop(columns=["_price_sort"])
        .reset_index(drop=True)
    )
    return out


def clear_cache():
    try:
        _fetch_events.clear()
    except Exception:
        st.cache_data.clear()


def render_market_panel(day):
    """Mobile-safe connection panel. Verification only; no model math is changed."""
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    st.markdown("### 🎯 WNBA SportsGameOdds Bridge")
    st.caption(
        "WNBA-only API transport • game lines + Points/Rebounds/Assists/PRA props • "
        "projection math remains PRA V2.8.x until the next modeling step"
    )

    if not get_api_key():
        st.warning(
            "SportsGameOdds is not connected for WNBA because SPORTSGAMEODDS_API_KEY is missing. "
            "The existing WNBA schedule/player/minutes engine is still active."
        )
        return

    with st.spinner("🔌 Checking WNBA markets on SportsGameOdds…"):
        snap = market_snapshot(day_str)

    state = str(snap.get("state") or "CHECK")
    game_df = snap.get("game_lines")
    prop_df = snap.get("player_props")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("API", "Connected" if state == "CONNECTED" else state.replace("_", " ").title())
    c2.metric("Games matched", f"{snap.get('matched_games',0)}/{snap.get('schedule_games',0)}")
    c3.metric("Game-line rows", 0 if game_df is None else len(game_df))
    c4.metric("Player prop rows", 0 if prop_df is None else len(prop_df))

    if state == "PROVIDER_ERROR":
        st.warning(
            "SportsGameOdds answered with an error for this WNBA slate. "
            f"Details: {snap.get('error') or 'unknown provider error'}. "
            "WNBA model inputs remain isolated and unchanged."
        )
        return
    if state == "NO_OPEN_WNBA_MARKETS":
        st.info(
            "No open WNBA SportsGameOdds events were returned for this selected date. "
            "That can happen before markets are posted or when WNBA is not enabled on the current API plan."
        )
        return
    if state == "MATCH_FAILURE":
        st.warning(
            "WNBA events were returned, but the team matcher could not pair them with the verified WNBA schedule. "
            "No sportsbook lines will be used."
        )
    if snap.get("unmatched_games"):
        st.caption("Unmatched: " + " • ".join(snap["unmatched_games"][:6]))

    if prop_df is not None and not prop_df.empty:
        summary = (
            prop_df.groupby(["market", "book"], dropna=False)
            .agg(
                Players=("player_key", "nunique"),
                Markets=("line", "count"),
                FreshestSec=("age_seconds", "min"),
            )
            .reset_index()
            .sort_values(["market", "Players"], ascending=[True, False])
        )
        summary["Freshest"] = summary["FreshestSec"].apply(
            lambda x: "—" if pd.isna(x) else (f"{int(x)}s" if float(x) < 120 else f"{int(float(x)//60)}m")
        )
        st.dataframe(
            summary[["market", "book", "Players", "Markets", "Freshest"]],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("API bridge details", expanded=False):
        st.write(
            {
                "selected_date": snap.get("selected_date"),
                "leagueID": snap.get("league"),
                "provider": snap.get("provider"),
                "bookmakers": snap.get("bookmakers"),
                "events_received": snap.get("events_received"),
                "matched_games": snap.get("matched_games"),
                "player_prop_types": list(PROP_STATS.values()),
                "model_math_changed": False,
                "mlb_files_touched": False,
            }
        )
        if st.button("🔄 Refresh WNBA SportsGameOdds", use_container_width=True, key=f"wnba_sgo_refresh_{day_str}"):
            clear_cache()
            st.rerun()


__all__ = [
    "PROP_STATS",
    "best_prop_lines",
    "clear_cache",
    "get_api_key",
    "get_bookmakers",
    "market_snapshot",
    "render_market_panel",
]
