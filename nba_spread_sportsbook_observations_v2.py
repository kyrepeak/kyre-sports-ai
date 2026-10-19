"""NBA Spread verified sportsbook observations V2.

Additive successor to the frozen V1 SportsGameOdds transport. V2 enriches exact
schedule-matched spread observations with game identity, validated American
prices, timestamps, freshness, and conflict rejection. It never participates in
projection/model math.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import math
import os
from typing import Any, Callable, Mapping, Sequence

import requests

from nba_spread_sportsbook_observations_v1 import (
    BOOK_NAMES,
    DEFAULT_BOOKMAKERS,
    SGO_EVENTS_URL,
    SGO_SPREAD_ODD_IDS,
)

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAX_MARKET_AGE_SECONDS = 300
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _norm_team(value: object) -> str:
    return "".join(ch for ch in _clean(value).casefold() if ch.isalnum())


def _team_name(event: Mapping[str, Any], side: str) -> str:
    team = ((event.get("teams") or {}).get(side) or {})
    names = team.get("names") or {}
    for field in ("long", "display", "medium", "short"):
        value = names.get(field)
        if value:
            return _clean(value)
    return _clean(team.get("name") or team.get("fullName") or team.get("teamName"))


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
    if abs(parsed - rounded) > 1e-9:
        return None
    return rounded


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


def _schedule_matches(schedule_games: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    matches: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for raw in schedule_games:
        if _clean(raw.get("status")).upper() not in ELIGIBLE_STATES:
            continue
        away_code = _clean(raw.get("away_tricode")).upper()
        home_code = _clean(raw.get("home_tricode")).upper()
        away_name = _norm_team(raw.get("away_name") or away_code)
        home_name = _norm_team(raw.get("home_name") or home_code)
        game_key = _clean(raw.get("game_key"))
        date = _clean(raw.get("game_date_phoenix"))
        if away_code and home_code and away_name and home_name and game_key and date:
            matches[(away_name, home_name)].append(
                {
                    "game_key": game_key,
                    "game_date_phoenix": date,
                    "away_tricode": away_code,
                    "home_tricode": home_code,
                }
            )
    return matches


def _event_date(event: Mapping[str, Any]) -> str | None:
    for field in ("startTime", "startsAt", "scheduled", "scheduledAt", "startDate"):
        parsed = _as_utc(event.get(field))
        if parsed is not None:
            from datetime import timedelta
            return (parsed - timedelta(hours=7)).date().isoformat()
    return None


def _resolve_game(event: Mapping[str, Any], schedule_index: Mapping[tuple[str, str], list[dict[str, str]]]) -> dict[str, str] | None:
    key = (_norm_team(_team_name(event, "away")), _norm_team(_team_name(event, "home")))
    candidates = list(schedule_index.get(key) or [])
    if not candidates:
        return None
    event_date = _event_date(event)
    if event_date:
        candidates = [item for item in candidates if item["game_date_phoenix"] == event_date]
    return candidates[0] if len(candidates) == 1 else None


def _single_consistent_quote(quotes: Sequence[Mapping[str, object]]) -> dict[str, object] | None:
    if not quotes:
        return None
    spreads = {float(item["spread"]) for item in quotes}
    if len(spreads) != 1:
        return None
    ordered = sorted(
        (dict(item) for item in quotes),
        key=lambda item: _as_utc(item.get("observed_at_utc")) or datetime.min.replace(tzinfo=timezone.utc),
    )
    return ordered[-1]


def normalize_sportsgameodds_spread_observations_v2(
    events: Sequence[Mapping[str, Any]],
    schedule_games: Sequence[Mapping[str, object]],
    *,
    retrieved_at_utc: str,
) -> list[dict[str, object]]:
    """Normalize exact, paired SportsGameOdds spread observations.

    The same-book same-side spread must be unambiguous. Any conflicting spread
    records cause that book/game to be rejected rather than averaged.
    """
    retrieved = _as_utc(retrieved_at_utc)
    if retrieved is None:
        raise ValueError("retrieved_at_utc must be an ISO-8601 timestamp")
    retrieved_text = _iso_utc(retrieved)
    schedule_index = _schedule_matches(schedule_games)
    rows: list[dict[str, object]] = []

    for event in events:
        if not isinstance(event, Mapping):
            continue
        league = _clean(event.get("leagueID")).upper()
        if league and league != "NBA":
            continue
        game = _resolve_game(event, schedule_index)
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
                        "spread": spread,
                        "price": _american_price(raw_book.get("odds")),
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
                    "away_spread": away_spread,
                    "home_spread": home_spread,
                    "away_price": away.get("price"),
                    "home_price": home.get("price"),
                    "observed_at_utc": observed_at,
                    "retrieved_at_utc": retrieved_text,
                    "source_transport": "SportsGameOdds",
                }
            )
    return rows


def _default_secret_getter(name: str) -> str | None:
    return os.getenv(name)


def _row_age_seconds(row: Mapping[str, object], now_utc: datetime) -> float | None:
    observed = _as_utc(row.get("observed_at_utc")) or _as_utc(row.get("retrieved_at_utc"))
    if observed is None:
        return None
    return (now_utc - observed).total_seconds()


def load_verified_sportsbook_observations_v2(
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
    observations = normalize_sportsgameodds_spread_observations_v2(events, schedule_games, retrieved_at_utc=retrieved)
    if not observations:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "SPORTSGAMEODDS_NO_VERIFIED_SPREAD_PAIRS"}

    fresh: list[dict[str, object]] = []
    stale_count = 0
    for row in observations:
        age = _row_age_seconds(row, now)
        if age is None or age < -30 or age > MAX_MARKET_AGE_SECONDS:
            stale_count += 1
            continue
        fresh.append(row)
    if not fresh:
        return {
            **base,
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SPORTSGAMEODDS_STALE_MARKET",
            "stale_observation_count": stale_count,
        }
    return {
        **base,
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "observations": fresh,
        "stale_observation_count": stale_count,
        "retrieved_at_utc": retrieved,
    }


__all__ = [
    "MAX_MARKET_AGE_SECONDS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "load_verified_sportsbook_observations_v2",
    "normalize_sportsgameodds_spread_observations_v2",
]
