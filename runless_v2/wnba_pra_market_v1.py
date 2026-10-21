"""Kyre Sports API — Vercel WNBA PRA market gateway.

Application callers use only this Kyre-owned route. The gateway tries FanDuel
first and calls DraftKings only when the primary source has no usable current
PRA market or is degraded. Exact sportsbook line, price, side, market identity,
and capture timestamp are preserved; cross-book averaging is forbidden.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo

from curl_cffi import requests as cffi_requests
from fastapi import APIRouter, HTTPException, Query

from ._wnba_fanduel_direct_v1 import collect_fanduel_wnba_feed

router = APIRouter(prefix="/api/v1/wnba/pra", tags=["wnba-pra-market"])

WNBA_LEAGUE_ID = "94682"
DK_HOST = "sportsbook-nash.draftkings.com"
DK_SITES = ("dkusaz", "dkusnj", "dkusil")
DK_TIMEOUT = 18.0
EASTERN = ZoneInfo("America/New_York")
_PRA_NAMES = {
    ("Player Combos", "Pts + Reb + Ast O/U"),
    ("Player Combos", "Points + Rebounds + Assists O/U"),
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _american(value: Any) -> int | None:
    if isinstance(value, Mapping):
        value = value.get("american") or value.get("americanOdds")
    text = _text(value).replace("−", "-").replace("–", "-").replace("+", "").replace(",", "")
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() and abs(number) >= 100 else None


def _event_local_date(event: Mapping[str, Any]) -> str | None:
    raw = _text(event.get("startEventDate") or event.get("startDate"))
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(EASTERN).date().isoformat()
    except ValueError:
        return None


def _event_teams(event: Mapping[str, Any]) -> tuple[str, str]:
    away = home = ""
    for p in event.get("participants") or []:
        if not isinstance(p, Mapping) or _text(p.get("type")).casefold() != "team":
            continue
        role = _text(p.get("venueRole")).casefold()
        name = _text(p.get("name"))
        if role == "away":
            away = name
        elif role == "home":
            home = name
    if (not away or not home) and " @ " in _text(event.get("name")):
        away, home = [x.strip() for x in _text(event.get("name")).split(" @ ", 1)]
    return away, home


def _dk_get(url: str) -> dict[str, Any]:
    response = cffi_requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://sportsbook.draftkings.com/leagues/basketball/wnba",
            "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-WNBA/2.0; read-only)",
        },
        impersonate="chrome120",
        timeout=DK_TIMEOUT,
        allow_redirects=True,
    )
    if getattr(response, "status_code", None) != 200:
        raise RuntimeError(f"DraftKings GET returned HTTP {getattr(response, 'status_code', 'unknown')}")
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("DraftKings response must be an object")
    return body


def _discover_dk_pra() -> tuple[str, str, str]:
    errors: list[str] = []
    for site in DK_SITES:
        try:
            league = _dk_get(f"https://{DK_HOST}/api/sportscontent/{site}/v1/leagues/{WNBA_LEAGUE_ID}")
        except Exception as exc:
            errors.append(f"{site}:{type(exc).__name__}")
            continue
        categories = {
            _text(row.get("id")): _text(row.get("name"))
            for row in (league.get("categories") or [])
            if isinstance(row, Mapping)
        }
        for row in league.get("subcategories") or []:
            if not isinstance(row, Mapping):
                continue
            category_id = _text(row.get("categoryId"))
            subcategory_id = _text(row.get("id"))
            pair = (categories.get(category_id, ""), _text(row.get("name")))
            if pair in _PRA_NAMES and category_id and subcategory_id:
                return site, category_id, subcategory_id
        errors.append(f"{site}:pra_market_missing")
    raise RuntimeError("DraftKings PRA discovery failed: " + ",".join(errors))


def _default_draftkings(*, date: str, season: int) -> list[dict[str, Any]]:
    del season
    site, category_id, subcategory_id = _discover_dk_pra()
    doc = _dk_get(
        f"https://{DK_HOST}/api/sportscontent/{site}/v1/leagues/{WNBA_LEAGUE_ID}"
        f"/categories/{category_id}/subcategories/{subcategory_id}"
    )
    events = {
        _text(e.get("id")): e
        for e in (doc.get("events") or [])
        if isinstance(e, Mapping)
        and _text(e.get("id"))
        and _text(e.get("status")).upper() not in {"STARTED", "LIVE", "COMPLETED", "CLOSED", "SETTLED"}
        and _event_local_date(e) == date
    }
    markets = {
        _text(m.get("id")): m
        for m in (doc.get("markets") or [])
        if isinstance(m, Mapping)
        and _text(m.get("eventId")) in events
        and (
            "points + rebounds + assists" in _text(m.get("name")).casefold()
            or "pts + reb + ast" in _text(m.get("name")).casefold()
        )
    }
    captured = datetime.now(timezone.utc).isoformat()
    offers: list[dict[str, Any]] = []
    for selection in doc.get("selections") or []:
        if not isinstance(selection, Mapping):
            continue
        market_id = _text(selection.get("marketId"))
        market = markets.get(market_id)
        if market is None:
            continue
        side = _text(selection.get("outcomeType") or selection.get("label")).casefold()
        if side not in {"over", "under"}:
            continue
        try:
            line = float(selection.get("points"))
        except (TypeError, ValueError):
            continue
        odds = _american(selection.get("displayOdds"))
        if odds is None:
            continue
        player = ""
        for participant in selection.get("participants") or []:
            if isinstance(participant, Mapping) and _text(participant.get("type")).casefold() == "player":
                player = _text(participant.get("name"))
                break
        if not player:
            name = _text(market.get("name"))
            player = re.sub(r"\s+(?:Points|Pts)\s*\+\s*(?:Rebounds|Reb)\s*\+\s*(?:Assists|Ast)\s+O/U.*$", "", name, flags=re.I).strip()
        if not player:
            continue
        event_id = _text(market.get("eventId"))
        event = events[event_id]
        away, home = _event_teams(event)
        offers.append(
            {
                "sportsbook": "DraftKings",
                "provider_id": "draftkings",
                "player_name": player,
                "stat": "pra",
                "side": side,
                "line": line,
                "american_odds": odds,
                "market_captured_at_utc": captured,
                "source_event_id": event_id,
                "source_market_id": market_id,
                "source_offer_id": _text(selection.get("id")),
                "away_team": away,
                "home_team": home,
            }
        )
    return offers


def _default_fanduel(*, date: str, season: int) -> list[dict[str, Any]]:
    snapshot = collect_fanduel_wnba_feed(date=date, season=season)
    raw = snapshot.get("raw_feed") if isinstance(snapshot, Mapping) else None
    rows = raw.get("offers") if isinstance(raw, Mapping) else None
    return [dict(row) for row in (rows or []) if isinstance(row, Mapping)]


def _pra(row: Mapping[str, Any]) -> bool:
    stat = re.sub(r"[^a-z]", "", _text(row.get("stat")).casefold())
    return stat in {"pra", "pointsreboundsassists"}


def _valid_two_sided(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, float], set[str]] = {}
    for row in rows:
        if not _pra(row):
            continue
        try:
            line = float(row.get("line"))
        except (TypeError, ValueError):
            continue
        key = (_text(row.get("source_event_id")), _text(row.get("player_name")).casefold(), line)
        groups.setdefault(key, set()).add(_text(row.get("side")).casefold())
    valid = {key for key, sides in groups.items() if {"over", "under"}.issubset(sides)}
    output: list[dict[str, Any]] = []
    for row in rows:
        if not _pra(row):
            continue
        try:
            key = (_text(row.get("source_event_id")), _text(row.get("player_name")).casefold(), float(row.get("line")))
        except (TypeError, ValueError):
            continue
        if key in valid and _text(row.get("side")).casefold() in {"over", "under"}:
            output.append(dict(row))
    return output


def build_pra_market_board(
    *,
    date: str,
    season: int = 2026,
    fanduel_collector: Callable[..., list[dict[str, Any]]] | None = None,
    draftkings_collector: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    datetime.strptime(date, "%Y-%m-%d")
    if int(season) != 2026:
        raise ValueError("WNBA PRA market gateway currently supports season 2026.")

    health: list[dict[str, Any]] = []
    fd = fanduel_collector or _default_fanduel
    dk = draftkings_collector or _default_draftkings

    primary: list[dict[str, Any]] = []
    try:
        primary = _valid_two_sided(fd(date=date, season=season))
        health.append({"provider_id": "fanduel", "state": "READY" if primary else "EMPTY", "pra_offer_count": len(primary), "error": None})
    except Exception as exc:
        health.append({"provider_id": "fanduel", "state": "DEGRADED", "pra_offer_count": 0, "error": type(exc).__name__})

    selected = primary
    provider = "fanduel" if primary else None
    if not selected:
        secondary: list[dict[str, Any]] = []
        try:
            secondary = _valid_two_sided(dk(date=date, season=season))
            health.append({"provider_id": "draftkings", "state": "READY" if secondary else "EMPTY", "pra_offer_count": len(secondary), "error": None})
        except Exception as exc:
            health.append({"provider_id": "draftkings", "state": "DEGRADED", "pra_offer_count": 0, "error": type(exc).__name__})
        selected = secondary
        provider = "draftkings" if secondary else None

    players = sorted({_text(r.get("player_name")) for r in selected if _text(r.get("player_name"))})
    books = sorted({_text(r.get("sportsbook")) for r in selected if _text(r.get("sportsbook"))})
    return {
        "service": "Kyre Sports API — Vercel",
        "state": "READY" if selected else "NO_CURRENT_PRA_MARKET",
        "date": date,
        "season": int(season),
        "selected_provider": provider,
        "sportsbooks": books,
        "pra_offer_count": len(selected),
        "player_count": len(players),
        "players": players,
        "offers": selected,
        "provider_health": health,
        "consensus_averaging": False,
        "projection_weight": 0.0,
    }


@router.get("/market-board")
def market_board(date: str = Query(...), season: int = Query(2026)) -> dict[str, Any]:
    try:
        return build_pra_market_board(date=date, season=season)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WNBA PRA gateway unavailable:{type(exc).__name__}") from exc
