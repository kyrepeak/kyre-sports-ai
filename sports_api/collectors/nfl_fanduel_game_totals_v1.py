"""Read-only NFL FanDuel game-total collector.

Contract:
- ESPN event IDs are authoritative.
- FanDuel events are accepted only after exact team-identity + kickoff reconciliation.
- Only open pregame full-game totals are returned.
- Any identity/market ambiguity fails closed.
- Sportsbook data is context only and has 0.0% projection influence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ESPN_SUMMARY_URL = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary"
FANDUEL_HOST = os.getenv("FANDUEL_SBAPI_HOST", "https://sbapi.az.sportsbook.fanduel.com").rstrip("/")
FANDUEL_PUBLIC_AK = os.getenv("FANDUEL_PUBLIC_AK", "FhMFpcPWXMeyZxOx")
FANDUEL_NFL_EVENT_TYPE_ID = os.getenv("FANDUEL_NFL_EVENT_TYPE_ID", "6423")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("NFL_TOTALS_HTTP_TIMEOUT_SECONDS", "8"))
KICKOFF_TOLERANCE_SECONDS = int(os.getenv("NFL_TOTALS_KICKOFF_TOLERANCE_SECONDS", "300"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _canonical_team(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _team_identity_values(team: dict[str, Any]) -> set[str]:
    values = {
        team.get("displayName"),
        team.get("shortDisplayName"),
        team.get("name"),
        team.get("abbreviation"),
    }
    return {canon for value in values if (canon := _canonical_team(value))}


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "kyre-sports-ai/nfl-game-totals-v1",
        },
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed trusted hosts
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("provider returned a non-object JSON payload")
    return payload


def _espn_identity(event_id: str) -> dict[str, Any]:
    payload = _get_json(ESPN_SUMMARY_URL, {"event": event_id})
    header = payload.get("header") or {}
    competitions = header.get("competitions") or []
    if not competitions:
        raise ValueError("official ESPN event identity unavailable")
    competition = competitions[0]
    competitors = competition.get("competitors") or []
    if len(competitors) != 2:
        raise ValueError("official ESPN event does not have exactly two competitors")

    sides: dict[str, dict[str, Any]] = {}
    team_ids: dict[str, str | None] = {}
    for competitor in competitors:
        side = str(competitor.get("homeAway") or "").lower()
        if side not in {"home", "away"}:
            continue
        team = competitor.get("team") or {}
        sides[side] = team
        raw_id = team.get("id")
        team_ids[side] = str(raw_id) if raw_id is not None else None

    if set(sides) != {"home", "away"}:
        raise ValueError("official ESPN home/away identity unavailable")

    kickoff = _parse_dt(competition.get("date") or header.get("date"))
    if kickoff is None:
        raise ValueError("official ESPN kickoff unavailable")

    status = competition.get("status") or header.get("status") or {}
    status_type = status.get("type") if isinstance(status, dict) else {}
    state = str((status_type or {}).get("state") or "").lower()
    if state and state != "pre":
        raise ValueError("event is not pregame")

    venue = competition.get("venue") or {}
    broadcasts = competition.get("broadcasts") or []
    broadcast_names: list[str] = []
    for broadcast in broadcasts:
        names = broadcast.get("names") if isinstance(broadcast, dict) else None
        if isinstance(names, list):
            broadcast_names.extend(str(name) for name in names if name)

    return {
        "event_id": str(event_id),
        "kickoff": kickoff,
        "home_values": _team_identity_values(sides["home"]),
        "away_values": _team_identity_values(sides["away"]),
        "home_team_id": team_ids.get("home"),
        "away_team_id": team_ids.get("away"),
        "venue": venue.get("fullName") if isinstance(venue, dict) else None,
        "broadcast": broadcast_names,
        "status": state or "pre",
    }


def _fanduel_landing() -> dict[str, Any]:
    return _get_json(
        f"{FANDUEL_HOST}/api/content-managed-page",
        {
            "page": "SPORT",
            "eventTypeId": FANDUEL_NFL_EVENT_TYPE_ID,
            "_ak": FANDUEL_PUBLIC_AK,
            "timezone": "America/Phoenix",
        },
    )


def _fanduel_event_page(provider_event_id: str) -> dict[str, Any]:
    return _get_json(
        f"{FANDUEL_HOST}/api/event-page",
        {
            "eventId": provider_event_id,
            "_ak": FANDUEL_PUBLIC_AK,
            "timezone": "America/Phoenix",
        },
    )


def _event_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = payload.get("attachments") or {}
    rows = attachments.get("events") if isinstance(attachments, dict) else None
    if isinstance(rows, dict):
        return [row for row in rows.values() if isinstance(row, dict)]
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _split_matchup_name(name: Any) -> tuple[str, str] | None:
    text = str(name or "").strip()
    for separator in (" @ ", " at ", " v ", " vs ", " vs. "):
        if separator in text:
            away, home = text.split(separator, 1)
            return _canonical_team(away), _canonical_team(home)
    return None


def _reconcile_provider_event(identity: dict[str, Any], landing: dict[str, Any]) -> str:
    matches: list[str] = []
    for event in _event_rows(landing):
        matchup = _split_matchup_name(event.get("name"))
        if not matchup:
            continue
        away_name, home_name = matchup
        if away_name not in identity["away_values"] or home_name not in identity["home_values"]:
            continue

        provider_kickoff = _parse_dt(event.get("openDate") or event.get("startDate"))
        if provider_kickoff is None:
            continue
        if abs((provider_kickoff - identity["kickoff"]).total_seconds()) > KICKOFF_TOLERANCE_SECONDS:
            continue

        provider_event_id = event.get("eventId") or event.get("id")
        if provider_event_id is not None:
            matches.append(str(provider_event_id))

    unique = sorted(set(matches))
    if len(unique) != 1:
        raise ValueError("exact ESPN-to-FanDuel reconciliation failed")
    return unique[0]


def _market_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = payload.get("attachments") or {}
    rows = attachments.get("markets") if isinstance(attachments, dict) else None
    if isinstance(rows, dict):
        return [row for row in rows.values() if isinstance(row, dict)]
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _american_price(runner: dict[str, Any]) -> int | float | None:
    odds = runner.get("winRunnerOdds") or runner.get("runnerOdds") or {}
    american = odds.get("americanDisplayOdds") if isinstance(odds, dict) else {}
    value = american.get("americanOdds") if isinstance(american, dict) else None
    if value is None:
        value = runner.get("americanOdds")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return int(numeric) if numeric.is_integer() else numeric


def _runner_side(runner: dict[str, Any]) -> str:
    name = str(runner.get("runnerName") or runner.get("name") or "").strip().lower()
    if name == "over" or name.startswith("over "):
        return "over"
    if name == "under" or name.startswith("under "):
        return "under"
    return ""


def _runner_total(runner: dict[str, Any]) -> float | None:
    value = runner.get("handicap")
    if value is None:
        match = re.search(r"(-?\d+(?:\.\d+)?)", str(runner.get("runnerName") or runner.get("name") or ""))
        value = match.group(1) if match else None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_full_game_total(market: dict[str, Any]) -> bool:
    name = str(market.get("marketName") or market.get("name") or "").strip().lower()
    market_type = str(market.get("marketType") or "").strip().lower()
    combined = f"{name} {market_type}"
    blocked = ("1st half", "first half", "quarter", "team total", "alternative", "alt total")
    if any(token in combined for token in blocked):
        return False
    return "total" in combined or "over/under" in combined


def _extract_game_total(payload: dict[str, Any], provider_event_id: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for market in _market_rows(payload):
        event_id = market.get("eventId")
        if event_id is not None and str(event_id) != str(provider_event_id):
            continue
        if market.get("marketStatus") in {"CLOSED", "SUSPENDED"} or market.get("status") in {"CLOSED", "SUSPENDED"}:
            continue
        if market.get("inPlay") is True or not _is_full_game_total(market):
            continue

        runners = market.get("runners") or []
        if not isinstance(runners, list):
            continue
        sides = {_runner_side(runner): runner for runner in runners if isinstance(runner, dict)}
        over = sides.get("over")
        under = sides.get("under")
        if not over or not under:
            continue

        over_total = _runner_total(over)
        under_total = _runner_total(under)
        total = over_total if over_total is not None else under_total
        if total is None or (under_total is not None and abs(total - under_total) > 1e-9):
            continue

        over_price = _american_price(over)
        under_price = _american_price(under)
        if over_price is None or under_price is None:
            continue

        candidates.append(
            {
                "sportsbook": "fanduel",
                "total": total,
                "over_price": over_price,
                "under_price": under_price,
                "market_id": str(market.get("marketId") or market.get("id") or ""),
                "updated_at_utc": market.get("lastUpdated") or market.get("updatedAt") or _utc_now(),
                "active": True,
            }
        )

    if len(candidates) != 1:
        raise ValueError("exactly one open pregame full-game total was not available")
    return candidates[0]


def collect_nfl_game_totals(event_id: str) -> dict[str, Any]:
    """Collect one identity-verified FanDuel NFL full-game total.

    This function deliberately returns a fail-closed payload rather than guessing when
    provider identity or market selection is incomplete/ambiguous.
    """
    captured_at = _utc_now()
    base: dict[str, Any] = {
        "event_id": str(event_id),
        "provider": "fanduel",
        "provider_event_id": None,
        "captured_at_utc": captured_at,
        "ready": False,
        "market_available": False,
        "markets": [],
        "diagnostics": [],
        "home_team_id": None,
        "away_team_id": None,
        "kickoff_utc": None,
        "status": None,
        "venue": None,
        "broadcast": [],
    }
    try:
        if not str(event_id).isdigit():
            raise ValueError("event_id must be an official numeric ESPN event ID")

        identity = _espn_identity(str(event_id))
        base.update(
            {
                "home_team_id": identity["home_team_id"],
                "away_team_id": identity["away_team_id"],
                "kickoff_utc": identity["kickoff"].isoformat().replace("+00:00", "Z"),
                "status": identity["status"],
                "venue": identity["venue"],
                "broadcast": identity["broadcast"],
            }
        )
        provider_event_id = _reconcile_provider_event(identity, _fanduel_landing())
        base["provider_event_id"] = provider_event_id
        market = _extract_game_total(_fanduel_event_page(provider_event_id), provider_event_id)
        base["markets"] = [market]
        base["ready"] = True
        base["market_available"] = True
        return base
    except Exception as exc:  # fail closed at the external-data boundary
        base["diagnostics"] = [str(exc)]
        return base