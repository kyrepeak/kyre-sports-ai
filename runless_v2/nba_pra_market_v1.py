"""Vercel transport for NBA pregame PRA sportsbook observations.

The endpoint is market-context only. It accepts an optional request-scoped
provider credential from the server-side Streamlit client, never persists or
returns the credential, and preserves sportsbook/provider/line/price/timestamp
identity. Sportsbook data has exactly 0.0 projection influence.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import math
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field, SecretStr

router = APIRouter(prefix="/api/v1/nba/pra/market", tags=["nba-pra-market"])
PHOENIX_TZ = ZoneInfo("America/Phoenix")
FANDUEL_BASE = "https://api.sportsbook.fanduel.com"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
FANDUEL_REGION = "NJ"
FANDUEL_TIMEZONE = "America/Phoenix"
FANDUEL_NBA_PAGE_ID = "nba"
FANDUEL_PRA_TAB = "player-combos"
SGO_BASE = "https://api.sportsgameodds.com/v2"
# Use the provider IDs already proven in this repo. Other approved books can be
# supplied by the existing Odds-API.io fallback when legitimately needed.
SGO_BOOKMAKERS = "draftkings,fanduel,betmgm,caesars"
PRA_STAT_IDS = {"points_rebounds_assists", "points+rebounds+assists", "pra"}
BOOK_LABELS = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
}


class NbaPraMarketRequest(BaseModel):
    date: date
    sportsgameodds_api_key: SecretStr | None = Field(default=None, min_length=1, max_length=1024)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _norm(value: Any) -> str:
    return "".join(ch for ch in _text(value).casefold() if ch.isalnum())


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _american(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    if abs(number) >= 100 and float(number).is_integer():
        return int(number)
    if number > 1.0:
        if number >= 2.0:
            return int(round((number - 1.0) * 100))
        return int(round(-100 / (number - 1.0)))
    return None


def _list_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(x) for x in payload if isinstance(x, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("data", "events", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(x) for x in value if isinstance(x, Mapping)]
    return []


def _event_name(event: Mapping[str, Any], side: str) -> str:
    teams = event.get("teams") or {}
    team = teams.get(side) if isinstance(teams, Mapping) else None
    if not isinstance(team, Mapping):
        return ""
    names = team.get("names") or {}
    if isinstance(names, Mapping):
        for key in ("long", "display", "medium", "short"):
            if names.get(key):
                return _text(names[key])
    return _text(team.get("name") or team.get("teamName"))


def _player_name(event: Mapping[str, Any], player_id: str, market_name: Any) -> str:
    players = event.get("players") or {}
    player = players.get(player_id) if isinstance(players, Mapping) else None
    if isinstance(player, Mapping):
        names = player.get("names") or {}
        if isinstance(names, Mapping):
            for key in ("long", "display", "full", "medium", "short"):
                if names.get(key):
                    return _text(names[key])
        for key in ("name", "displayName", "fullName"):
            if player.get(key):
                return _text(player[key])
    raw = _text(market_name)
    lowered = raw.casefold()
    for suffix in (" points + rebounds + assists", " points rebounds assists", " pra"):
        if suffix in lowered:
            return raw[: lowered.index(suffix)].strip()
    return ""


def _parse_event(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    odds = event.get("odds") or {}
    if not isinstance(odds, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for odd in odds.values():
        if not isinstance(odd, Mapping):
            continue
        stat = _text(odd.get("statID")).casefold()
        side = _text(odd.get("sideID")).casefold()
        player_id = _text(odd.get("playerID") or odd.get("statEntityID"))
        if (
            stat not in PRA_STAT_IDS
            or _text(odd.get("periodID")).casefold() != "game"
            or _text(odd.get("betTypeID")).casefold() != "ou"
            or side not in {"over", "under"}
            or not player_id
        ):
            continue
        player_name = _player_name(event, player_id, odd.get("marketName"))
        if not player_name:
            continue
        books = odd.get("byBookmaker") or {}
        if not isinstance(books, Mapping):
            continue
        for raw_book, quote in books.items():
            if not isinstance(quote, Mapping) or quote.get("available") is False:
                continue
            book = BOOK_LABELS.get(_norm(raw_book))
            line = _num(quote.get("overUnder"))
            if not book or line is None:
                continue
            rows.append(
                {
                    "provider": "SportsGameOdds",
                    "provider_event_id": _text(event.get("eventID") or event.get("id")),
                    "provider_player_id": player_id,
                    "player_name": player_name,
                    "sportsbook": book,
                    "side": side,
                    "line": line,
                    "price": _american(quote.get("odds")),
                    "observed_at_utc": _text(quote.get("lastUpdatedAt") or event.get("updatedAt")),
                    "away_team": _event_name(event, "away"),
                    "home_team": _event_name(event, "home"),
                }
            )
    return rows


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [row for row in value.values() if isinstance(row, Mapping)]
    if isinstance(value, list):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _event_teams(event: Mapping[str, Any]) -> tuple[str, str]:
    name = _text(event.get("name") or event.get("eventName"))
    if " @ " not in name:
        return "", ""
    away, home = name.split(" @ ", 1)
    return away.strip(), home.strip()


def _fanduel_event_on_day(event: Mapping[str, Any], slate_date: date) -> bool:
    raw = _text(event.get("openDate") or event.get("startTime"))
    if not raw:
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(PHOENIX_TZ).date() == slate_date


def _fanduel_price(runner: Mapping[str, Any]) -> int | None:
    odds = runner.get("winRunnerOdds")
    if not isinstance(odds, Mapping):
        return None
    american = odds.get("americanDisplayOdds")
    if not isinstance(american, Mapping):
        return None
    return _american(
        american.get("americanOddsInt")
        if american.get("americanOddsInt") is not None
        else american.get("americanOdds")
    )


def _parse_fanduel_pra_page(
    document: Mapping[str, Any],
    *,
    captured_at_utc: str,
) -> list[dict[str, Any]]:
    attachments = document.get("attachments") if isinstance(document, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    events = {
        _text(event.get("eventId") or event.get("id")): event
        for event in _rows(attachments.get("events"))
        if _text(event.get("eventId") or event.get("id"))
    }
    rows: list[dict[str, Any]] = []
    standard_name = re.compile(
        r"^(?P<player>.+?)\s+-\s+Pts\s*\+\s*Reb\s*\+\s*Ast$",
        re.IGNORECASE,
    )
    for market in _rows(attachments.get("markets")):
        market_name = _text(market.get("marketName") or market.get("name"))
        match = standard_name.match(market_name)
        market_type = _text(market.get("marketType"))
        if not match or "ALT" in market_type.upper():
            continue
        if _text(market.get("marketStatus") or market.get("status")).upper() not in {"", "OPEN", "ACTIVE"}:
            continue
        if market.get("inPlay") is True:
            continue
        event_id = _text(market.get("eventId") or market.get("eventID"))
        event = events.get(event_id, {})
        away_team, home_team = _event_teams(event)
        if not away_team or not home_team:
            continue
        player_name = match.group("player").strip()
        parsed: list[dict[str, Any]] = []
        for runner in _rows(market.get("runners")):
            if _text(runner.get("runnerStatus") or runner.get("status")).upper() not in {"", "ACTIVE", "OPEN"}:
                continue
            result = runner.get("result")
            side = _text(result.get("type") if isinstance(result, Mapping) else "").casefold()
            if side not in {"over", "under"}:
                continue
            line = _num(runner.get("handicap"))
            price = _fanduel_price(runner)
            if line is None or price is None:
                continue
            parsed.append(
                {
                    "provider": "FanDuel",
                    "provider_event_id": event_id,
                    "provider_market_id": _text(market.get("marketId") or market.get("id")),
                    "provider_player_id": player_name,
                    "player_name": player_name,
                    "sportsbook": "FanDuel",
                    "side": side,
                    "line": line,
                    "price": price,
                    "observed_at_utc": captured_at_utc,
                    "away_team": away_team,
                    "home_team": home_team,
                }
            )
        if {row["side"] for row in parsed} != {"over", "under"}:
            continue
        lines = {row["line"] for row in parsed}
        if len(lines) != 1:
            continue
        rows.extend(parsed)
    return rows


def _request_fanduel(path: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
    timeout = httpx.Timeout(20.0, connect=3.0)
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://sportsbook.fanduel.com",
        "Referer": "https://sportsbook.fanduel.com/",
        "x-sportsbook-region": FANDUEL_REGION,
    }
    with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers) as client:
        response = client.get(f"{FANDUEL_BASE}{path}", params=dict(params))
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("FanDuel response was not a JSON object")
    return payload


def _fetch_fanduel_pra_observations(slate_date: date) -> tuple[list[dict[str, Any]], str]:
    try:
        landing = _request_fanduel(
            "/sbapi/content-managed-page",
            {
                "_ak": FANDUEL_PUBLIC_WEB_KEY,
                "page": "CUSTOM",
                "customPageId": FANDUEL_NBA_PAGE_ID,
                "timezone": FANDUEL_TIMEZONE,
            },
        )
        attachments = landing.get("attachments")
        if not isinstance(attachments, Mapping):
            return [], "FANDUEL_NO_ATTACHMENTS"
        nba_competition_ids = {
            _text(row.get("competitionId") or row.get("id"))
            for row in _rows(attachments.get("competitions"))
            if _text(row.get("name") or row.get("competitionName")).casefold() == "nba"
        }
        events = [
            event
            for event in _rows(attachments.get("events"))
            if _fanduel_event_on_day(event, slate_date)
            and (
                not nba_competition_ids
                or _text(event.get("competitionId")) in nba_competition_ids
            )
        ]
        if not events:
            return [], "FANDUEL_NO_EVENTS"
        captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        rows: list[dict[str, Any]] = []
        for event in events:
            event_id = _text(event.get("eventId") or event.get("id"))
            if not event_id:
                continue
            document = _request_fanduel(
                "/sbapi/event-page",
                {
                    "_ak": FANDUEL_PUBLIC_WEB_KEY,
                    "eventId": event_id,
                    "tab": FANDUEL_PRA_TAB,
                    "useCombinedTouchdownsVirtualMarket": "true",
                    "useQuickBets": "true",
                },
            )
            rows.extend(_parse_fanduel_pra_page(document, captured_at_utc=captured_at))
        return rows, "FANDUEL_OK" if rows else "FANDUEL_NO_PRA"
    except Exception as exc:
        return [], f"FANDUEL_ERROR:{type(exc).__name__}"


def _odd_filter() -> str:
    return ",".join(
        f"points+rebounds+assists-PLAYER_ID-game-ou-{side}" for side in ("over", "under")
    )


def _phoenix_window(day: date) -> tuple[str, str]:
    start = datetime.combine(day, time.min, tzinfo=PHOENIX_TZ)
    end = start + timedelta(days=1)
    fmt = lambda value: value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return fmt(start), fmt(end)


def _request_events(params: dict[str, Any], api_key: str) -> list[dict[str, Any]]:
    timeout = httpx.Timeout(20.0, connect=3.0)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        response = client.get(
            f"{SGO_BASE}/events",
            headers={"X-API-Key": api_key},
            params=params,
        )
        response.raise_for_status()
        return _list_payload(response.json())


def _fetch_sgo_events(slate_date: date, api_key: str) -> tuple[list[dict[str, Any]], str]:
    starts_after, starts_before = _phoenix_window(slate_date)
    base = {
        "leagueID": "NBA",
        "startsAfter": starts_after,
        "startsBefore": starts_before,
        "oddsAvailable": "true",
        "bookmakerID": SGO_BOOKMAKERS,
        "limit": 100,
    }
    focused_error = ""
    try:
        focused = _request_events({**base, "oddIDs": _odd_filter()}, api_key)
        if focused:
            return focused, "FOCUSED_OK"
    except Exception as exc:
        focused_error = type(exc).__name__
    # Same-provider recovery only: a broad event request avoids silently
    # collapsing an unsupported/fragile complex filter into zero markets.
    try:
        broad = _request_events(base, api_key)
        return broad, "BROAD_OK" if broad else "SGO_NO_EVENTS"
    except Exception as exc:
        suffix = type(exc).__name__
        return [], f"SGO_ERROR:{focused_error or 'EMPTY'}:{suffix}"


def collect_nba_pra_market(slate_date: date, api_key: str | None = None) -> dict[str, Any]:
    key = _text(api_key)
    rows, diagnostic = _fetch_fanduel_pra_observations(slate_date)
    if not rows and key:
        events, diagnostic = _fetch_sgo_events(slate_date, key)
        rows = [row for event in events for row in _parse_event(event)]
    player_count = len({_norm(row.get("player_name")) for row in rows if row.get("player_name")})
    return {
        "service": "Kyre Sports API — Vercel",
        "schema_version": "nba_pra_market_v1",
        "sport": "nba",
        "market": "points+rebounds+assists",
        "date": slate_date.isoformat(),
        "ready": bool(rows),
        "verification": "VERIFIED" if rows else "UNAVAILABLE",
        "diagnostic_state": "OK" if rows else diagnostic,
        "player_count": player_count,
        "observation_count": len(rows),
        "observations": rows,
        "projection_weight": 0.0,
        "sportsbook_projection_influence": 0.0,
        "consensus_averaging": False,
        "fabrication": False,
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "service": "Kyre Sports API — Vercel",
        "schema_version": "nba_pra_market_v1",
        "projection_weight": 0.0,
        "consensus_averaging": False,
        "credential_storage": "request-scoped-only",
    }


@router.post("")
def market(request: NbaPraMarketRequest) -> dict[str, Any]:
    key = request.sportsgameodds_api_key.get_secret_value() if request.sportsgameodds_api_key else None
    return collect_nba_pra_market(request.date, key)
