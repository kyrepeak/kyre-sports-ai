"""Kyre Sports API transport for NBA pregame PRA sportsbook observations.

Provider-local misses never become global market failures until the eligible
approved routes for the field have been checked. Sportsbook observations retain
book, line, price, side and timestamp identity; they are never averaged and have
0.0 projection influence.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import math
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

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

DRAFTKINGS_HOST = "sportsbook-nash.draftkings.com"
DRAFTKINGS_NBA_LEAGUE_ID = "42648"
DRAFTKINGS_SITES = ("dkusaz", "dkusnj", "dkusil")
DRAFTKINGS_TIMEOUT_SECONDS = 12.0
_DK_PRA_NAMES = {
    ("Player Combos", "Pts + Reb + Ast O/U"),
    ("Player Combos", "Points + Rebounds + Assists O/U"),
}


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
    if isinstance(value, Mapping):
        value = value.get("american") or value.get("americanOdds") or value.get("americanDisplayOdds")
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
    if " @ " in name:
        away, home = name.split(" @ ", 1)
        return away.strip(), home.strip()
    away = home = ""
    for participant in event.get("participants") or []:
        if not isinstance(participant, Mapping):
            continue
        role = _text(participant.get("venueRole")).casefold()
        team = _text(participant.get("name"))
        if role == "away":
            away = team
        elif role == "home":
            home = team
    return away, home


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
    return _american(american.get("americanOddsInt") if american.get("americanOddsInt") is not None else american.get("americanOdds"))


def _parse_fanduel_pra_page(document: Mapping[str, Any], *, captured_at_utc: str) -> list[dict[str, Any]]:
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
        r"^(?P<player>.+?)\s+-\s+(?:Pts|Points)\s*\+\s*(?:Reb|Rebounds)\s*\+\s*(?:Ast|Assists)$",
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
        if len({row["line"] for row in parsed}) != 1:
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
            {"_ak": FANDUEL_PUBLIC_WEB_KEY, "page": "CUSTOM", "customPageId": FANDUEL_NBA_PAGE_ID, "timezone": FANDUEL_TIMEZONE},
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
                {"_ak": FANDUEL_PUBLIC_WEB_KEY, "eventId": event_id, "tab": FANDUEL_PRA_TAB, "useCombinedTouchdownsVirtualMarket": "true", "useQuickBets": "true"},
            )
            rows.extend(_parse_fanduel_pra_page(document, captured_at_utc=captured_at))
        return rows, "FANDUEL_OK" if rows else "FANDUEL_NO_PRA"
    except Exception as exc:
        return [], f"FANDUEL_ERROR:{type(exc).__name__}"


def _dk_get(url: str) -> Mapping[str, Any]:
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://sportsbook.draftkings.com/leagues/basketball/nba",
        "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-NBA/2.0; read-only)",
    }
    if cffi_requests is not None:
        response = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=DRAFTKINGS_TIMEOUT_SECONDS, allow_redirects=True)
    else:
        response = httpx.get(url, headers=headers, timeout=DRAFTKINGS_TIMEOUT_SECONDS, follow_redirects=True)
    if getattr(response, "status_code", None) != 200:
        raise RuntimeError(f"DraftKings GET returned HTTP {getattr(response, 'status_code', 'unknown')}")
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise RuntimeError("DraftKings response must be an object")
    return payload


def _discover_draftkings_pra() -> tuple[str, str, str]:
    for site in DRAFTKINGS_SITES:
        try:
            league = _dk_get(f"https://{DRAFTKINGS_HOST}/api/sportscontent/{site}/v1/leagues/{DRAFTKINGS_NBA_LEAGUE_ID}")
        except Exception:
            continue
        categories = {
            _text(row.get("id")): _text(row.get("name"))
            for row in league.get("categories") or []
            if isinstance(row, Mapping)
        }
        for row in league.get("subcategories") or []:
            if not isinstance(row, Mapping):
                continue
            category_id = _text(row.get("categoryId"))
            subcategory_id = _text(row.get("id"))
            pair = (categories.get(category_id, ""), _text(row.get("name")))
            if pair in _DK_PRA_NAMES and category_id and subcategory_id:
                return site, category_id, subcategory_id
    raise RuntimeError("DraftKings PRA discovery unavailable")


def _dk_event_date(event: Mapping[str, Any]) -> date | None:
    raw = _text(event.get("startEventDate") or event.get("startDate"))
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(PHOENIX_TZ).date()


def _fetch_draftkings_pra_observations(slate_date: date) -> tuple[list[dict[str, Any]], str]:
    try:
        site, category_id, subcategory_id = _discover_draftkings_pra()
        document = _dk_get(
            f"https://{DRAFTKINGS_HOST}/api/sportscontent/{site}/v1/leagues/{DRAFTKINGS_NBA_LEAGUE_ID}"
            f"/categories/{category_id}/subcategories/{subcategory_id}"
        )
        events = {
            _text(event.get("id")): event
            for event in document.get("events") or []
            if isinstance(event, Mapping)
            and _text(event.get("id"))
            and _dk_event_date(event) == slate_date
            and _text(event.get("status")).upper() not in {"STARTED", "LIVE", "COMPLETED", "CLOSED", "SETTLED"}
        }
        markets = {
            _text(market.get("id")): market
            for market in document.get("markets") or []
            if isinstance(market, Mapping)
            and _text(market.get("eventId")) in events
            and (
                "points + rebounds + assists" in _text(market.get("name")).casefold()
                or "pts + reb + ast" in _text(market.get("name")).casefold()
            )
        }
        captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        rows: list[dict[str, Any]] = []
        for selection in document.get("selections") or []:
            if not isinstance(selection, Mapping):
                continue
            market_id = _text(selection.get("marketId"))
            market = markets.get(market_id)
            if market is None:
                continue
            side = _text(selection.get("outcomeType") or selection.get("label")).casefold()
            if side not in {"over", "under"}:
                continue
            line = _num(selection.get("points"))
            odds = _american(selection.get("displayOdds") or selection.get("oddsAmerican") or selection.get("americanOdds"))
            if line is None or odds is None:
                continue
            player_name = ""
            for participant in selection.get("participants") or []:
                if isinstance(participant, Mapping) and _text(participant.get("type")).casefold() == "player":
                    player_name = _text(participant.get("name"))
                    break
            if not player_name:
                player_name = re.sub(
                    r"\s+(?:Points|Pts)\s*\+\s*(?:Rebounds|Reb)\s*\+\s*(?:Assists|Ast)\s+O/U.*$",
                    "",
                    _text(market.get("name")),
                    flags=re.I,
                ).strip()
            if not player_name:
                continue
            event_id = _text(market.get("eventId"))
            away_team, home_team = _event_teams(events.get(event_id, {}))
            rows.append(
                {
                    "provider": "DraftKings",
                    "provider_event_id": event_id,
                    "provider_market_id": market_id,
                    "provider_player_id": player_name,
                    "player_name": player_name,
                    "sportsbook": "DraftKings",
                    "side": side,
                    "line": line,
                    "price": odds,
                    "observed_at_utc": captured_at,
                    "away_team": away_team,
                    "home_team": home_team,
                }
            )
        return rows, "DRAFTKINGS_OK" if rows else "DRAFTKINGS_NO_PRA"
    except Exception as exc:
        return [], f"DRAFTKINGS_ACCESS_FAILURE:{type(exc).__name__}"


def _reference_recent_participant_profiles(slate_date: date) -> tuple[dict[str, dict[str, Any]], str]:
    """Return current-season history participants, never an official-roster claim."""
    try:
        from .nba_pra_player_context_v1 import (
            REFERENCE_ROOT,
            _get_text,
            _parse_reference_per_game_index,
            _season_end_year,
            kyre_player_id,
        )

        season = _season_end_year(slate_date)
        document, _ = _get_text(f"{REFERENCE_ROOT}/leagues/NBA_{season}_per_game.html", timeout=10.0)
        parsed = _parse_reference_per_game_index(document)
        profiles: dict[str, dict[str, Any]] = {}
        for key, raw in parsed.items():
            if not isinstance(raw, Mapping):
                continue
            name = _text(raw.get("player_name"))
            team = _text(raw.get("team")).upper()
            baseline = dict(raw.get("season_baseline") or {})
            try:
                games = int(baseline.get("games") or 0)
            except (TypeError, ValueError):
                games = 0
            if not name or not team or games <= 0:
                continue
            profiles[str(key)] = {
                "player_name": name,
                "team": team,
                "position": _text(raw.get("position")),
                "headshot": _text(raw.get("headshot")),
                "provider_ids": dict(raw.get("provider_ids") or {}),
                "current_games": [],
                "prior_games": [],
                "season_baseline": baseline,
                "kyre_player_id": kyre_player_id(name, team, "NBA"),
                "data_state": "HISTORY_BASELINE",
                "stats_source": "Basketball-Reference current-season per-game index",
            }
        return profiles, f"RECENT_PARTICIPANTS_{len(profiles)}" if profiles else "NO_RECENT_PARTICIPANTS"
    except Exception as exc:
        return {}, f"RECENT_PARTICIPANT_POOL_ERROR:{type(exc).__name__}"


def collect_nba_pra_market(slate_date: date) -> dict[str, Any]:
    provider_health: list[dict[str, Any]] = []
    rows, fanduel_state = _fetch_fanduel_pra_observations(slate_date)
    provider_health.append({"provider": "FanDuel", "state": fanduel_state, "observation_count": len(rows)})

    if not rows:
        rows, draftkings_state = _fetch_draftkings_pra_observations(slate_date)
        provider_health.append({"provider": "DraftKings", "state": draftkings_state, "observation_count": len(rows)})

    participant_profiles: dict[str, dict[str, Any]] = {}
    participant_state = "NOT_NEEDED"
    if not rows:
        participant_profiles, participant_state = _reference_recent_participant_profiles(slate_date)

    player_count = len({_norm(row.get("player_name")) for row in rows if row.get("player_name")})
    ready = bool(rows)
    return {
        "service": "Kyre Sports API — Vercel",
        "schema_version": "nba_pra_market_v2_provider_independence",
        "sport": "nba",
        "market": "points+rebounds+assists",
        "date": slate_date.isoformat(),
        "ready": ready,
        "verification": "VERIFIED" if ready else "UNAVAILABLE",
        "diagnostic_state": "OK" if ready else "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA",
        "player_count": player_count,
        "observation_count": len(rows),
        "observations": rows,
        "provider_health": provider_health,
        "recent_participant_profiles": participant_profiles,
        "recent_participant_state": participant_state,
        "projection_weight": 0.0,
        "sportsbook_projection_influence": 0.0,
        "consensus_averaging": False,
        "fabrication": False,
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "service": "Kyre Sports API — Vercel",
        "schema_version": "nba_pra_market_v2_provider_independence",
        "projection_weight": 0.0,
        "consensus_averaging": False,
        "provider_credentials_required": False,
        "provider_routing": ["FanDuel", "DraftKings"],
        "single_provider_global_gate": False,
    }


@router.post("")
def market(request: NbaPraMarketRequest) -> dict[str, Any]:
    return collect_nba_pra_market(request.date)
