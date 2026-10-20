"""NBA Spread sportsbook observations V3 — richer multi-book market intelligence.

Additive successor to V2. V3 keeps exact frozen schedule identity and the same
fail-closed freshness rules, expands the requested major-book set, and requests
SportsGameOdds open/close fields so Page 1 can display real open-to-current
movement when the provider returns it. Sportsbook data remains read-only market
context and never participates in projection math.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import math
import os
from typing import Any, Callable, Mapping, Sequence

import requests

import nba_spread_sportsbook_observations_v2 as prior

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAX_MARKET_AGE_SECONDS = prior.MAX_MARKET_AGE_SECONDS
INCLUDE_OPEN_CLOSE_ODDS = True
ELIGIBLE_STATES = prior.ELIGIBLE_STATES
SGO_EVENTS_URL = prior.SGO_EVENTS_URL
SGO_SPREAD_ODD_IDS = prior.SGO_SPREAD_ODD_IDS
DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,caesars,pinnacle,espnbet,fanatics,bet365"
BOOK_NAMES = {
    **prior.BOOK_NAMES,
    "pinnacle": "Pinnacle",
}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _american_price(value: object) -> int | None:
    parsed = _number(value)
    if parsed is None or abs(parsed) < 100 or abs(parsed) > 100000:
        return None
    rounded = int(round(parsed))
    return rounded if math.isclose(parsed, rounded, abs_tol=1e-9) else None


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


def _single_consistent_quote(quotes: Sequence[Mapping[str, object]]) -> dict[str, object] | None:
    if not quotes:
        return None
    spreads = {_number(item.get("spread")) for item in quotes}
    if None in spreads or len(spreads) != 1:
        return None
    ordered = sorted(
        (dict(item) for item in quotes),
        key=lambda item: _as_utc(item.get("observed_at_utc")) or datetime.min.replace(tzinfo=timezone.utc),
    )
    return ordered[-1]


def _paired_optional(away: object, home: object) -> tuple[float | None, float | None]:
    a = _number(away)
    h = _number(home)
    if a is None or h is None or not math.isclose(a + h, 0.0, abs_tol=1e-9):
        return None, None
    return float(a), float(h)


def normalize_sportsgameodds_spread_observations_v3(
    events: Sequence[Mapping[str, Any]],
    schedule_games: Sequence[Mapping[str, object]],
    *,
    retrieved_at_utc: str,
) -> list[dict[str, object]]:
    """Normalize exact schedule-matched, paired current/open spread quotes."""
    retrieved = _as_utc(retrieved_at_utc)
    if retrieved is None:
        raise ValueError("retrieved_at_utc must be an ISO-8601 timestamp")
    retrieved_text = _iso_utc(retrieved)
    schedule_index = prior._schedule_matches(schedule_games)
    rows: list[dict[str, object]] = []

    for event in events:
        if not isinstance(event, Mapping):
            continue
        league = _clean(event.get("leagueID")).upper()
        if league and league != "NBA":
            continue
        game = prior._resolve_game(event, schedule_index)
        if game is None:
            continue

        quotes: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(lambda: {"away": [], "home": []})
        odds = event.get("odds") or {}
        if not isinstance(odds, Mapping):
            continue
        for odd in odds.values():
            if not isinstance(odd, Mapping):
                continue
            if _clean(odd.get("periodID")).lower() != "game":
                continue
            if _clean(odd.get("betTypeID")).lower() not in {"sp", "spread"}:
                continue
            side = _clean(odd.get("sideID")).lower()
            if side not in {"away", "home"}:
                continue
            books = odd.get("byBookmaker") or {}
            if not isinstance(books, Mapping):
                continue
            for raw_book_id, raw_book in books.items():
                if not isinstance(raw_book, Mapping) or raw_book.get("available") is False:
                    continue
                spread = _number(raw_book.get("spread"))
                if spread is None:
                    continue
                book_id = _clean(raw_book_id).lower()
                if not book_id:
                    continue
                observed = _clean(raw_book.get("lastUpdatedAt")) or None
                if observed and _as_utc(observed) is None:
                    observed = None
                quotes[book_id][side].append(
                    {
                        "spread": float(spread),
                        "price": _american_price(raw_book.get("odds")),
                        "open_spread": _number(raw_book.get("openSpread")),
                        "close_spread": _number(raw_book.get("closeSpread")),
                        "open_price": _american_price(raw_book.get("openOdds")),
                        "close_price": _american_price(raw_book.get("closeOdds")),
                        "observed_at_utc": observed,
                    }
                )

        for book_id in sorted(quotes):
            away = _single_consistent_quote(quotes[book_id]["away"])
            home = _single_consistent_quote(quotes[book_id]["home"])
            if away is None or home is None:
                continue
            away_spread = float(away["spread"])
            home_spread = float(home["spread"])
            if not math.isclose(away_spread + home_spread, 0.0, abs_tol=1e-9):
                continue
            open_away, open_home = _paired_optional(away.get("open_spread"), home.get("open_spread"))
            close_away, close_home = _paired_optional(away.get("close_spread"), home.get("close_spread"))
            timestamps = [
                parsed
                for parsed in (_as_utc(away.get("observed_at_utc")), _as_utc(home.get("observed_at_utc")))
                if parsed is not None
            ]
            observed_at = _iso_utc(min(timestamps)) if timestamps else None
            rows.append(
                {
                    "game_key": game["game_key"],
                    "game_date_phoenix": game["game_date_phoenix"],
                    "away_tricode": game["away_tricode"],
                    "home_tricode": game["home_tricode"],
                    "sportsbook": BOOK_NAMES.get(book_id, book_id.replace("_", " ").title()),
                    "sportsbook_id": book_id,
                    "away_spread": away_spread,
                    "home_spread": home_spread,
                    "away_price": away.get("price"),
                    "home_price": home.get("price"),
                    "open_away_spread": open_away,
                    "open_home_spread": open_home,
                    "open_away_price": away.get("open_price"),
                    "open_home_price": home.get("open_price"),
                    "close_away_spread": close_away,
                    "close_home_spread": close_home,
                    "close_away_price": away.get("close_price"),
                    "close_home_price": home.get("close_price"),
                    "observed_at_utc": observed_at,
                    "retrieved_at_utc": retrieved_text,
                    "source_transport": "SportsGameOdds",
                }
            )
    return rows


def _default_secret_getter(name: str) -> str | None:
    return os.getenv(name)


def load_verified_sportsbook_observations_v3(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    secret_getter: Callable[[str], str | None] = _default_secret_getter,
    request_get: Callable[..., Any] = requests.get,
    now_utc: datetime | None = None,
    bookmakers: str = DEFAULT_BOOKMAKERS,
    timeout: float = 12.0,
) -> dict[str, object]:
    key = _clean(secret_getter("SPORTSGAMEODDS_API_KEY"))
    base: dict[str, object] = {
        "source": "SportsGameOdds",
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "max_market_age_seconds": MAX_MARKET_AGE_SECONDS,
        "include_open_close_odds": INCLUDE_OPEN_CLOSE_ODDS,
        "requested_bookmakers": bookmakers,
    }
    if not key:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE"}

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    params = {
        "leagueID": "NBA",
        "oddID": SGO_SPREAD_ODD_IDS,
        "bookmakerID": bookmakers,
        "oddsAvailable": "true",
        "includeOpenCloseOdds": "true",
        "limit": 100,
    }
    try:
        response = request_get(SGO_EVENTS_URL, params=params, headers={"x-api-key": key}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": f"SPORTSGAMEODDS_PROVIDER_ERROR:{type(exc).__name__}"}

    events = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(events, list):
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "SPORTSGAMEODDS_INVALID_PAYLOAD"}

    retrieved = _iso_utc(now)
    observations = normalize_sportsgameodds_spread_observations_v3(events, schedule_games, retrieved_at_utc=retrieved)
    if not observations:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "SPORTSGAMEODDS_NO_VERIFIED_SPREAD_PAIRS"}

    fresh: list[dict[str, object]] = []
    stale_count = 0
    for row in observations:
        observed = _as_utc(row.get("observed_at_utc")) or _as_utc(row.get("retrieved_at_utc"))
        age = (now - observed).total_seconds() if observed is not None else None
        if age is None or age < -30 or age > MAX_MARKET_AGE_SECONDS:
            stale_count += 1
            continue
        fresh.append(row)
    if not fresh:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "SPORTSGAMEODDS_STALE_MARKET", "stale_observation_count": stale_count}

    return {
        **base,
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "observations": fresh,
        "stale_observation_count": stale_count,
        "retrieved_at_utc": retrieved,
        "sportsbook_count": len({_clean(row.get("sportsbook")).casefold() for row in fresh if _clean(row.get("sportsbook"))}),
    }


__all__ = [
    "BOOK_NAMES",
    "DEFAULT_BOOKMAKERS",
    "INCLUDE_OPEN_CLOSE_ODDS",
    "MAX_MARKET_AGE_SECONDS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "load_verified_sportsbook_observations_v3",
    "normalize_sportsgameodds_spread_observations_v3",
]
