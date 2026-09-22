"""WNBA Rebounds + Assists market transport V1.

Isolated exact-market bridge for the combined full-game Rebounds + Assists
player prop. This module does not synthesize R+A lines from separate rebounds
and assists markets and does not contain projection/Monte-Carlo/ranking math.

Verified provider market contract:
    rebounds+assists-PLAYER_ID-game-ou-over
    rebounds+assists-PLAYER_ID-game-ou-under

Only exact same-player + same-book + same-line Over/Under pairs can receive a
no-vig probability. Provider rows are reconciled to the already-verified current
WNBA slate player pool before they are labeled VERIFIED.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

import numpy as np
import pandas as pd
import requests
import streamlit as st

import wnba_schedule_v24 as schedule24
import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "WNBA R+A MARKET V1 • EXACT PAIRED SPORTSGAMEODDS TRANSPORT"
RA_STAT_ID = "rebounds+assists"
RA_MARKET_NAME = "Rebounds + Assists"
RA_ODD_IDS = (
    "rebounds+assists-PLAYER_ID-game-ou-over,"
    "rebounds+assists-PLAYER_ID-game-ou-under"
)
CACHE_TTL_SECONDS = 180


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _safe_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _norm(value) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _american(value):
    try:
        text = str(value).strip().replace(",", "")
        return int(round(float(text))) if text else None
    except Exception:
        return None


def _float(value):
    try:
        return float(value)
    except Exception:
        return None


def _implied(odds):
    x = _num(odds, np.nan)
    if not np.isfinite(x) or x == 0:
        return np.nan
    if x < 0:
        return (-x) / ((-x) + 100.0)
    return 100.0 / (x + 100.0)


def _dt(value):
    if not value:
        return None
    try:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if out.tzinfo is None:
            out = out.replace(tzinfo=timezone.utc)
        return out.astimezone(timezone.utc)
    except Exception:
        return None


def _older_timestamp(a, b):
    da, db = _dt(a), _dt(b)
    if da is None:
        return b
    if db is None:
        return a
    return a if da <= db else b


def _newer_quote(current: dict | None, price, updated_at):
    candidate = {"price": price, "updated_at": updated_at}
    if current is None:
        return candidate
    old_dt, new_dt = _dt(current.get("updated_at")), _dt(updated_at)
    if new_dt is not None and (old_dt is None or new_dt > old_dt):
        return candidate
    return current


def _age_seconds(value):
    dt = _dt(value)
    if dt is None:
        return np.nan
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())


def _player_name(event: dict, player_id: str, market_name="") -> str:
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
                return str(names[field])
        for field in ("displayName", "fullName", "name"):
            if candidate.get(field):
                return str(candidate[field])

    text = str(market_name or "").strip()
    for suffix in (
        " Rebounds + Assists Over/Under",
        " Rebounds + Assists",
        " REB + AST Over/Under",
        " REB + AST",
    ):
        if text.lower().endswith(suffix.lower()):
            return text[: -len(suffix)].strip()
    if text:
        return text.split(" Over/Under", 1)[0].strip()

    raw = re.sub(r"_\d+_WNBA$", "", str(player_id or ""), flags=re.I)
    return raw.replace("_", " ").title()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False, max_entries=12)
def _fetch_events(api_key: str, starts_after: str, starts_before: str, bookmakers: str):
    headers = {"x-api-key": str(api_key)}
    base = {
        "leagueID": "WNBA",
        "oddsAvailable": "true",
        "startsAfter": str(starts_after),
        "startsBefore": str(starts_before),
        "bookmakerID": str(bookmakers),
        "includeAltLines": "false",
        "limit": 50,
    }
    # Existing production WNBA bridge uses `oddID`. Provider documentation also
    # describes `oddIDs`; retry that spelling only if the filtered request is rejected.
    params = {**base, "oddID": RA_ODD_IDS}
    response = requests.get(f"{sgo.SGO_BASE}/events", params=params, headers=headers, timeout=20)
    if response.status_code == 400:
        params = {**base, "oddIDs": RA_ODD_IDS}
        response = requests.get(f"{sgo.SGO_BASE}/events", params=params, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, list) else []


def _parse_event(event: dict, game_id: str) -> list[dict]:
    odds = (event or {}).get("odds") or {}
    if not isinstance(odds, dict):
        return []

    buckets: dict[tuple, dict] = {}
    for odd in odds.values():
        if not isinstance(odd, dict):
            continue
        if str(odd.get("statID") or "").lower() != RA_STAT_ID:
            continue
        if str(odd.get("periodID") or "").lower() != "game":
            continue
        if str(odd.get("betTypeID") or "").lower() != "ou":
            continue
        side = str(odd.get("sideID") or "").lower()
        if side not in {"over", "under"}:
            continue
        player_id = str(odd.get("playerID") or odd.get("statEntityID") or "").strip()
        if not player_id or player_id.lower() in {"all", "home", "away"}:
            continue

        name = _player_name(event, player_id, odd.get("marketName"))
        by_book = odd.get("byBookmaker") or {}
        if not isinstance(by_book, dict):
            continue
        for book_id, book_data in by_book.items():
            if not isinstance(book_data, dict) or book_data.get("available") is False:
                continue
            line = _float(book_data.get("overUnder"))
            price = _american(book_data.get("odds"))
            if line is None or price is None:
                continue
            book_key = sgo._book_id(book_id)
            key = (str(game_id or ""), player_id, book_key, float(line))
            row = buckets.setdefault(
                key,
                {
                    "game_id": str(game_id or ""),
                    "event_id": str((event or {}).get("eventID") or (event or {}).get("id") or ""),
                    "provider_player_id": player_id,
                    "provider_player": name,
                    "player_key": _norm(name),
                    "market": RA_MARKET_NAME,
                    "stat_id": RA_STAT_ID,
                    "book_id": book_key,
                    "book": sgo._BOOK_ALIASES.get(book_key, str(book_id)),
                    "line": float(line),
                    "over_price": None,
                    "under_price": None,
                    "over_updated": None,
                    "under_updated": None,
                },
            )
            current = None
            if row.get(f"{side}_price") is not None:
                current = {"price": row.get(f"{side}_price"), "updated_at": row.get(f"{side}_updated")}
            chosen = _newer_quote(current, price, book_data.get("lastUpdatedAt"))
            row[f"{side}_price"] = chosen.get("price")
            row[f"{side}_updated"] = chosen.get("updated_at")

    out = []
    for row in buckets.values():
        over = row.get("over_price")
        under = row.get("under_price")
        paired = over is not None and under is not None
        raw_o, raw_u = _implied(over), _implied(under)
        denom = raw_o + raw_u if np.isfinite(raw_o) and np.isfinite(raw_u) else np.nan
        row["raw_over_prob"] = raw_o
        row["raw_under_prob"] = raw_u
        row["no_vig_over"] = raw_o / denom if paired and np.isfinite(denom) and denom > 0 else np.nan
        row["no_vig_under"] = raw_u / denom if paired and np.isfinite(denom) and denom > 0 else np.nan
        row["hold"] = denom - 1.0 if paired and np.isfinite(denom) else np.nan
        row["pair_state"] = "PAIRED" if paired else "INCOMPLETE"
        row["updated_at"] = _older_timestamp(row.get("over_updated"), row.get("under_updated"))
        row["age_seconds"] = _age_seconds(row.get("updated_at"))
        out.append(row)
    return out


def _empty(day, state, error=None):
    return {
        "state": state,
        "selected_date": pd.to_datetime(day).strftime("%Y-%m-%d"),
        "provider": "SportsGameOdds",
        "schedule_games": 0,
        "matched_games": 0,
        "events_received": 0,
        "market_rows": pd.DataFrame(),
        "error": error,
        "bookmakers": sgo.get_bookmakers(),
    }


def market_snapshot(day):
    key = sgo.get_api_key()
    if not key:
        return _empty(day, "NO_API_KEY")
    try:
        schedule = schedule24.schedule_for_date(str(day))
    except Exception as exc:
        return _empty(day, "SCHEDULE_ERROR", f"{type(exc).__name__}: {exc}")
    if schedule is None or schedule.empty:
        return _empty(day, "NO_WNBA_GAMES")

    starts_after, starts_before = sgo._slate_window(day)
    try:
        events = _fetch_events(key, starts_after, starts_before, sgo.get_bookmakers())
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        code = getattr(response, "status_code", None)
        out = _empty(day, "PROVIDER_ERROR", f"HTTP {code}" if code else type(exc).__name__)
        out["schedule_games"] = int(len(schedule))
        return out
    except Exception as exc:
        out = _empty(day, "PROVIDER_ERROR", f"{type(exc).__name__}: {exc}")
        out["schedule_games"] = int(len(schedule))
        return out

    rows = []
    matched = 0
    for _, game in schedule.iterrows():
        event = sgo._match_event(events, game)
        if event is None:
            continue
        matched += 1
        rows.extend(_parse_event(event, str(game.get("game_id") or "")))

    frame = pd.DataFrame(rows)
    state = "CONNECTED" if not frame.empty else ("NO_OPEN_RA_MARKETS" if matched or not events else "MATCH_FAILURE")
    return {
        "state": state,
        "selected_date": pd.to_datetime(day).strftime("%Y-%m-%d"),
        "provider": "SportsGameOdds",
        "schedule_games": int(len(schedule)),
        "matched_games": int(matched),
        "events_received": int(len(events)),
        "market_rows": frame,
        "error": None,
        "bookmakers": sgo.get_bookmakers(),
    }


def reconcile_to_player_pool(day, player_pool: pd.DataFrame):
    snap = market_snapshot(day)
    market = snap.get("market_rows")
    if market is None or market.empty:
        return pd.DataFrame(), {**snap, "verified_pairs": 0, "identity_matches": 0}
    if player_pool is None or player_pool.empty:
        return pd.DataFrame(), {**snap, "state": "PLAYER_POOL_MISSING", "verified_pairs": 0, "identity_matches": 0}

    pool = player_pool.copy()
    pool["_game"] = pool.get("game_id", "").astype(str)
    pool["_name"] = pool.get("PLAYER_NAME", "").map(_norm)
    buckets: dict[tuple[str, str], list[int]] = {}
    for idx, row in pool.iterrows():
        key = (str(row.get("_game") or ""), str(row.get("_name") or ""))
        if key[0] and key[1]:
            buckets.setdefault(key, []).append(idx)

    records = []
    for _, quote in market.iterrows():
        key = (str(quote.get("game_id") or ""), _norm(quote.get("provider_player")))
        matches = buckets.get(key, [])
        if len(matches) != 1:
            continue
        player = pool.loc[matches[0]]
        rec = quote.to_dict()
        rec.update({
            "PLAYER_ID": player.get("PLAYER_ID"),
            "PLAYER_NAME": player.get("PLAYER_NAME"),
            "TEAM_ID": player.get("TEAM_ID"),
            "TEAM_NAME": player.get("TEAM_NAME"),
            "TEAM_ABBREVIATION": player.get("TEAM_ABBREVIATION"),
            "opponent_team_id": player.get("opponent_team_id"),
            "opponent": player.get("opponent"),
            "opponent_abbr": player.get("opponent_abbr"),
            "ESPN_PLAYER_ID": player.get("ESPN_PLAYER_ID"),
            "identity_state": "VERIFIED",
            "market_state": "VERIFIED" if str(quote.get("pair_state")) == "PAIRED" else "INCOMPLETE_PAIR",
        })
        records.append(rec)

    out = pd.DataFrame(records)
    verified = 0 if out.empty else int(out.get("market_state", pd.Series(dtype=str)).astype(str).eq("VERIFIED").sum())
    identities = 0 if out.empty else int(out.get("identity_state", pd.Series(dtype=str)).astype(str).eq("VERIFIED").sum())
    state = str(snap.get("state") or "CHECK")
    if verified:
        state = "VERIFIED"
    elif state == "CONNECTED":
        state = "MARKET_CHECK"
    return out, {**snap, "state": state, "verified_pairs": verified, "identity_matches": identities}


def clear_cache():
    try:
        _fetch_events.clear()
    except Exception:
        st.cache_data.clear()


__all__ = [
    "MODEL_VERSION", "RA_STAT_ID", "RA_MARKET_NAME", "RA_ODD_IDS",
    "market_snapshot", "reconcile_to_player_pool", "clear_cache",
]
