"""Smart Live market policy for NFL Daily Picks V4.

This module never alters model projections or probabilities.  It owns only:
- adaptive page refresh cadence,
- stable NFL team logo identity,
- exact-pair SportsGameOdds in-play display transport,
- a fail-closed live quote firewall, and
- session-local line movement history.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Iterable, Mapping, MutableMapping

import requests

try:
    import streamlit as st
except Exception:  # pragma: no cover - import guard for non-UI tests
    st = None

import nfl_moneyline_market_v1 as nfl_sgo
from nfl_prop_analytics_schedule_v1 import _canon_team, team_logo_url as _team_logo_url

MODEL_VERSION = "NFL DAILY PICKS SMART LIVE V4 • EXACT-PAIR DISPLAY TRANSPORT"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PREGAME_REFRESH_SECONDS = 45
LIVE_REFRESH_SECONDS = 20
IDLE_REFRESH_SECONDS = 120
LIVE_FETCH_TTL_SECONDS = 8
LIVE_QUOTE_FRESH_SECONDS = 75
LIVE_QUOTE_STALE_SECONDS = 120
MAX_PAIR_SKEW_SECONDS = 60
MAX_HISTORY_POINTS = 12

TEAM_ODD_IDS = (
    "points-away-game-ml-away",
    "points-home-game-ml-home",
    "points-away-game-sp-away",
    "points-home-game-sp-home",
    "points-all-game-ou-over",
    "points-all-game-ou-under",
)


def _state(value: Any) -> str:
    raw = str(value or "scheduled").strip().lower()
    if raw in {"in", "live", "in_progress", "in-progress"}:
        return "live"
    if raw in {"post", "final", "completed", "complete"}:
        return "final"
    return "scheduled"


def smart_refresh_seconds(game_states: Iterable[Any]) -> int:
    states = {_state(value) for value in game_states}
    if "live" in states:
        return LIVE_REFRESH_SECONDS
    if "scheduled" in states:
        return PREGAME_REFRESH_SECONDS
    return IDLE_REFRESH_SECONDS


def nfl_team_logo_url(team: Any) -> str:
    """Reuse the existing canonical NFL identity/logo resolver."""
    return _team_logo_url(team)


def matchup_teams(matchup: Any) -> tuple[str, str]:
    text = str(matchup or "").strip()
    lowered = text.lower()
    for marker in (" at ", " @ ", " vs. ", " vs "):
        if marker in lowered:
            idx = lowered.index(marker)
            away = _canon_team(text[:idx].strip())
            home = _canon_team(text[idx + len(marker):].strip())
            return away, home
    parts = [part for part in text.replace("@", " ").split() if part]
    if len(parts) >= 2:
        return _canon_team(parts[0]), _canon_team(parts[-1])
    canonical = _canon_team(text)
    return canonical, ""


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _row_age(row: Mapping[str, Any], now_utc: datetime) -> float | None:
    direct = _finite_number(row.get("age_seconds"))
    if direct is not None and direct >= 0:
        return direct
    updated = row.get("updated_at")
    if not updated:
        return None
    try:
        if isinstance(updated, datetime):
            dt = updated
        else:
            dt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now_utc - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return None


def live_market_firewall(
    game_state: Any,
    observations: Iterable[Mapping[str, Any]],
    *,
    game_id: str,
    now_utc: datetime,
) -> dict[str, Any]:
    """Return only explicitly certified fresh in-play observations for live games."""
    state = _state(game_state)
    rows = tuple(dict(row) for row in observations if str(row.get("game_id")) == str(game_id))
    if state != "live":
        return {
            "state": state,
            "label": "PREGAME MARKET" if state == "scheduled" else "MARKET CLOSED",
            "model_label": "MODEL",
            "observations": tuple(row for row in rows if row.get("verified") is True),
        }
    accepted = []
    for row in rows:
        age = _row_age(row, now_utc)
        if row.get("verified") is not True or row.get("live_verified") is not True:
            continue
        if age is None or age > LIVE_QUOTE_FRESH_SECONDS:
            continue
        clean = dict(row)
        clean["age_seconds"] = age
        accepted.append(clean)
    return {
        "state": "live",
        "label": "LIVE MARKET VERIFIED" if accepted else "LIVE ODDS UNAVAILABLE",
        "model_label": "PREGAME MODEL",
        "observations": tuple(accepted),
    }


_HISTORY_KEY = "nfl_daily_picks_v4_session_line_history"


def _history_key(row: Mapping[str, Any]) -> str:
    return "|".join(
        str(row.get(field) or "").strip().upper()
        for field in ("game_id", "market_id", "side", "book")
    )


def update_session_line_history(
    session_state: MutableMapping[str, Any],
    observations: Iterable[Mapping[str, Any]],
    *,
    now_utc: datetime,
) -> None:
    bucket = session_state.setdefault(_HISTORY_KEY, {})
    for raw in observations:
        row = dict(raw)
        if row.get("verified") is not True:
            continue
        key = _history_key(row)
        if not key.strip("|"):
            continue
        point = {
            "line": _finite_number(row.get("line")),
            "price": _finite_number(row.get("price")),
            "at": now_utc.astimezone(timezone.utc).isoformat(),
        }
        history = list(bucket.get(key) or [])
        if history and history[-1].get("line") == point["line"] and history[-1].get("price") == point["price"]:
            continue
        history.append(point)
        bucket[key] = history[-MAX_HISTORY_POINTS:]


def session_line_history(session_state: Mapping[str, Any], observation: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    bucket = dict(session_state.get(_HISTORY_KEY) or {})
    return tuple(dict(point) for point in tuple(bucket.get(_history_key(observation)) or ()))


def session_line_movement(history: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    points = tuple(dict(point) for point in history)
    if len(points) < 2:
        return {"ready": False, "scope": "SESSION", "reason": "NO_SESSION_CHANGE_YET"}
    previous = _finite_number(points[-2].get("line"))
    current = _finite_number(points[-1].get("line"))
    if previous is None or current is None:
        return {"ready": False, "scope": "SESSION", "reason": "LINE_NOT_NUMERIC"}
    return {
        "ready": True,
        "scope": "SESSION",
        "previous_line": previous,
        "current_line": current,
        "delta": current - previous,
        "previous_at": points[-2].get("at"),
        "current_at": points[-1].get("at"),
    }


def _book_id(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _book_name(value: Any) -> str:
    key = _book_id(value)
    return getattr(nfl_sgo, "_BOOKS", {}).get(key, str(value))


def _american(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(round(float(str(value).replace(",", ""))))
    except Exception:
        return None


def _iso_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _fetch_live_events_uncached(api_key: str, starts_after: str, starts_before: str, bookmakers: str):
    params = {
        "leagueID": "NFL",
        "oddsAvailable": "true",
        "startsAfter": starts_after,
        "startsBefore": starts_before,
        "oddID": ",".join(TEAM_ODD_IDS),
        "bookmakerID": bookmakers,
        "includeAltLines": "false",
        "limit": 50,
    }
    headers = {"x-api-key": str(api_key), "Cache-Control": "no-cache"}
    response = requests.get(f"{nfl_sgo.SGO_BASE}/events", params=params, headers=headers, timeout=20)
    if response.status_code in {400, 504}:
        params.pop("oddID", None)
        response = requests.get(f"{nfl_sgo.SGO_BASE}/events", params=params, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    return []


if st is not None:
    _fetch_live_events = st.cache_data(ttl=LIVE_FETCH_TTL_SECONDS, show_spinner=False, max_entries=8)(_fetch_live_events_uncached)
else:  # pragma: no cover
    _fetch_live_events = _fetch_live_events_uncached


def _event_canon(event: Mapping[str, Any], side: str) -> str:
    try:
        return _canon_team(nfl_sgo._sgo_team(event, side))
    except Exception:
        return ""


def _match_live_event(events: Iterable[Mapping[str, Any]], matchup: Any):
    away, home = matchup_teams(matchup)
    for event in events:
        if _event_canon(event, "away") == away and _event_canon(event, "home") == home:
            return event
    return None


def _parse_exact_live_pairs(event: Mapping[str, Any], game_id: str, now_utc: datetime) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    odds = (event or {}).get("odds") or {}
    if not isinstance(odds, dict):
        return []
    for odd in odds.values():
        if not isinstance(odd, dict) or str(odd.get("periodID") or "").lower() != "game":
            continue
        stat_entity = str(odd.get("statEntityID") or "").lower()
        bet_type = str(odd.get("betTypeID") or "").lower()
        side = str(odd.get("sideID") or "").lower()
        if bet_type == "ml" and side in {"away", "home"}:
            market_id = "moneyline"
            line_field = None
        elif bet_type == "sp" and side in {"away", "home"}:
            market_id = "spread"
            line_field = "spread"
        elif bet_type == "ou" and stat_entity == "all" and side in {"over", "under"}:
            market_id = "game-total"
            line_field = "overUnder"
        else:
            continue
        by_book = odd.get("byBookmaker") or {}
        if not isinstance(by_book, dict):
            continue
        for raw_book, data in by_book.items():
            if not isinstance(data, dict) or data.get("available") is False:
                continue
            book = _book_name(raw_book)
            updated = _iso_dt(data.get("lastUpdatedAt"))
            groups.setdefault((book, market_id), {})[side] = {
                "price": _american(data.get("odds")),
                "line": _finite_number(data.get(line_field)) if line_field else None,
                "updated_at": updated,
            }
    required = {
        "moneyline": ("away", "home"),
        "spread": ("away", "home"),
        "game-total": ("over", "under"),
    }
    rows: list[dict[str, Any]] = []
    for (book, market_id), sides in groups.items():
        left_name, right_name = required[market_id]
        if left_name not in sides or right_name not in sides:
            continue
        left, right = sides[left_name], sides[right_name]
        timestamps = [left.get("updated_at"), right.get("updated_at")]
        if any(ts is None for ts in timestamps):
            ages = [None, None]
            skew = None
            pair_ok = False
        else:
            ages = [max(0.0, (now_utc - ts).total_seconds()) for ts in timestamps]
            skew = abs((timestamps[0] - timestamps[1]).total_seconds())
            pair_ok = max(ages) <= LIVE_QUOTE_FRESH_SECONDS and skew <= MAX_PAIR_SKEW_SECONDS
        for side_name, payload, age in ((left_name, left, ages[0]), (right_name, right, ages[1])):
            rows.append(
                {
                    "game_id": str(game_id),
                    "market_id": market_id,
                    "side": side_name.upper(),
                    "book": book,
                    "price": payload.get("price"),
                    "line": payload.get("line"),
                    "updated_at": payload.get("updated_at"),
                    "age_seconds": age,
                    "verified": bool(pair_ok),
                    "live_verified": bool(pair_ok),
                    "provider": "SportsGameOdds",
                    "pair_skew_seconds": skew,
                    "pair_status": "LIVE_EXACT_PAIR" if pair_ok else "LIVE_PAIR_NOT_FRESH",
                }
            )
    return rows


def fetch_live_market_observations(
    game_states: Mapping[str, Mapping[str, Any]],
    *,
    day_str: str,
    now_utc: datetime,
) -> tuple[dict[str, Any], ...]:
    """Fetch exact-pair SGO quotes only for games the official slate says are live."""
    live_games = {
        str(game_id): dict(payload or {})
        for game_id, payload in dict(game_states or {}).items()
        if _state((payload or {}).get("state")) == "live"
    }
    if not live_games:
        return ()
    try:
        api_key = nfl_sgo.get_sgo_api_key()
        bookmakers = nfl_sgo.get_sgo_bookmakers()
        if not api_key or not bookmakers:
            return ()
        starts_after, starts_before = nfl_sgo._slate_window(day_str)
        events = _fetch_live_events(api_key, starts_after, starts_before, bookmakers)
    except Exception:
        return ()
    out: list[dict[str, Any]] = []
    for game_id, payload in live_games.items():
        event = _match_live_event(events, payload.get("matchup"))
        if event is None:
            continue
        out.extend(_parse_exact_live_pairs(event, game_id, now_utc))
    return tuple(out)


__all__ = [
    "IDLE_REFRESH_SECONDS",
    "LIVE_FETCH_TTL_SECONDS",
    "LIVE_QUOTE_FRESH_SECONDS",
    "LIVE_QUOTE_STALE_SECONDS",
    "LIVE_REFRESH_SECONDS",
    "MODEL_VERSION",
    "PREGAME_REFRESH_SECONDS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "fetch_live_market_observations",
    "live_market_firewall",
    "matchup_teams",
    "nfl_team_logo_url",
    "session_line_history",
    "session_line_movement",
    "smart_refresh_seconds",
    "update_session_line_history",
]
