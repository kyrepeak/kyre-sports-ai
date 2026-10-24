"""Kyre Sports API transport for NBA pregame PRA sportsbook observations.

The endpoint preserves sportsbook, provider, line, price, and timestamp identity.
Sportsbook observations have exactly 0.0 projection influence and are never
averaged across books.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import math
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/nba/pra/market", tags=["nba-pra-market"])
PHOENIX_TZ = ZoneInfo("America/Phoenix")
FANDUEL_BASE = "https://api.sportsbook.fanduel.com"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
FANDUEL_REGION = "NJ"
FANDUEL_TIMEZONE = "America/Phoenix"
FANDUEL_NBA_PAGE_ID = "nba"
FANDUEL_PRA_TAB = "player-combos"

_PRA_STANDARD_NAME = re.compile(
    r"^(?P<player>.+?)\s*-\s*(?:Pts|Points)\s*\+\s*(?:Reb|Rebs|Rebounds)\s*\+\s*(?:Ast|Asts|Assists)$",
    re.IGNORECASE,
)


class NbaPraMarketRequest(BaseModel):
    date: date


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
    for market in _rows(attachments.get("markets")):
        market_name = _text(market.get("marketName") or market.get("name"))
        match = _PRA_STANDARD_NAME.match(market_name)
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
            and (not nba_competition_ids or _text(event.get("competitionId")) in nba_competition_ids)
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


def collect_nba_pra_market(slate_date: date) -> dict[str, Any]:
    rows, diagnostic = _fetch_fanduel_pra_observations(slate_date)
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
        "provider_credentials_required": False,
        "fabrication": False,
    }


@router.post("")
def market(request: NbaPraMarketRequest) -> dict[str, Any]:
    return collect_nba_pra_market(request.date)
