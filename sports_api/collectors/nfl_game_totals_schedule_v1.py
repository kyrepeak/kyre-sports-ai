"""Official ESPN NFL schedule/identity + metadata layer for Game Totals V1.

This module is sportsbook-free. It establishes exact official game identity for
one requested NFL calendar date and is safe for current/future supported slates.
Unknown identities fail closed; optional venue metadata never fabricates values
and never causes an otherwise valid official game to be dropped.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping

from sports_api.collectors import nfl_fanduel_passing_yards as base

SCHEMA_VERSION = "nfl_game_totals_schedule_v1"
ESPN_SITE_BASES = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl",
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl",
)


class NFLGameTotalsScheduleError(RuntimeError):
    """The official NFL slate could not be proven safely."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _requested_date(value: date | str) -> date:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(_text(value))
    except ValueError as exc:
        raise NFLGameTotalsScheduleError("game_date must be YYYY-MM-DD") from exc


def _aware_utc(value: Any, field: str) -> datetime:
    text = _text(value).replace("Z", "+00:00")
    if not text:
        raise NFLGameTotalsScheduleError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise NFLGameTotalsScheduleError(f"{field} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NFLGameTotalsScheduleError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _team_identity(row: Mapping[str, Any], side: str) -> dict[str, str]:
    team = row.get("team") if isinstance(row.get("team"), Mapping) else {}
    team_id = _text((team or {}).get("id"))
    abbr = _text((team or {}).get("abbreviation")).upper()
    name = _text((team or {}).get("displayName") or (team or {}).get("name"))
    if not team_id.isdigit() or not abbr or not name:
        raise NFLGameTotalsScheduleError(f"ESPN {side} team identity is incomplete")
    return {"team_id": team_id, "abbr": abbr, "name": name}


def _venue_metadata(competition: Mapping[str, Any]) -> dict[str, Any]:
    venue = competition.get("venue") if isinstance(competition.get("venue"), Mapping) else {}
    address = (venue or {}).get("address") if isinstance((venue or {}).get("address"), Mapping) else {}
    name = _text((venue or {}).get("fullName") or (venue or {}).get("name"))
    city = _text((address or {}).get("city"))
    state = _text((address or {}).get("state"))
    indoor_raw = (venue or {}).get("indoor")
    indoor = indoor_raw if isinstance(indoor_raw, bool) else None
    return {
        "available": bool(name),
        "name": name or None,
        "city": city or None,
        "state": state or None,
        "indoor": indoor,
    }


def _parse_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _text(raw.get("id"))
    if not event_id.isdigit():
        raise NFLGameTotalsScheduleError("ESPN scoreboard event ID must be numeric")

    competitions = raw.get("competitions") or []
    if len(competitions) != 1 or not isinstance(competitions[0], Mapping):
        raise NFLGameTotalsScheduleError(f"ESPN event {event_id} must have exactly one competition")
    competition = competitions[0]
    competition_id = _text(competition.get("id"))
    if competition_id and competition_id != event_id:
        raise NFLGameTotalsScheduleError(f"ESPN event {event_id} competition identity mismatch")

    sides: dict[str, dict[str, str]] = {}
    for competitor in competition.get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        side = _text(competitor.get("homeAway")).lower()
        if side in {"home", "away"}:
            if side in sides:
                raise NFLGameTotalsScheduleError(f"ESPN event {event_id} has duplicate {side} team")
            sides[side] = _team_identity(competitor, side)
    if set(sides) != {"home", "away"}:
        raise NFLGameTotalsScheduleError(f"ESPN event {event_id} is missing exact home/away identities")
    if sides["home"]["team_id"] == sides["away"]["team_id"]:
        raise NFLGameTotalsScheduleError(f"ESPN event {event_id} has duplicate team IDs")

    kickoff = _aware_utc(competition.get("date") or raw.get("date"), "ESPN kickoff")
    status = competition.get("status") if isinstance(competition.get("status"), Mapping) else {}
    status_type = (status or {}).get("type") if isinstance((status or {}).get("type"), Mapping) else {}
    state = _text((status_type or {}).get("state")).lower()
    completed = bool((status_type or {}).get("completed"))
    detail = _text((status_type or {}).get("detail") or (status_type or {}).get("shortDetail"))

    return {
        "official_event_id": event_id,
        "kickoff_utc": kickoff.isoformat(),
        "status": {
            "state": state or "unknown",
            "completed": completed,
            "detail": detail,
            "pregame": not completed and state not in {"in", "post"},
        },
        "away": sides["away"],
        "home": sides["home"],
        "venue": _venue_metadata(competition),
        "neutral_site": bool(competition.get("neutralSite")),
        "identity_policy": {
            "official_authority": "ESPN",
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_team_ids": False,
        },
    }


def parse_espn_scoreboard(payload: Mapping[str, Any], game_date: date | str) -> dict[str, Any]:
    requested = _requested_date(game_date)
    events = payload.get("events") if isinstance(payload, Mapping) else None
    if not isinstance(events, list):
        raise NFLGameTotalsScheduleError("ESPN scoreboard events payload is invalid")

    games: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    for raw in events:
        if not isinstance(raw, Mapping):
            raise NFLGameTotalsScheduleError("ESPN scoreboard contains a non-object event")
        game = _parse_event(raw)
        event_id = game["official_event_id"]
        if event_id in seen_event_ids:
            raise NFLGameTotalsScheduleError(f"duplicate ESPN event ID {event_id}")
        seen_event_ids.add(event_id)
        games.append(game)

    games.sort(key=lambda row: (row["kickoff_utc"], row["official_event_id"]))
    venue_available_count = sum(1 for game in games if game["venue"]["available"])
    return {
        "schema_version": SCHEMA_VERSION,
        "service": "Kyre Sports API",
        "sport": "nfl",
        "official_authority": "ESPN",
        "requested_date": requested.isoformat(),
        "game_count": len(games),
        "venue_available_count": venue_available_count,
        "venue_missing_count": len(games) - venue_available_count,
        "games": games,
        "identity_policy": {
            "official_event_id_required": True,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_team_ids": False,
        },
    }


def fetch_espn_nfl_scoreboard_hosted(
    game_date: date | str,
    *,
    timeout: int = base.DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], str]:
    requested = _requested_date(game_date)
    params = {"dates": requested.strftime("%Y%m%d"), "limit": "100"}
    for root in ESPN_SITE_BASES:
        try:
            payload = base._get_json(
                f"{root}/scoreboard",
                params,
                headers=base.ESPN_HEADERS,
                timeout=timeout,
            )
            return payload, root
        except base.NFLPassingYardsCollectorError:
            continue
    raise NFLGameTotalsScheduleError(
        "official ESPN NFL scoreboard transport failed closed across site.api + site.web.api"
    )


def collect_official_nfl_slate(
    game_date: date | str,
    *,
    fetcher=None,
) -> dict[str, Any]:
    requested = _requested_date(game_date)
    if fetcher is None:
        payload, source = fetch_espn_nfl_scoreboard_hosted(requested)
    else:
        result = fetcher(requested)
        if isinstance(result, tuple):
            payload, source = result
        else:
            payload, source = result, "injected-test-source"
    out = parse_espn_scoreboard(payload, requested)
    out["source"] = source
    return out


__all__ = [
    "ESPN_SITE_BASES",
    "NFLGameTotalsScheduleError",
    "SCHEMA_VERSION",
    "collect_official_nfl_slate",
    "fetch_espn_nfl_scoreboard_hosted",
    "parse_espn_scoreboard",
]
