"""NBA Spread Step 1 — verified SportsGameOdds spread observation transport."""
from __future__ import annotations

import math
import os
from typing import Any, Callable, Mapping, Sequence

import requests

SGO_EVENTS_URL = "https://api.sportsgameodds.com/v2/events"
SGO_SPREAD_ODD_IDS = "points-away-game-sp-away,points-home-game-sp-home"
DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,caesars"
BOOK_NAMES = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "espnbet": "ESPN BET",
    "fanatics": "Fanatics",
    "bet365": "bet365",
}
ELIGIBLE_STATES = {"UPCOMING", "DELAYED"}


def _team_name(event: Mapping[str, Any], side: str) -> str:
    team = ((event.get("teams") or {}).get(side) or {})
    names = team.get("names") or {}
    for field in ("long", "display", "medium", "short"):
        value = names.get(field)
        if value:
            return str(value).strip()
    return str(team.get("name") or team.get("teamName") or "").strip()


def _norm_team(value: object) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _schedule_identity(schedule_games: Sequence[Mapping[str, object]]) -> dict[tuple[str, str], tuple[str, str]]:
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for game in schedule_games:
        if str(game.get("status") or "").upper() not in ELIGIBLE_STATES:
            continue
        away_code = str(game.get("away_tricode") or "").strip().upper()
        home_code = str(game.get("home_tricode") or "").strip().upper()
        away_name = _norm_team(game.get("away_name") or away_code)
        home_name = _norm_team(game.get("home_name") or home_code)
        if away_code and home_code and away_name and home_name:
            out[(away_name, home_name)] = (away_code, home_code)
    return out


def normalize_sportsgameodds_spread_observations(
    events: Sequence[Mapping[str, Any]],
    schedule_games: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    identities = _schedule_identity(schedule_games)
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        codes = identities.get((_norm_team(_team_name(event, "away")), _norm_team(_team_name(event, "home"))))
        if not codes:
            continue
        away_code, home_code = codes
        away_books: dict[str, float] = {}
        home_books: dict[str, float] = {}
        for odd in (event.get("odds") or {}).values():
            if not isinstance(odd, Mapping):
                continue
            if str(odd.get("periodID") or "").lower() != "game" or str(odd.get("betTypeID") or "").lower() not in {"sp", "spread"}:
                continue
            side = str(odd.get("sideID") or "").lower()
            if side not in {"away", "home"}:
                continue
            for book_id, book in (odd.get("byBookmaker") or {}).items():
                if not isinstance(book, Mapping) or book.get("available") is False:
                    continue
                spread = _number(book.get("spread"))
                if spread is None:
                    continue
                (away_books if side == "away" else home_books)[str(book_id).lower()] = spread
        for book_id in sorted(set(away_books) & set(home_books)):
            away_spread, home_spread = away_books[book_id], home_books[book_id]
            if abs(away_spread + home_spread) > 1e-9:
                continue
            key = (away_code, home_code, book_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "away_tricode": away_code,
                "home_tricode": home_code,
                "sportsbook": BOOK_NAMES.get(book_id, book_id.replace("_", " ").title()),
                "away_spread": away_spread,
                "home_spread": home_spread,
            })
    return rows


def _default_secret_getter(name: str) -> str | None:
    return os.getenv(name)


def load_verified_sportsbook_observations(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    secret_getter: Callable[[str], str | None] = _default_secret_getter,
    request_get: Callable[..., Any] = requests.get,
    bookmakers: str = DEFAULT_BOOKMAKERS,
    timeout: float = 12.0,
) -> dict[str, object]:
    key = (secret_getter("SPORTSGAMEODDS_API_KEY") or "").strip()
    base = {
        "source": "SportsGameOdds",
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
    }
    if not key:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE"}
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
    observations = normalize_sportsgameodds_spread_observations(events, schedule_games)
    if not observations:
        return {**base, "verification": "UNAVAILABLE", "diagnostic_state": "SPORTSGAMEODDS_NO_VERIFIED_SPREAD_PAIRS"}
    return {**base, "verification": "VERIFIED", "diagnostic_state": "OK", "observations": observations}


__all__ = [
    "DEFAULT_BOOKMAKERS",
    "SGO_EVENTS_URL",
    "SGO_SPREAD_ODD_IDS",
    "load_verified_sportsbook_observations",
    "normalize_sportsgameodds_spread_observations",
]
