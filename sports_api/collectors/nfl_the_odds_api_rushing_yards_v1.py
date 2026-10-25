"""Field-specific The Odds API fallback for NFL Rushing Yards.

This collector is backend-only. Kyre Sports API remains the application-facing
gateway. It exact-matches one already-canonical NFL game by away/home teams,
requests only the standard ``player_rush_yds`` market, preserves one underlying
sportsbook quote per player, and never invents team/position/value metadata.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import re
from typing import Any, Mapping

import requests

MODEL_VERSION = "NFL RUSHING YARDS THE ODDS API FALLBACK V1"
THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4"
MARKET_KEY = "player_rush_yds"
MAX_MARKET_AGE_SECONDS = 1800
BOOK_PRIORITY = (
    "FanDuel",
    "DraftKings",
    "BetMGM",
    "Caesars",
    "bet365",
    "Fanatics Sportsbook",
)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).casefold()).strip()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _api_key() -> str:
    for name in ("THE_ODDS_API_KEY", "KYRE_THE_ODDS_API_KEY", "ODDS_API_KEY"):
        value = _text(os.environ.get(name))
        if value:
            return value
    return ""


def _book_name(key: Any, title: Any = None) -> str:
    normalized = _text(key).casefold()
    mapping = {
        "fanduel": "FanDuel",
        "draftkings": "DraftKings",
        "betmgm": "BetMGM",
        "williamhill_us": "Caesars",
        "caesars": "Caesars",
        "bet365": "bet365",
        "bet365_nj": "bet365",
        "fanatics": "Fanatics Sportsbook",
        "fanaticssportsbook": "Fanatics Sportsbook",
    }
    return mapping.get(normalized) or _text(title) or _text(key)


def _state(state: str, *, observations: list[dict[str, Any]] | None = None, reason: str = "", evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "state": _text(state).upper(),
        "observations": list(observations or []),
        "reason": _text(reason),
        "evidence": dict(evidence or {}),
        "fabricated": False,
    }


def _parse_stamp(value: Any) -> datetime | None:
    text = _text(value).replace("Z", "+00:00")
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)


def _get_json(url: str, *, params: Mapping[str, Any], timeout: int) -> tuple[Any | None, str | None]:
    try:
        response = requests.get(
            url,
            params=dict(params),
            timeout=max(1, int(timeout)),
            headers={"Accept": "application/json", "User-Agent": "KyreSportsAPI-NFL-Step2D/1.0"},
        )
        response.raise_for_status()
    except Exception as exc:
        return None, f"{type(exc).__name__}: {_text(exc)}"[:300]
    try:
        return response.json(), None
    except Exception as exc:
        return None, f"JSON {type(exc).__name__}: {_text(exc)}"[:300]


def _event_match(events: Any, game: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(events, list):
        return None
    away = _norm(game.get("away_name"))
    home = _norm(game.get("home_name"))
    if not away or not home:
        return None
    matches = [
        row for row in events
        if isinstance(row, Mapping)
        and _norm(row.get("away_team")) == away
        and _norm(row.get("home_team")) == home
    ]
    return dict(matches[0]) if len(matches) == 1 else None


def _fresh_rows(payload: Mapping[str, Any], *, now_utc: datetime) -> tuple[list[dict[str, Any]], bool]:
    candidates: list[dict[str, Any]] = []
    saw_timestamp_problem = False
    priority = {name: index for index, name in enumerate(BOOK_PRIORITY)}

    for bookmaker in payload.get("bookmakers") or []:
        if not isinstance(bookmaker, Mapping):
            continue
        sportsbook = _book_name(bookmaker.get("key"), bookmaker.get("title"))
        if sportsbook not in priority:
            continue
        for market in bookmaker.get("markets") or []:
            if not isinstance(market, Mapping) or _text(market.get("key")) != MARKET_KEY:
                continue
            stamp_text = _text(market.get("last_update") or bookmaker.get("last_update"))
            stamp = _parse_stamp(stamp_text)
            if stamp is None:
                saw_timestamp_problem = True
                continue
            age = (now_utc - stamp).total_seconds()
            if age < -60 or age > MAX_MARKET_AGE_SECONDS:
                saw_timestamp_problem = True
                continue
            grouped: dict[tuple[str, float], dict[str, Any]] = {}
            for outcome in market.get("outcomes") or []:
                if not isinstance(outcome, Mapping):
                    continue
                player_name = _text(outcome.get("description"))
                side = _text(outcome.get("name")).casefold()
                line = _num(outcome.get("point"))
                price = _num(outcome.get("price"))
                if not player_name or side not in {"over", "under"} or line is None or price is None:
                    continue
                row = grouped.setdefault((player_name, line), {
                    "player_name": player_name,
                    "sportsbook": sportsbook,
                    "market": "Rushing Yards",
                    "line": line,
                    "source_timestamp": stamp.isoformat(),
                    "source_provider": "The Odds API",
                    "provider_event_id": _text(payload.get("id")),
                })
                row[f"{side}_odds"] = price
            for row in grouped.values():
                if row.get("over_odds") is not None and row.get("under_odds") is not None:
                    candidates.append(row)

    # One exact quote per player. Do not average books or manufacture consensus.
    candidates.sort(key=lambda row: (priority.get(_text(row.get("sportsbook")), 999), _norm(row.get("player_name"))))
    selected: dict[str, dict[str, Any]] = {}
    for row in candidates:
        key = _norm(row.get("player_name"))
        if key and key not in selected:
            selected[key] = dict(row)
    return list(selected.values()), saw_timestamp_problem


def collect_the_odds_api_game_markets(game: Mapping[str, Any], *, timeout: int = 8) -> dict[str, Any]:
    """Return structured Step-2D observations for one exact NFL event."""
    key = _api_key()
    if not key:
        return _state(
            "ALL_SOURCES_UNAVAILABLE",
            reason="The Odds API credential is not configured in the Kyre Sports API runtime",
            evidence={"configured": False, "market_key": MARKET_KEY},
        )

    events, error = _get_json(
        f"{THE_ODDS_API_BASE}/sports/americanfootball_nfl/events",
        params={"apiKey": key, "dateFormat": "iso"},
        timeout=timeout,
    )
    if error:
        return _state("PROVIDER_FETCH_FAILURE", reason=error, evidence={"stage": "events", "market_key": MARKET_KEY})
    if not isinstance(events, list):
        return _state("PARSER_FAILURE", reason="The Odds API events response is not a list", evidence={"stage": "events"})

    event = _event_match(events, game)
    if event is None:
        return _state(
            "EVENT_MAPPING_FAILURE",
            reason="The Odds API did not yield exactly one exact home/away event match",
            evidence={"event_match": "failed_exact_home_away", "market_key": MARKET_KEY},
        )
    event_id = _text(event.get("id"))
    if not event_id:
        return _state("EVENT_MAPPING_FAILURE", reason="exact event match had no provider event id")

    payload, error = _get_json(
        f"{THE_ODDS_API_BASE}/sports/americanfootball_nfl/events/{event_id}/odds",
        params={
            "apiKey": key,
            "regions": "us",
            "markets": MARKET_KEY,
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=timeout,
    )
    if error:
        return _state(
            "PROVIDER_FETCH_FAILURE",
            reason=error,
            evidence={"stage": "event_odds", "provider_event_id": event_id, "event_match": "exact_home_away"},
        )
    if not isinstance(payload, Mapping):
        return _state("PARSER_FAILURE", reason="The Odds API event odds response is not an object", evidence={"provider_event_id": event_id})

    now = datetime.now(timezone.utc)
    observations, timestamp_problem = _fresh_rows(payload, now_utc=now)
    evidence = {
        "configured": True,
        "event_match": "exact_home_away",
        "provider_event_id": event_id,
        "market_key": MARKET_KEY,
        "sportsbook_line_averaging": False,
    }
    if observations:
        return _state("AVAILABLE", observations=observations, evidence=evidence)
    if timestamp_problem:
        return _state("STALE_DATA", reason="The Odds API rushing-yard observations were missing/stale", evidence=evidence)
    return _state(
        "VERIFIED_NOT_POSTED",
        reason="exact event payload parsed successfully with no fresh complete player_rush_yds quote",
        evidence=evidence,
    )


__all__ = [
    "BOOK_PRIORITY",
    "MARKET_KEY",
    "MAX_MARKET_AGE_SECONDS",
    "MODEL_VERSION",
    "THE_ODDS_API_BASE",
    "collect_the_odds_api_game_markets",
]
