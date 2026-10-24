"""NBA PRA real-market restore successor for Kyre Sports API.

Preserves the frozen FanDuel/DraftKings provider-independence route, then uses
The Odds API only when those direct routes do not supply a real PRA market.
All quotes remain sportsbook-specific. No averaging, fabrication, or sportsbook
input to the Kyre projection is allowed here.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import math
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Header

from . import nba_pra_market_provider_independence_v1 as frozen

router = APIRouter(prefix="/api/v1/nba/pra/market", tags=["nba-pra-market"])
NbaPraMarketRequest = frozen.NbaPraMarketRequest
PHOENIX_TZ = ZoneInfo("America/Phoenix")
THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4"
THE_ODDS_API_SPORT = "basketball_nba"
THE_ODDS_API_MARKET = "player_points_rebounds_assists"
THE_ODDS_API_BOOKMAKERS = "fanduel,draftkings,betmgm,caesars,williamhill_us,bet365,fanatics"
_ALLOWED_BOOK_KEYS = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "williamhill_us": "Caesars",
    "bet365": "bet365",
    "fanatics": "Fanatics Sportsbook",
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) else None


def _american(value: Any) -> int | None:
    parsed = _number(value)
    if parsed is None or parsed == 0:
        return None
    if abs(parsed) >= 100:
        return int(round(parsed))
    if parsed > 1:
        return int(round((parsed - 1.0) * 100.0)) if parsed >= 2 else int(round(-100.0 / (parsed - 1.0)))
    return None


def _event_on_slate(event: Mapping[str, Any], slate_date: date) -> bool:
    raw = _text(event.get("commence_time"))
    if not raw:
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(PHOENIX_TZ).date() == slate_date


def normalize_the_odds_api_pra_event(
    payload: Mapping[str, Any], *, slate_date: date
) -> list[dict[str, Any]]:
    """Normalize one official The Odds API event into exact book PRA observations."""
    if not isinstance(payload, Mapping) or not _event_on_slate(payload, slate_date):
        return []
    event_id = _text(payload.get("id"))
    away_team = _text(payload.get("away_team"))
    home_team = _text(payload.get("home_team"))
    if not event_id or not away_team or not home_team:
        return []

    raw_rows: list[dict[str, Any]] = []
    for bookmaker in payload.get("bookmakers") or []:
        if not isinstance(bookmaker, Mapping):
            continue
        book_key = _text(bookmaker.get("key")).casefold()
        sportsbook = _ALLOWED_BOOK_KEYS.get(book_key)
        if not sportsbook:
            continue
        book_stamp = _text(bookmaker.get("last_update"))
        for market in bookmaker.get("markets") or []:
            if not isinstance(market, Mapping) or _text(market.get("key")) != THE_ODDS_API_MARKET:
                continue
            stamp = _text(market.get("last_update")) or book_stamp
            market_id = f"{event_id}:{book_key}:{THE_ODDS_API_MARKET}"
            for outcome in market.get("outcomes") or []:
                if not isinstance(outcome, Mapping):
                    continue
                side = _text(outcome.get("name")).casefold()
                player = _text(outcome.get("description"))
                line = _number(outcome.get("point"))
                price = _american(outcome.get("price"))
                if side not in {"over", "under"} or not player or line is None or price is None:
                    continue
                raw_rows.append({
                    "provider": "The Odds API",
                    "provider_event_id": event_id,
                    "provider_market_id": market_id,
                    "provider_player_id": player,
                    "player_name": player,
                    "sportsbook": sportsbook,
                    "side": side,
                    "line": float(line),
                    "price": price,
                    "observed_at_utc": stamp,
                    "away_team": away_team,
                    "home_team": home_team,
                })

    groups: dict[tuple[str, str, float], list[dict[str, Any]]] = {}
    for row in raw_rows:
        key = (row["sportsbook"], "".join(ch for ch in row["player_name"].casefold() if ch.isalnum()), row["line"])
        groups.setdefault(key, []).append(row)
    rows: list[dict[str, Any]] = []
    for values in groups.values():
        sides = {row["side"] for row in values}
        if sides == {"over", "under"}:
            newest: dict[str, dict[str, Any]] = {}
            for row in values:
                side = row["side"]
                if side not in newest or row["observed_at_utc"] >= newest[side]["observed_at_utc"]:
                    newest[side] = row
            rows.extend([newest["over"], newest["under"]])
    return rows


def fetch_the_odds_api_pra_observations(
    slate_date: date,
    *,
    api_key: str,
    request_get: Callable[..., Any] | None = None,
    timeout: float = 15.0,
) -> tuple[list[dict[str, Any]], str]:
    key = _text(api_key)
    if not key:
        return [], "THE_ODDS_API_CREDENTIAL_UNAVAILABLE"
    request_get = request_get or httpx.get
    try:
        events_response = request_get(
            f"{THE_ODDS_API_BASE}/sports/{THE_ODDS_API_SPORT}/events",
            params={"apiKey": key, "dateFormat": "iso"},
            timeout=timeout,
        )
        events_response.raise_for_status()
        events_payload = events_response.json()
        events = [row for row in events_payload if isinstance(row, Mapping)] if isinstance(events_payload, list) else []
        target_events = [row for row in events if _event_on_slate(row, slate_date) and _text(row.get("id"))]
        if not target_events:
            return [], "THE_ODDS_API_NO_EVENTS"

        rows: list[dict[str, Any]] = []
        for event in target_events:
            event_id = _text(event.get("id"))
            response = request_get(
                f"{THE_ODDS_API_BASE}/sports/{THE_ODDS_API_SPORT}/events/{event_id}/odds",
                params={
                    "apiKey": key,
                    "regions": "us",
                    "markets": THE_ODDS_API_MARKET,
                    "bookmakers": THE_ODDS_API_BOOKMAKERS,
                    "oddsFormat": "american",
                    "dateFormat": "iso",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, Mapping):
                rows.extend(normalize_the_odds_api_pra_event(payload, slate_date=slate_date))
        return rows, "THE_ODDS_API_OK" if rows else "THE_ODDS_API_NO_PRA"
    except Exception as exc:
        return [], f"THE_ODDS_API_ERROR:{type(exc).__name__}"


def _route_audit() -> list[dict[str, Any]]:
    audit = [dict(row) for row in frozen.PROVIDER_ROUTE_AUDIT if row.get("provider") != "The Odds API"]
    audit.append({"provider": "The Odds API", "state": "ACTIVE_AGGREGATOR_FALLBACK"})
    return audit


def collect_nba_pra_market(
    slate_date: date,
    *,
    the_odds_api_key: str | None = None,
    direct_loader: Callable[[date], Mapping[str, Any]] | None = None,
    odds_loader: Callable[..., tuple[list[dict[str, Any]], str]] | None = None,
) -> dict[str, Any]:
    direct_impl = direct_loader or frozen.collect_nba_pra_market
    odds_impl = odds_loader or fetch_the_odds_api_pra_observations
    base = dict(direct_impl(slate_date) or {})
    base["provider_route_audit"] = _route_audit()
    base["schema_version"] = "nba_pra_market_v3_real_restore"

    direct_rows = [dict(row) for row in base.get("observations") or [] if isinstance(row, Mapping)]
    if direct_rows:
        return base

    key = _text(the_odds_api_key)
    if not key:
        health = [dict(row) for row in base.get("provider_health") or [] if isinstance(row, Mapping)]
        health.append({"provider": "The Odds API", "state": "THE_ODDS_API_CREDENTIAL_UNAVAILABLE", "observation_count": 0})
        base["provider_health"] = health
        return base

    rows, odds_state = odds_impl(slate_date, api_key=key)
    health = [dict(row) for row in base.get("provider_health") or [] if isinstance(row, Mapping)]
    health.append({"provider": "The Odds API", "state": odds_state, "observation_count": len(rows)})
    base["provider_health"] = health
    if not rows:
        return base

    player_count = len({"".join(ch for ch in _text(row.get("player_name")).casefold() if ch.isalnum()) for row in rows if _text(row.get("player_name"))})
    base.update({
        "ready": True,
        "verification": "VERIFIED",
        "diagnostic_state": "OK",
        "global_market_state_reason": "MARKET_AVAILABLE",
        "player_count": player_count,
        "observation_count": len(rows),
        "observations": rows,
        "projection_weight": 0.0,
        "sportsbook_projection_influence": 0.0,
        "consensus_averaging": False,
        "fabrication": False,
    })
    return base


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "service": "Kyre Sports API — Vercel",
        "schema_version": "nba_pra_market_v3_real_restore",
        "projection_weight": 0.0,
        "consensus_averaging": False,
        "provider_routing": ["FanDuel", "DraftKings", "The Odds API"],
        "provider_route_audit": _route_audit(),
        "single_provider_global_gate": False,
        "fabrication": False,
    }


@router.post("")
def market(
    request: NbaPraMarketRequest,
    x_kyre_the_odds_api_key: str | None = Header(default=None, alias="X-Kyre-The-Odds-Api-Key"),
) -> dict[str, Any]:
    return collect_nba_pra_market(request.date, the_odds_api_key=x_kyre_the_odds_api_key)
