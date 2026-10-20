"""Verified Odds-API.io NBA spread observations for Page-1 market gap fill.

This transport is additive market context only. It exact-matches the already
verified NBA schedule, normalizes full-game spreads into the same row contract
as SportsGameOdds, and fails closed on missing identity, lines, prices or stale
quotes. It never changes model/projection/probability/ranking behavior.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import re
from typing import Any, Callable, Mapping, Sequence

import requests

ODDS_API_BASE = "https://api.odds-api.io/v3"
DEFAULT_BOOKMAKERS = "DraftKings,FanDuel,BetMGM,Caesars,Pinnacle,ESPN BET,Fanatics,Bet365"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAX_MARKET_AGE_SECONDS = 300
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean(value).casefold())


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _as_utc(value: object) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _decimal_to_american(value: object) -> int | None:
    decimal = _number(value)
    if decimal is None or decimal <= 1.0:
        return None
    if decimal >= 2.0:
        return int(round((decimal - 1.0) * 100.0))
    return int(round(-100.0 / (decimal - 1.0)))


def _event_team(event: Mapping[str, Any], side: str) -> str:
    direct = event.get(side)
    if isinstance(direct, Mapping):
        for key in ("name", "displayName", "fullName", "shortName"):
            if direct.get(key):
                return _clean(direct.get(key))
    if direct:
        return _clean(direct)
    for key in (f"{side}Team", f"{side}_team", f"{side}Name"):
        value = event.get(key)
        if isinstance(value, Mapping):
            value = value.get("name") or value.get("displayName")
        if value:
            return _clean(value)
    return ""


def _schedule_index(schedule_games: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    out: dict[tuple[str, str], list[dict[str, str]]] = {}
    for raw in schedule_games:
        if _clean(raw.get("status")).upper() not in ELIGIBLE_STATES:
            continue
        away_name = _clean(raw.get("away_name") or raw.get("away_tricode"))
        home_name = _clean(raw.get("home_name") or raw.get("home_tricode"))
        key = (_norm(away_name), _norm(home_name))
        if not all(key):
            continue
        out.setdefault(key, []).append({
            "game_key": _clean(raw.get("game_key")),
            "game_date_phoenix": _clean(raw.get("game_date_phoenix")),
            "away_tricode": _clean(raw.get("away_tricode")).upper(),
            "home_tricode": _clean(raw.get("home_tricode")).upper(),
        })
    return out


def _same_team(a: str, b: str) -> bool:
    aa, bb = _norm(a), _norm(b)
    return bool(aa and bb and (aa == bb or aa in bb or bb in aa))


def _resolve_game(event: Mapping[str, Any], schedule_games: Sequence[Mapping[str, object]]) -> dict[str, str] | None:
    away = _event_team(event, "away")
    home = _event_team(event, "home")
    matches: list[dict[str, str]] = []
    for raw in schedule_games:
        if _clean(raw.get("status")).upper() not in ELIGIBLE_STATES:
            continue
        if _same_team(away, _clean(raw.get("away_name") or raw.get("away_tricode"))) and _same_team(home, _clean(raw.get("home_name") or raw.get("home_tricode"))):
            matches.append({
                "game_key": _clean(raw.get("game_key")),
                "game_date_phoenix": _clean(raw.get("game_date_phoenix")),
                "away_tricode": _clean(raw.get("away_tricode")).upper(),
                "home_tricode": _clean(raw.get("home_tricode")).upper(),
            })
    return matches[0] if len(matches) == 1 else None


def _events_from_payload(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(x) for x in payload if isinstance(x, Mapping)]
    if isinstance(payload, Mapping):
        rows = payload.get("data") or payload.get("events")
        if isinstance(rows, list):
            return [dict(x) for x in rows if isinstance(x, Mapping)]
    return []


def _odds_from_payload(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(x) for x in payload if isinstance(x, Mapping)]
    if isinstance(payload, Mapping):
        rows = payload.get("data")
        if isinstance(rows, list):
            return [dict(x) for x in rows if isinstance(x, Mapping)]
        if payload.get("id") is not None:
            return [dict(payload)]
    return []


def normalize_odds_api_spread_observations(
    odds_events: Sequence[Mapping[str, Any]],
    schedule_games: Sequence[Mapping[str, object]],
    *,
    retrieved_at_utc: str,
) -> list[dict[str, object]]:
    retrieved = _as_utc(retrieved_at_utc)
    if retrieved is None:
        raise ValueError("retrieved_at_utc must be ISO-8601")
    rows: list[dict[str, object]] = []
    for payload in odds_events:
        game = _resolve_game(payload, schedule_games)
        if game is None:
            continue
        bookmakers = payload.get("bookmakers") or {}
        if not isinstance(bookmakers, Mapping):
            continue
        for book_name, markets in bookmakers.items():
            if not isinstance(markets, Sequence) or isinstance(markets, (str, bytes)):
                continue
            for market in markets:
                if not isinstance(market, Mapping) or _clean(market.get("name")).casefold() != "spread":
                    continue
                odds = market.get("odds") or []
                first = odds[0] if isinstance(odds, Sequence) and not isinstance(odds, (str, bytes)) and odds and isinstance(odds[0], Mapping) else {}
                home_spread = _number(first.get("hdp"))
                if home_spread is None:
                    continue
                away_spread = -home_spread
                away_price = _decimal_to_american(first.get("away"))
                home_price = _decimal_to_american(first.get("home"))
                updated = _clean(market.get("updatedAt") or payload.get("updatedAt")) or None
                if updated and _as_utc(updated) is None:
                    updated = None
                rows.append({
                    **game,
                    "sportsbook": _clean(book_name),
                    "away_spread": float(away_spread),
                    "home_spread": float(home_spread),
                    "away_price": away_price,
                    "home_price": home_price,
                    "open_away_spread": None,
                    "open_home_spread": None,
                    "observed_at_utc": updated,
                    "retrieved_at_utc": _iso_utc(retrieved),
                    "source_transport": "Odds-API.io",
                })
                break
    return rows


def _default_secret_getter(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


def load_verified_odds_api_spread_observations(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    secret_getter: Callable[[str], str | None] = _default_secret_getter,
    request_get: Callable[..., Any] = requests.get,
    now_utc: datetime | None = None,
    bookmakers: str = DEFAULT_BOOKMAKERS,
    timeout: float = 12.0,
) -> dict[str, object]:
    key = _clean(secret_getter("ODDS_API_IO_KEY") or secret_getter("ODDS_API_KEY"))
    base: dict[str, object] = {
        "source": "Odds-API.io",
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }
    if not key:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "ODDS_API_IO_CREDENTIAL_UNAVAILABLE"}

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    try:
        event_response = request_get(
            f"{ODDS_API_BASE}/events",
            params={"apiKey": key, "sport": "nba", "status": "pending", "limit": 100},
            timeout=timeout,
        )
        event_response.raise_for_status()
        events = _events_from_payload(event_response.json())
    except Exception as exc:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": f"ODDS_API_IO_EVENTS_ERROR:{type(exc).__name__}"}

    matched_event_ids: list[str] = []
    for event in events:
        if _resolve_game(event, schedule_games) is not None and event.get("id") is not None:
            matched_event_ids.append(str(event.get("id")))
    if not matched_event_ids:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "ODDS_API_IO_NO_MATCHED_EVENTS"}

    odds_rows: list[dict[str, Any]] = []
    try:
        for start in range(0, len(matched_event_ids), 10):
            chunk = matched_event_ids[start:start + 10]
            response = request_get(
                f"{ODDS_API_BASE}/odds/multi",
                params={"apiKey": key, "eventIds": ",".join(chunk), "bookmakers": bookmakers, "markets": "Spread"},
                timeout=timeout,
            )
            response.raise_for_status()
            odds_rows.extend(_odds_from_payload(response.json()))
    except Exception as exc:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": f"ODDS_API_IO_ODDS_ERROR:{type(exc).__name__}"}

    retrieved = _iso_utc(now)
    normalized = normalize_odds_api_spread_observations(odds_rows, schedule_games, retrieved_at_utc=retrieved)
    fresh: list[dict[str, object]] = []
    stale_count = 0
    for row in normalized:
        observed = _as_utc(row.get("observed_at_utc")) or _as_utc(row.get("retrieved_at_utc"))
        age = (now - observed).total_seconds() if observed is not None else None
        if age is None or age < -30 or age > MAX_MARKET_AGE_SECONDS:
            stale_count += 1
            continue
        fresh.append(row)
    if not fresh:
        diagnostic = "ODDS_API_IO_STALE_MARKET" if stale_count else "ODDS_API_IO_NO_VERIFIED_SPREADS"
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": diagnostic, "stale_observation_count": stale_count}
    return {
        **base,
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "observations": fresh,
        "stale_observation_count": stale_count,
        "retrieved_at_utc": retrieved,
    }


__all__ = [
    "DEFAULT_BOOKMAKERS",
    "MAX_MARKET_AGE_SECONDS",
    "ODDS_API_BASE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "load_verified_odds_api_spread_observations",
    "normalize_odds_api_spread_observations",
]
