"""Kyre Sports API CFB Game Total Page 1 contract.

Application-facing Game Total discovery data is delivered only through Kyre
Sports API. NCAA owns canonical schedule/identity. FanDuel is the primary
sportsbook market source; approved secondary books are requested only for games
with no primary total quote. Quotes remain sportsbook-specific and never enter
projection/model math.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

import cfb_schedule_v3 as ncaa_schedule
from sports_api.collectors.cfb_game_total_market_v1 import (
    collect_fanduel_game_markets,
    collect_the_odds_api_game_markets,
    match_market_rows_to_ncaa_games,
)

router = APIRouter(prefix="/api/v1/cfb/game-total", tags=["cfb"])
MODEL_VERSION = "CFB GAME TOTAL PAGE1 API V1 • KYRE SPORTS API"
SCHEMA_VERSION = "cfb_game_total_page1_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PHOENIX = ZoneInfo("America/Phoenix")
MAX_AUTO_SCAN_DAYS = 14
FORBIDDEN_PROVIDERS = ["SGO", "ESPN", "ESPN BET"]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _kickoff(game: Mapping[str, Any]) -> datetime | None:
    text = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _load_ncaa_games(day: str) -> list[dict[str, Any]]:
    """Load only the current official NCAA date-scoped scoreboard path."""
    selected = date.fromisoformat(day).isoformat()
    payload, _attempts = ncaa_schedule._fetch_ncaa_scoreboard_payload(selected)
    if not payload:
        return []
    games, _diag = ncaa_schedule._official_scoreboard_games(payload, selected)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in games:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        game_id = _clean(row.get("game_id") or row.get("identity_key"))
        if not game_id or game_id in seen:
            continue
        if row.get("identity_verified") is not True or row.get("date_matches_query") is not True:
            continue
        seen.add(game_id)
        out.append(row)
    out.sort(key=lambda game: (_clean(game.get("kickoff_iso")), _clean(game.get("game_id"))))
    return out


def _dedupe_games(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for raw in games:
        row = dict(raw)
        game_id = _clean(row.get("game_id") or row.get("identity_key"))
        if not game_id or game_id in seen:
            continue
        seen.add(game_id)
        out.append(row)
    return out


def _resolve_slate_date(
    *, requested: str | None, now: datetime
) -> tuple[str, list[dict[str, Any]]]:
    if requested:
        selected = date.fromisoformat(requested).isoformat()
        return selected, _load_ncaa_games(selected)
    local_now = now.astimezone(PHOENIX)
    for offset in range(MAX_AUTO_SCAN_DAYS + 1):
        day = (local_now.date() + timedelta(days=offset)).isoformat()
        games = _load_ncaa_games(day)
        if not games:
            continue
        upcoming = [game for game in games if _kickoff(game) is None or _kickoff(game) >= now.astimezone(timezone.utc)]
        if upcoming:
            return day, upcoming
    return local_now.date().isoformat(), []


def collect_primary_market_rows() -> list[dict[str, Any]]:
    try:
        return collect_fanduel_game_markets()
    except Exception:
        return []


def collect_secondary_market_rows(missing_games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not missing_games:
        return []
    if not _clean(os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")):
        return []
    try:
        rows = collect_the_odds_api_game_markets()
    except Exception:
        return []
    matched = match_market_rows_to_ncaa_games(missing_games, rows)
    accepted: list[dict[str, Any]] = []
    for game in missing_games:
        game_id = _clean(game.get("game_id") or game.get("identity_key"))
        accepted.extend(dict(row) for row in matched.get(game_id, []))
    return accepted


def _market_state(
    games: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    consulted: list[str] = ["FanDuel"]
    primary_rows = collect_primary_market_rows()
    matched = match_market_rows_to_ncaa_games(games, primary_rows)
    missing = [
        game for game in games
        if _clean(game.get("game_id") or game.get("identity_key")) not in matched
    ]
    if missing:
        secondary_rows = collect_secondary_market_rows(missing)
        if secondary_rows:
            consulted.append("The Odds API")
            secondary = match_market_rows_to_ncaa_games(missing, secondary_rows)
            for game_id, quotes in secondary.items():
                matched.setdefault(game_id, []).extend(dict(row) for row in quotes)
    return matched, consulted


def _quote_quality(quote: Mapping[str, Any]) -> str:
    if quote.get("total_line") is None:
        return "UNAVAILABLE"
    complete = all(
        quote.get(key) is not None
        for key in (
            "over_price", "under_price", "away_spread", "home_spread",
            "away_moneyline", "home_moneyline", "observed_at_utc",
        )
    )
    return "VERIFIED" if complete else "PARTIAL"


def _public_quote(raw: Mapping[str, Any]) -> dict[str, Any]:
    quote = {
        "sportsbook": _clean(raw.get("sportsbook")) or None,
        "market": _clean(raw.get("market")) or "game_total",
        "provider_event_id": _clean(raw.get("provider_event_id")) or None,
        "provider_market_id": _clean(raw.get("provider_market_id")) or None,
        "total_line": raw.get("total_line"),
        "over_price": raw.get("over_price"),
        "under_price": raw.get("under_price"),
        "away_spread": raw.get("away_spread"),
        "away_spread_price": raw.get("away_spread_price"),
        "home_spread": raw.get("home_spread"),
        "home_spread_price": raw.get("home_spread_price"),
        "away_moneyline": raw.get("away_moneyline"),
        "home_moneyline": raw.get("home_moneyline"),
        "observed_at_utc": _clean(raw.get("observed_at_utc")) or None,
        "line_status": _clean(raw.get("line_status")) or None,
    }
    quote["line_integrity"] = _quote_quality(quote)
    return quote


def _public_game(game: Mapping[str, Any], quotes: list[dict[str, Any]]) -> dict[str, Any]:
    row = dict(game)
    row["market_quotes"] = [_public_quote(quote) for quote in quotes]
    row["market_quote_count"] = len(row["market_quotes"])
    row["market_integrity"] = (
        "VERIFIED" if any(q["line_integrity"] == "VERIFIED" for q in row["market_quotes"])
        else "PARTIAL" if row["market_quotes"] else "UNAVAILABLE"
    )
    return row


def build_page1_payload(
    *, game_date: str | None = None,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    now = now_provider()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        selected_day, resolved_games = _resolve_slate_date(requested=game_date, now=now)
    except ValueError as exc:
        raise ValueError("game_date must be YYYY-MM-DD") from exc

    games = _dedupe_games([dict(game) for game in resolved_games if isinstance(game, Mapping)])
    market_map, consulted = _market_state(games)
    public_games: list[dict[str, Any]] = []
    for game in games:
        game_id = _clean(game.get("game_id") or game.get("identity_key"))
        public_games.append(_public_game(game, market_map.get(game_id, [])))

    verified = sum(1 for game in public_games if game.get("market_integrity") == "VERIFIED")
    partial = sum(1 for game in public_games if game.get("market_integrity") == "PARTIAL")
    unavailable = sum(1 for game in public_games if game.get("market_integrity") == "UNAVAILABLE")
    return {
        "service": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_date": selected_day,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "games": public_games,
        "summary": {
            "games": len(public_games),
            "verified_market_games": verified,
            "partial_market_games": partial,
            "market_unavailable_games": unavailable,
        },
        "routing": {
            "application_gateway": "Kyre Sports API",
            "schedule_primary": "NCAA",
            "identity_primary": "NCAA",
            "market_primary": "FanDuel",
            "market_secondary": "The Odds API",
            "provider_calls": consulted,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_INFLUENCE,
            "consensus_averaging": False,
            "fabrication": False,
            "null_to_zero": False,
            "forbidden_providers": list(FORBIDDEN_PROVIDERS),
        },
    }


@router.get("/page1")
def page1(
    game_date: str | None = Query(None, min_length=10, max_length=10),
) -> dict[str, Any]:
    try:
        return build_page1_payload(game_date=game_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = [
    "FORBIDDEN_PROVIDERS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_page1_payload",
    "collect_primary_market_rows",
    "collect_secondary_market_rows",
    "page1",
    "router",
]
