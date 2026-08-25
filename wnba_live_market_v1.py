"""WNBA Live Markets V1 — exact paired in-play market verification.

Step-2 transport only for the isolated WNBA Live Games page.

Contract
--------
- Reuse the existing SportsGameOdds WNBA API key/bookmaker configuration.
- Fetch only full-game WNBA moneyline, spread and total odd IDs.
- Match provider events to the already-verified live WNBA matchup by team identity.
- Preserve each outcome's own bookmaker timestamp instead of collapsing a whole
  bookmaker row to one timestamp.
- Require same-book, exact-line paired outcomes before calculating raw/no-vig
  probabilities.
- Apply a live state/quote firewall. Stale, timestamp-missing, line-mismatched or
  heavily time-skewed pairs are displayable for diagnosis but are NOT model-ready.
- No projection, Monte Carlo, EV, qualification or pick exists in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests
import streamlit as st

import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "WNBA LIVE MARKETS V1 • STEP 2 EXACT PAIRS"
ET = ZoneInfo("America/New_York")

# Deliberately conservative for manual-refresh Step 2. These are verification
# gates only; they do not grade a wager. We can tighten them when auto-refresh is
# introduced after the market/state synchronization is visually verified.
FRESH_SECONDS = 75
STALE_SECONDS = 120
MAX_PAIR_SKEW_SECONDS = 60
MAX_STATE_LAG_SECONDS = 120


def _num(value: Any):
    try:
        return float(value)
    except Exception:
        return None


def _american(value: Any):
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(round(float(str(value).replace(",", ""))))
    except Exception:
        return None


def _book_id(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _book_name(value: Any) -> str:
    key = _book_id(value)
    aliases = getattr(sgo, "_BOOK_ALIASES", {}) or {}
    return str(aliases.get(key) or value or key or "Sportsbook")


def _dt(value: Any):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _iso(value: Any) -> str:
    parsed = _dt(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else ""


def _implied(odds: int | None):
    if odds is None or odds == 0:
        return None
    if odds > 0:
        return 100.0 / (float(odds) + 100.0)
    x = abs(float(odds))
    return x / (x + 100.0)


def _novig(a: int | None, b: int | None):
    pa, pb = _implied(a), _implied(b)
    if pa is None or pb is None or (pa + pb) <= 0:
        return None, None, None
    total = pa + pb
    return pa / total, pb / total, total - 1.0


def _pair_times(left: dict, right: dict, state_captured_at: Any, now_utc: datetime):
    a = _dt(left.get("updated_at"))
    b = _dt(right.get("updated_at"))
    state_dt = _dt(state_captured_at)
    if a is None or b is None:
        return {
            "older_updated_at": "",
            "newer_updated_at": "",
            "quote_age_seconds": None,
            "pair_skew_seconds": None,
            "state_lag_seconds": None,
        }
    older, newer = min(a, b), max(a, b)
    quote_age = max(0.0, (now_utc - older).total_seconds())
    pair_skew = max(0.0, (newer - older).total_seconds())
    state_lag = None
    if state_dt is not None:
        # Positive = the conservative/older quote predates the verified game
        # state. A quote after the state snapshot has zero lag.
        state_lag = max(0.0, (state_dt - older).total_seconds())
    return {
        "older_updated_at": older.isoformat().replace("+00:00", "Z"),
        "newer_updated_at": newer.isoformat().replace("+00:00", "Z"),
        "quote_age_seconds": quote_age,
        "pair_skew_seconds": pair_skew,
        "state_lag_seconds": state_lag,
    }


def _firewall(pair_exact: bool, timing: dict) -> tuple[str, str, bool]:
    if not pair_exact:
        return "LINE MISMATCH", "BLOCKED", False
    age = timing.get("quote_age_seconds")
    skew = timing.get("pair_skew_seconds")
    lag = timing.get("state_lag_seconds")
    if age is None or skew is None:
        return "TIMESTAMP MISSING", "BLOCKED", False
    if skew > MAX_PAIR_SKEW_SECONDS:
        return "PAIR TIME SKEW", "BLOCKED", False
    if age > STALE_SECONDS or (lag is not None and lag > MAX_STATE_LAG_SECONDS):
        return "STALE", "BLOCKED", False
    if age <= FRESH_SECONDS:
        return "FRESH", "MODEL-ELIGIBLE LATER", True
    return "AGING", "MODEL-ELIGIBLE LATER", True


def _quote_bucket(event: dict) -> dict:
    """Return {book -> market -> side -> quote} preserving per-side timestamps."""
    out: dict[str, dict] = {}
    odds = (event or {}).get("odds") or {}
    if not isinstance(odds, dict):
        return out

    for odd in odds.values():
        if not isinstance(odd, dict):
            continue
        if str(odd.get("periodID") or "").lower() != "game":
            continue
        stat_entity = str(odd.get("statEntityID") or "").lower()
        if stat_entity not in {"all", "home", "away"}:
            continue
        bet_type = str(odd.get("betTypeID") or "").lower()
        side = str(odd.get("sideID") or "").lower()
        if bet_type not in {"ml", "sp", "ou"}:
            continue
        if bet_type == "ml" and side not in {"away", "home"}:
            continue
        if bet_type == "sp" and side not in {"away", "home"}:
            continue
        if bet_type == "ou" and side not in {"over", "under"}:
            continue
        by_book = odd.get("byBookmaker") or {}
        if not isinstance(by_book, dict):
            continue

        for raw_book, data in by_book.items():
            if not isinstance(data, dict) or data.get("available") is False:
                continue
            price = _american(data.get("odds"))
            if price is None:
                continue
            book = _book_name(raw_book)
            market_name = {"ml": "MONEYLINE", "sp": "SPREAD", "ou": "TOTAL"}[bet_type]
            line = None
            if bet_type == "sp":
                line = _num(data.get("spread"))
            elif bet_type == "ou":
                line = _num(data.get("overUnder"))
            quote = {
                "price": price,
                "line": line,
                "updated_at": _iso(data.get("lastUpdatedAt")),
                "available": True,
            }
            out.setdefault(book, {}).setdefault(market_name, {})[side] = quote
    return out


def _pair_row(
    *,
    book: str,
    market: str,
    left_side: str,
    right_side: str,
    left: dict,
    right: dict,
    left_name: str,
    right_name: str,
    state_captured_at: Any,
    now_utc: datetime,
):
    left_line = _num(left.get("line"))
    right_line = _num(right.get("line"))
    if market == "SPREAD":
        pair_exact = left_line is not None and right_line is not None and abs(left_line + right_line) <= 0.01
    elif market == "TOTAL":
        pair_exact = left_line is not None and right_line is not None and abs(left_line - right_line) <= 0.01
    else:
        pair_exact = True

    pa_raw = _implied(left.get("price"))
    pb_raw = _implied(right.get("price"))
    pa_nv, pb_nv, hold = _novig(left.get("price"), right.get("price"))
    timing = _pair_times(left, right, state_captured_at, now_utc)
    freshness, firewall, usable = _firewall(pair_exact, timing)

    return {
        "book": book,
        "market": market,
        "left_side": left_side,
        "right_side": right_side,
        "left_name": left_name,
        "right_name": right_name,
        "left_line": left_line,
        "right_line": right_line,
        "left_price": left.get("price"),
        "right_price": right.get("price"),
        "left_raw_prob": pa_raw,
        "right_raw_prob": pb_raw,
        "left_novig_prob": pa_nv,
        "right_novig_prob": pb_nv,
        "book_hold": hold,
        "pair_exact": bool(pair_exact),
        **timing,
        "freshness": freshness,
        "firewall": firewall,
        "model_eligible_later": bool(usable),
    }


def parse_event_pairs(event: dict, game: dict, now_utc: datetime | None = None) -> list[dict]:
    now_utc = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    buckets = _quote_bucket(event)
    rows: list[dict] = []
    away = str(game.get("away_team") or "Away")
    home = str(game.get("home_team") or "Home")
    captured = game.get("captured_at")

    for book, market_map in buckets.items():
        ml = market_map.get("MONEYLINE") or {}
        if ml.get("away") and ml.get("home"):
            rows.append(_pair_row(
                book=book, market="MONEYLINE", left_side="away", right_side="home",
                left=ml["away"], right=ml["home"], left_name=away, right_name=home,
                state_captured_at=captured, now_utc=now_utc,
            ))

        sp = market_map.get("SPREAD") or {}
        if sp.get("away") and sp.get("home"):
            rows.append(_pair_row(
                book=book, market="SPREAD", left_side="away", right_side="home",
                left=sp["away"], right=sp["home"], left_name=away, right_name=home,
                state_captured_at=captured, now_utc=now_utc,
            ))

        total = market_map.get("TOTAL") or {}
        if total.get("over") and total.get("under"):
            rows.append(_pair_row(
                book=book, market="TOTAL", left_side="over", right_side="under",
                left=total["over"], right=total["under"], left_name="OVER", right_name="UNDER",
                state_captured_at=captured, now_utc=now_utc,
            ))
    return rows


@st.cache_data(ttl=8, show_spinner=False, max_entries=8)
def _fetch_live_events(api_key: str, day_str: str, bookmakers: str):
    starts_after, starts_before = sgo._slate_window(day_str)
    params = {
        "leagueID": sgo.SGO_LEAGUE_ID,
        "oddsAvailable": "true",
        "startsAfter": starts_after,
        "startsBefore": starts_before,
        "oddID": ",".join(sgo.TEAM_ODD_IDS),
        "bookmakerID": str(bookmakers),
        "includeAltLines": "false",
        "limit": 50,
    }
    headers = {"x-api-key": str(api_key), "Cache-Control": "no-cache"}
    response = requests.get(f"{sgo.SGO_BASE}/events", params=params, headers=headers, timeout=20)
    # Match the existing bridge's single reduced retry behavior if the provider
    # temporarily rejects the detailed market filter.
    if response.status_code in {400, 504}:
        reduced = {
            "leagueID": sgo.SGO_LEAGUE_ID,
            "oddsAvailable": "true",
            "startsAfter": starts_after,
            "startsBefore": starts_before,
            "bookmakerID": str(bookmakers),
            "includeAltLines": "false",
            "limit": 50,
        }
        response = requests.get(f"{sgo.SGO_BASE}/events", params=reduced, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, list) else []


def _event_id(event: dict) -> str:
    return str((event or {}).get("eventID") or (event or {}).get("id") or "")


def market_snapshot_for_live_games(games: list[dict], day_str: str) -> dict:
    fetched_at = datetime.now(ET)
    key = sgo.get_api_key()
    books = sgo.get_bookmakers()
    base = {
        "state": "CHECK",
        "provider": "SportsGameOdds",
        "bookmakers": books,
        "fetched_at": fetched_at.isoformat(),
        "events_returned": 0,
        "games_requested": len(games or []),
        "games_matched": 0,
        "pairs": [],
        "by_game": {},
        "unmatched": [],
        "error": "",
    }
    if not key:
        base["state"] = "NO_API_KEY"
        base["error"] = "SPORTSGAMEODDS_API_KEY is not configured."
        return base
    if not games:
        base["state"] = "NO_LIVE_GAMES"
        return base

    try:
        events = _fetch_live_events(key, str(day_str), books)
    except requests.HTTPError as exc:
        code = getattr(exc.response, "status_code", None)
        base["state"] = "PROVIDER_ERROR"
        base["error"] = f"SportsGameOdds HTTP {code or 'error'}"
        return base
    except Exception as exc:
        base["state"] = "PROVIDER_ERROR"
        base["error"] = f"{type(exc).__name__}: {exc}"[:220]
        return base

    base["events_returned"] = len(events)
    now_utc = datetime.now(timezone.utc)
    all_pairs: list[dict] = []
    matched = 0

    for game in games:
        schedule_like = {
            "away_team": game.get("away_team"),
            "away_tricode": game.get("away_abbr"),
            "home_team": game.get("home_team"),
            "home_tricode": game.get("home_abbr"),
            "game_date": day_str,
            "first_tip_et": "",
        }
        event = sgo._match_event(events, schedule_like)
        game_key = str(game.get("espn_event_id") or f"{game.get('away_team_id')}-{game.get('home_team_id')}")
        if event is None:
            base["unmatched"].append(f"{game.get('away_team')} @ {game.get('home_team')}")
            base["by_game"][game_key] = {"event_id": "", "pairs": []}
            continue
        matched += 1
        rows = parse_event_pairs(event, game, now_utc=now_utc)
        event_id = _event_id(event)
        for row in rows:
            row.update({
                "espn_event_id": str(game.get("espn_event_id") or ""),
                "sgo_event_id": event_id,
                "away_team": game.get("away_team"),
                "home_team": game.get("home_team"),
                "state_captured_at": game.get("captured_at"),
            })
        all_pairs.extend(rows)
        base["by_game"][game_key] = {"event_id": event_id, "pairs": rows}

    base["games_matched"] = matched
    base["pairs"] = all_pairs
    if matched == 0:
        base["state"] = "MATCH_FAILURE" if events else "NO_OPEN_LIVE_MARKETS"
    elif not all_pairs:
        base["state"] = "NO_VERIFIED_PAIRS"
    else:
        base["state"] = "CONNECTED"
    return base


def clear_cache():
    try:
        _fetch_live_events.clear()
    except Exception:
        pass


__all__ = [
    "MODEL_VERSION",
    "FRESH_SECONDS",
    "STALE_SECONDS",
    "MAX_PAIR_SKEW_SECONDS",
    "MAX_STATE_LAG_SECONDS",
    "market_snapshot_for_live_games",
    "parse_event_pairs",
    "clear_cache",
]
