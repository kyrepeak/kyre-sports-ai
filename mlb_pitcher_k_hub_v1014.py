"""MLB Pitcher Strikeouts O/U V1.0.14 — redundant sportsbook transport.

Root-cause repair for intermittent missing K lines. The Pitcher K model, Monte
Carlo, grading, Top-5 ordering, evidence score, Supports/Concerns and card layout
remain V1.0.13/V1.0.7 behavior.

Transport order:
1) SportsGameOdds MLB pitching_strikeouts props (primary)
2) Existing Odds-API.io nested player-prop parser (fallback / gap fill)
3) Short-lived last-good REAL fetched line cache (15 minutes, same current slate)

No line is fabricated. Cached lines are visibly labeled "(cached)" on cards.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
import time

import requests
import streamlit as st

import mlb_pitcher_k_hub_v1013 as v1013
import sportsbook_multi_provider_v1 as sgo

engine = v1013.engine
MODEL_VERSION = "Pitcher K V1.0.14"
_LEGACY_FETCH = engine._fetch_market_lines

SGO_CACHE_TTL_SECONDS = 75
LAST_GOOD_MAX_AGE_SECONDS = 15 * 60
SGO_K_ODD_IDS = ",".join([
    "pitching_strikeouts-PLAYER_ID-game-ou-over",
    "pitching_strikeouts-PLAYER_ID-game-ou-under",
])

_BOOK_ALIASES = {
    "draftkings": "DraftKings", "fanduel": "FanDuel", "betmgm": "BetMGM",
    "caesars": "Caesars", "espnbet": "ESPN BET", "fanatics": "Fanatics",
    "bet365": "bet365", "bovada": "Bovada",
}


def _float(value):
    try:
        x = float(str(value).replace(",", "").strip())
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _american(value):
    x = _float(value)
    return int(round(x)) if x is not None else None


def _book_name(book_id):
    key = "".join(ch for ch in str(book_id or "").lower() if ch.isalnum())
    return _BOOK_ALIASES.get(key, str(book_id or "Sportsbook"))


def _player_match(odd, wanted):
    parts = [odd.get("marketName"), odd.get("playerID"), odd.get("statEntityID"), odd.get("oddID")]
    hay = engine._norm_name(" ".join(str(x or "") for x in parts))
    if not hay:
        return None
    for norm, original in sorted(wanted.items(), key=lambda kv: len(kv[0]), reverse=True):
        if norm and (norm in hay or hay in norm):
            return original
    return None


@st.cache_data(ttl=SGO_CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_sgo_k_events(api_key, starts_after, starts_before, bookmakers):
    headers = {"x-api-key": str(api_key)}
    base = {
        "leagueID": "MLB", "oddsAvailable": "true",
        "startsAfter": str(starts_after), "startsBefore": str(starts_before),
        "bookmakerID": str(bookmakers), "limit": 50,
    }
    params = dict(base); params["oddIDs"] = SGO_K_ODD_IDS
    response = requests.get(f"{sgo.SGO_BASE}/events", params=params, headers=headers, timeout=20)
    if response.status_code in {400, 404, 422}:
        params = dict(base); params["oddID"] = SGO_K_ODD_IDS
        response = requests.get(f"{sgo.SGO_BASE}/events", params=params, headers=headers, timeout=20)
    if response.status_code in {502, 503, 504}:
        response = requests.get(f"{sgo.SGO_BASE}/events", params=base, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, list) else []


def _build_board_from_sgo_event(event, pitcher_names):
    wanted = {engine._norm_name(x): x for x in pitcher_names if x}
    buckets = defaultdict(lambda: {"over": None, "under": None, "updatedAt": None})
    odds = (event or {}).get("odds") or {}
    if not isinstance(odds, dict): return {}
    for odd in odds.values():
        if not isinstance(odd, dict): continue
        if str(odd.get("statID") or "").lower() != "pitching_strikeouts": continue
        if str(odd.get("periodID") or "").lower() != "game": continue
        if str(odd.get("betTypeID") or "").lower() != "ou": continue
        side = str(odd.get("sideID") or "").lower()
        if side not in {"over", "under"}: continue
        pitcher = _player_match(odd, wanted)
        if not pitcher: continue
        by_book = odd.get("byBookmaker") or {}
        if not isinstance(by_book, dict): continue
        for book_id, book_data in by_book.items():
            if not isinstance(book_data, dict) or book_data.get("available") is False: continue
            line = _float(book_data.get("overUnder"))
            price = _american(book_data.get("odds"))
            if line is None:
                line = _float(odd.get("bookOverUnder") or odd.get("fairOverUnder"))
            if line is None: continue
            key = (pitcher, float(line), str(book_id))
            buckets[key][side] = price
            buckets[key]["updatedAt"] = book_data.get("lastUpdatedAt") or book_data.get("updatedAt") or buckets[key].get("updatedAt")

    per_pitcher = defaultdict(list)
    for (pitcher, line, book_id), sides in buckets.items():
        if sides.get("over") is None and sides.get("under") is None: continue
        per_pitcher[pitcher].append({
            "line": float(line), "book_id": str(book_id), "book": _book_name(book_id),
            "over_price": sides.get("over"), "under_price": sides.get("under"),
            "updatedAt": sides.get("updatedAt"),
            "pair_complete": sides.get("over") is not None and sides.get("under") is not None,
        })

    out = {}
    for pitcher, rows in per_pitcher.items():
        by_line = defaultdict(list)
        for row in rows: by_line[round(float(row["line"]), 3)].append(row)
        def line_score(item):
            line, q = item
            complete = sum(1 for x in q if x.get("pair_complete"))
            sides = sum(int(x.get("over_price") is not None) + int(x.get("under_price") is not None) for x in q)
            books = len({x.get("book_id") for x in q})
            return (complete, books, sides, -abs(float(line)))
        chosen_line, chosen = max(by_line.items(), key=line_score)
        over_rows = [x for x in chosen if x.get("over_price") is not None]
        under_rows = [x for x in chosen if x.get("under_price") is not None]
        best_over = max(over_rows, key=lambda x: int(x["over_price"]), default=None)
        best_under = max(under_rows, key=lambda x: int(x["under_price"]), default=None)
        out[pitcher] = {
            "line": float(chosen_line),
            "best_over_book": (best_over or {}).get("book"), "best_over_price": (best_over or {}).get("over_price"),
            "best_under_book": (best_under or {}).get("book"), "best_under_price": (best_under or {}).get("under_price"),
            "over_dec": None, "under_dec": None, "quote_count": len(chosen),
            "provider": "SportsGameOdds", "cached": False,
        }
    return out


def _fetch_sgo_market_lines(games_df, pitcher_rows):
    key = sgo.get_sgo_api_key(); books = sgo.get_sgo_bookmakers()
    if not key or games_df is None or getattr(games_df, "empty", True):
        return {}, {"connected": False, "events": 0, "props": 0, "provider": "SportsGameOdds"}
    start_iso, end_iso = sgo._window_for_games(games_df)
    events = _fetch_sgo_k_events(key, start_iso, end_iso, books)
    out = {}; matched_events = 0
    for _, row in games_df.iterrows():
        try: pk = int(row.get("game_pk"))
        except Exception: continue
        event = sgo._match_event(events, row)
        if not event: continue
        matched_events += 1
        names = [x.get("player_name") for x in pitcher_rows if int(x.get("game_pk", -1)) == pk]
        for name, board in _build_board_from_sgo_event(event, names).items():
            out[(pk, engine._norm_name(name))] = board
    return out, {"connected": True, "events": matched_events, "props": len(out), "provider": "SportsGameOdds", "books": books}


def _current_game_pks(games_df):
    values = set()
    if games_df is None: return values
    try:
        for _, row in games_df.iterrows():
            try: values.add(int(row.get("game_pk")))
            except Exception: pass
    except Exception: pass
    return values


def _store_last_good(lines, games_df, provider):
    if not lines: return
    st.session_state["pk_k_last_good_market"] = {
        "saved_at": time.time(), "game_pks": sorted(_current_game_pks(games_df)),
        "provider": str(provider or "Sportsbook"), "lines": deepcopy(lines),
    }


def _load_last_good(games_df):
    state = st.session_state.get("pk_k_last_good_market") or {}
    saved = _float(state.get("saved_at"))
    if saved is None: return {}, None
    age = max(0.0, time.time() - saved)
    if age > LAST_GOOD_MAX_AGE_SECONDS: return {}, None
    if sorted(_current_game_pks(games_df)) != list(state.get("game_pks") or []): return {}, None
    raw = deepcopy(state.get("lines") or {})
    if not raw: return {}, None
    for board in raw.values():
        if not isinstance(board, dict): continue
        board["cached"] = True; board["cached_age_seconds"] = age
        board["provider"] = f"{state.get('provider') or 'Sportsbook'} cache"
        for field in ("best_over_book", "best_under_book"):
            value = board.get(field)
            if value and "(cached)" not in str(value): board[field] = f"{value} (cached)"
    return raw, age


def _fetch_market_lines_multi(games_df, pitcher_rows):
    primary_error = None; fallback_error = None
    sgo_lines = {}; sgo_meta = {"connected": False, "events": 0, "props": 0}
    if sgo.get_sgo_api_key():
        try: sgo_lines, sgo_meta = _fetch_sgo_market_lines(games_df, pitcher_rows)
        except Exception as exc:
            primary_error = exc
            sgo_meta = {"connected": False, "events": 0, "props": 0, "provider": "SportsGameOdds", "error": f"{type(exc).__name__}: {exc}"}
    legacy_lines = {}; legacy_meta = {"connected": False, "events": 0, "props": 0}
    try: legacy_lines, legacy_meta = _LEGACY_FETCH(games_df, pitcher_rows)
    except Exception as exc:
        fallback_error = exc
        legacy_meta = {"connected": False, "events": 0, "props": 0, "provider": "Odds-API.io", "error": f"{type(exc).__name__}: {exc}"}

    merged = dict(sgo_lines or {})
    for key, board in (legacy_lines or {}).items():
        if key not in merged:
            copy = dict(board or {}); copy["provider"] = "Odds-API.io"; copy["cached"] = False; merged[key] = copy
    if merged:
        providers = []
        if sgo_lines: providers.append("SportsGameOdds")
        if legacy_lines: providers.append("Odds-API.io")
        provider = " + ".join(providers) or "Sportsbook"
        _store_last_good(merged, games_df, provider)
        return merged, {
            "connected": True,
            "events": max(int((sgo_meta or {}).get("events") or 0), int((legacy_meta or {}).get("events") or 0)),
            "props": len(merged), "provider": provider,
            "primary_props": len(sgo_lines or {}), "fallback_props": len(legacy_lines or {}),
            "primary_error": str(primary_error) if primary_error else None,
            "fallback_error": str(fallback_error) if fallback_error else None, "cached": False,
        }
    cached, age = _load_last_good(games_df)
    if cached:
        return cached, {"connected": True, "events": 0, "props": len(cached), "provider": "Last-good sportsbook cache", "primary_props": 0, "fallback_props": 0, "cached": True, "cache_age_seconds": age}
    return {}, {
        "connected": bool((sgo_meta or {}).get("connected") or (legacy_meta or {}).get("connected")),
        "events": max(int((sgo_meta or {}).get("events") or 0), int((legacy_meta or {}).get("events") or 0)),
        "props": 0, "provider": "Unavailable", "primary_props": 0, "fallback_props": 0, "cached": False,
        "primary_error": str(primary_error) if primary_error else (sgo_meta or {}).get("error"),
        "fallback_error": str(fallback_error) if fallback_error else (legacy_meta or {}).get("error"),
    }


engine._fetch_market_lines = _fetch_market_lines_multi


def _install_transport():
    engine._fetch_market_lines = _fetch_market_lines_multi


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    _install_transport()
    result = v1013.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    meta = st.session_state.get("pk10_market_meta") or {}
    if meta.get("props"):
        provider = meta.get("provider") or "Sportsbook"
        if meta.get("cached"):
            age = int(float(meta.get("cache_age_seconds") or 0))
            st.caption(f"📡 Pitcher-K lines: {provider} • {meta.get('props', 0)} pitcher market(s) • cached {age // 60}m {age % 60:02d}s ago • no fabricated lines")
        else:
            st.caption(f"📡 Pitcher-K lines: {provider} • {meta.get('props', 0)} pitcher market(s) • SGO {meta.get('primary_props', 0)} / fallback {meta.get('fallback_props', 0)}")
    return result
