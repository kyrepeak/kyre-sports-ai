"""CFB Game Total V164 exact team-logo identity adapter.

Presentation-only.  Resolve missing away/home ESPN team IDs from the official
ESPN college-football scoreboard by exact event_id, then hand the enriched copy
back to the frozen exact-ID logo resolver.  No name guessing, no model changes.
"""
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
import os
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import requests

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/"
    "college-football/scoreboard"
)
ESPN_GROUPS = (80, 81)
ESPN_LOGO_CDN_TEMPLATE = "https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png"
NETWORK_TIMEOUT_SECONDS = 6.0
TEAM_IDENTITY_API_BASE_ENV = "KYRE_SPORTS_API_BASE_URL"
TEAM_IDENTITY_API_BASE_DEFAULT = "https://kyre-sports-api.onrender.com"
TEAM_IDENTITY_ENDPOINT = "/api/v1/cfb/identity/team-logos"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _event_id(game: Mapping[str, Any]) -> str:
    for key in ("espn_event_id", "event_id"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _game_date(game: Mapping[str, Any]) -> str:
    for key in ("game_date", "date", "start_date", "kickoff_iso", "start_time_utc", "kickoff_utc"):
        raw = _clean(game.get(key))
        if not raw:
            continue
        try:
            if "T" in raw:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                    return parsed.astimezone(ZoneInfo("America/New_York")).date().isoformat()
            return date.fromisoformat(raw[:10]).isoformat()
        except ValueError:
            continue
    return ""


def _rows_from_payload(payload: Mapping[str, Any], requested_day: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        event_id = _clean(event.get("id"))
        comps = event.get("competitions") or []
        if not event_id or not comps or not isinstance(comps[0], Mapping):
            continue
        comp = comps[0]
        sides: dict[str, Mapping[str, Any]] = {}
        for competitor in comp.get("competitors") or []:
            if not isinstance(competitor, Mapping):
                continue
            side = _clean(competitor.get("homeAway")).casefold()
            if side in {"away", "home"}:
                sides[side] = competitor
        if set(sides) != {"away", "home"}:
            continue

        def team(side: str) -> tuple[str, str]:
            raw = sides[side].get("team")
            data = raw if isinstance(raw, Mapping) else {}
            team_id = _clean(data.get("id"))
            name = _clean(data.get("displayName") or data.get("shortDisplayName") or data.get("location") or data.get("name"))
            return team_id, name

        away_id, away_name = team("away")
        home_id, home_name = team("home")
        if not away_id.isdigit() or not home_id.isdigit():
            continue
        rows.append({
            "event_id": event_id,
            "game_date": requested_day,
            "away_team_id": away_id,
            "home_team_id": home_id,
            "away_team": away_name,
            "home_team": home_name,
        })
    return rows


@lru_cache(maxsize=32)
def _api_rows(requested_day: str) -> tuple[dict[str, str], ...]:
    """Read exact team IDs from the Kyre Sports API's server-side ESPN resolver."""
    base = _clean(os.environ.get(TEAM_IDENTITY_API_BASE_ENV)) or TEAM_IDENTITY_API_BASE_DEFAULT
    try:
        response = requests.get(
            f"{base.rstrip('/')}{TEAM_IDENTITY_ENDPOINT}",
            params={"game_date": requested_day},
            headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-CFB-V164-Logos/1.0"},
            timeout=NETWORK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return ()

    if not isinstance(payload, Mapping):
        return ()
    if payload.get("synthetic_ids") is not False:
        return ()
    if payload.get("may_modify_projection") is not False:
        return ()
    try:
        if float(payload.get("projection_weight")) != 0.0:
            return ()
    except (TypeError, ValueError):
        return ()

    rows: list[dict[str, str]] = []
    for raw in payload.get("games") or []:
        if not isinstance(raw, Mapping) or raw.get("identity_verified") is not True:
            continue
        event_id = _clean(raw.get("event_id"))
        away_id = _clean(raw.get("away_team_id"))
        home_id = _clean(raw.get("home_team_id"))
        if not event_id or not away_id.isdigit() or not home_id.isdigit():
            continue
        rows.append({
            "event_id": event_id,
            "away_team_id": away_id,
            "home_team_id": home_id,
        })
    return tuple(rows)


@lru_cache(maxsize=32)
def _espn_rows(requested_day: str) -> tuple[dict[str, str], ...]:
    combined: dict[str, dict[str, str]] = {}
    for group_id in ESPN_GROUPS:
        try:
            response = requests.get(
                ESPN_SCOREBOARD_URL,
                params={"dates": requested_day.replace("-", ""), "limit": 500, "groups": group_id},
                headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-CFB-V164-Logos/1.0"},
                timeout=NETWORK_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping):
                continue
            for row in _rows_from_payload(payload, requested_day):
                combined.setdefault(row["event_id"], row)
        except (requests.RequestException, ValueError, TypeError):
            continue
    return tuple(combined.values())


def _selector_row(game: Mapping[str, Any], selector_payload: Mapping[str, Any] | None) -> dict[str, str] | None:
    event_id = _event_id(game)
    if not event_id or not isinstance(selector_payload, Mapping):
        return None
    matches = []
    for raw in selector_payload.get("games") or []:
        if not isinstance(raw, Mapping) or _clean(raw.get("event_id")) != event_id:
            continue
        away_id = _clean(raw.get("away_team_id"))
        home_id = _clean(raw.get("home_team_id"))
        if away_id.isdigit() and home_id.isdigit():
            matches.append({
                "event_id": event_id,
                "away_team_id": away_id,
                "home_team_id": home_id,
            })
    return matches[0] if len(matches) == 1 else None


def enrich_exact_team_ids(
    game: Mapping[str, Any],
    selector_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = dict(game)
    event_id = _event_id(game)
    if not event_id:
        return enriched

    row = _selector_row(game, selector_payload)
    if row is None:
        requested_day = _game_date(game)
        if requested_day:
            exact = [candidate for candidate in _api_rows(requested_day) if candidate["event_id"] == event_id]
            row = exact[0] if len(exact) == 1 else None
            if row is None:
                exact = [candidate for candidate in _espn_rows(requested_day) if candidate["event_id"] == event_id]
                row = exact[0] if len(exact) == 1 else None
    if row is None:
        return enriched

    for side in ("away", "home"):
        team_id = _clean(row.get(f"{side}_team_id"))
        if not team_id.isdigit():
            continue
        enriched[f"{side}_espn_team_id"] = team_id
        enriched[f"{side}_team_id"] = team_id
    enriched["logo_identity_source"] = "ESPN exact event_id -> exact team IDs"
    return enriched


def resolve_visuals(
    game: Mapping[str, Any],
    frozen_resolver,
    selector_payload: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    first = frozen_resolver(game)
    if all(bool((first.get(side) or {}).get("exact_identity")) for side in ("away", "home")):
        return first
    enriched = enrich_exact_team_ids(game, selector_payload)
    return frozen_resolver(enriched)


def clear_cache() -> None:
    _api_rows.cache_clear()
    _espn_rows.cache_clear()


__all__ = [
    "ESPN_GROUPS",
    "ESPN_LOGO_CDN_TEMPLATE",
    "ESPN_SCOREBOARD_URL",
    "TEAM_IDENTITY_ENDPOINT",
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "clear_cache",
    "enrich_exact_team_ids",
    "resolve_visuals",
]
