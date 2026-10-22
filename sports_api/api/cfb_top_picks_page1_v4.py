"""Kyre Sports API CFB Top Picks Page 1 Cleanup V4.

V4 is an enrichment-only successor above frozen V3. It preserves V3 ranking,
selection, probability, sportsbook, line, and slate-backfill behavior while
filling the simple Page 1 identity fields from approved sources.

Application-facing gateway: Kyre Sports API only.
No SGO. No ESPN. No ESPN BET.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from fastapi import APIRouter, HTTPException, Query

import sports_api.api.cfb_top_picks_page1_v3 as base
from sports_api.collectors import cfb_top_picks_identity_v1 as identity

router = APIRouter(prefix="/api/v4/cfb/top-picks", tags=["cfb"])
MODEL_VERSION = "CFB TOP PICKS PAGE1 API V4 • CLEAN IDENTITY BOARD"
SCHEMA_VERSION = "cfb_top_picks_page1_v4"
DEFAULT_LIMIT = 10
MAX_LIMIT = 10


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _date_label(kickoff_iso: Any, selected_date: str) -> str:
    text = _clean(kickoff_iso)
    day = text[:10] if len(text) >= 10 else ""
    if day and day == selected_date:
        return "TODAY"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%a %b %d").upper()
    except Exception:
        return "DATE NOT_AVAILABLE"


def _unavailable_team(name: Any) -> dict[str, Any]:
    return {
        "team_name": _clean(name) or "TEAM NOT_AVAILABLE",
        "school_slug": None,
        "record_text": "NOT_AVAILABLE",
        "record_status": "NOT_AVAILABLE",
        "logo_url": None,
        "source": "NCAA identity unavailable",
    }


def build_event_index(
    payload: Mapping[str, Any],
    team_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Bind visible event IDs to exactly-matched NCAA team identities."""
    events: dict[str, dict[str, Any]] = {}
    rows = list(payload.get("game_picks") or []) + list(payload.get("player_props") or [])
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        event_id = _clean(raw.get("event_id") or raw.get("official_game_id"))
        if not event_id:
            continue
        away_name = _clean(raw.get("away_team"))
        home_name = _clean(raw.get("home_team"))
        away = identity.find_team_identity(away_name, team_index) or _unavailable_team(away_name)
        home = identity.find_team_identity(home_name, team_index) or _unavailable_team(home_name)
        current = events.get(event_id)
        candidate = {"event_id": event_id, "away": away, "home": home}
        if current is None:
            events[event_id] = candidate
            continue
        # A single event ID must not drift across team identities.
        if (
            _clean(current.get("away", {}).get("team_name")) != _clean(away.get("team_name"))
            or _clean(current.get("home", {}).get("team_name")) != _clean(home.get("team_name"))
        ):
            events[event_id] = {
                "event_id": event_id,
                "away": _unavailable_team(away_name),
                "home": _unavailable_team(home_name),
                "identity_status": "CONFLICTING",
            }
    return events


def _team_rosters_for_props(
    payload: Mapping[str, Any],
    event_index: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    teams: dict[str, dict[str, Any]] = {}
    for raw in list(payload.get("player_props") or []):
        if not isinstance(raw, Mapping):
            continue
        event_id = _clean(raw.get("event_id") or raw.get("official_game_id"))
        event = event_index.get(event_id) or {}
        for side in ("away", "home"):
            team = event.get(side)
            if not isinstance(team, Mapping):
                continue
            slug = _clean(team.get("school_slug")).casefold()
            if slug:
                teams[slug] = dict(team)
    rosters: dict[str, dict[str, dict[str, Any]]] = {}
    diagnostics: list[dict[str, Any]] = []
    for slug, team in teams.items():
        players, diag = identity.load_official_roster(team)
        rosters[slug] = players
        diagnostics.append({"team_slug": slug, **dict(diag)})
    return rosters, diagnostics


def enrich_page1_payload(
    payload: Mapping[str, Any],
    *,
    event_index: Mapping[str, Mapping[str, Any]],
    team_index: Mapping[str, Mapping[str, Any]],
    roster_index: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Pure presentation enrichment; selection/model fields are never changed."""
    del team_index  # identities are already bound into event_index
    out = dict(payload)
    selected_date = _clean(payload.get("selected_date"))

    games: list[dict[str, Any]] = []
    for raw in list(payload.get("game_picks") or []):
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        event_id = _clean(row.get("event_id") or row.get("official_game_id"))
        event = event_index.get(event_id) or {}
        away = event.get("away") if isinstance(event.get("away"), Mapping) else _unavailable_team(row.get("away_team"))
        home = event.get("home") if isinstance(event.get("home"), Mapping) else _unavailable_team(row.get("home_team"))
        row.update({
            "away_record": _clean(away.get("record_text")) or "NOT_AVAILABLE",
            "home_record": _clean(home.get("record_text")) or "NOT_AVAILABLE",
            "away_record_status": _clean(away.get("record_status")) or "NOT_AVAILABLE",
            "home_record_status": _clean(home.get("record_status")) or "NOT_AVAILABLE",
            "away_logo": _clean(away.get("logo_url")) or None,
            "home_logo": _clean(home.get("logo_url")) or None,
            "away_school_slug": _clean(away.get("school_slug")) or None,
            "home_school_slug": _clean(home.get("school_slug")) or None,
            "team_identity_status": "VERIFIED" if away.get("school_slug") and home.get("school_slug") else "NOT_AVAILABLE",
            "date_label": _date_label(row.get("kickoff_iso"), selected_date),
        })
        games.append(row)

    props: list[dict[str, Any]] = []
    for raw in list(payload.get("player_props") or []):
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        event_id = _clean(row.get("event_id") or row.get("official_game_id"))
        event = event_index.get(event_id) or {}
        away = event.get("away") if isinstance(event.get("away"), Mapping) else _unavailable_team(row.get("away_team"))
        home = event.get("home") if isinstance(event.get("home"), Mapping) else _unavailable_team(row.get("home_team"))
        player_identity = identity.resolve_player_identity(
            row.get("player_name"),
            away,
            home,
            roster_index,
        )
        row.update({
            "away_record": _clean(away.get("record_text")) or "NOT_AVAILABLE",
            "home_record": _clean(home.get("record_text")) or "NOT_AVAILABLE",
            "away_logo": _clean(away.get("logo_url")) or None,
            "home_logo": _clean(home.get("logo_url")) or None,
            "date_label": _date_label(row.get("kickoff_iso"), selected_date),
            **player_identity,
        })
        props.append(row)

    out["schema_version"] = SCHEMA_VERSION
    out["model_version"] = MODEL_VERSION
    out["game_picks"] = games
    out["player_props"] = props
    routing = dict(payload.get("routing") or {})
    routing.update({
        "application_gateway": "Kyre Sports API",
        "team_records_primary": "NCAA Winning Percentage",
        "team_logos_primary": "NCAA official school identity",
        "player_identity_primary": "Official team roster",
        "identity_secondary_only_when_needed": True,
        "forbidden_providers": ["SGO", "ESPN", "ESPN BET"],
        "consensus_averaging": False,
        "null_to_zero": False,
        "fabrication": False,
    })
    out["routing"] = routing
    diagnostics = dict(payload.get("diagnostics") or {})
    diagnostics.update({
        "verified_game_team_identity_rows": sum(1 for row in games if row.get("team_identity_status") == "VERIFIED"),
        "verified_player_identity_rows": sum(1 for row in props if row.get("identity_status") == "VERIFIED"),
        "game_logo_complete_rows": sum(1 for row in games if row.get("away_logo") and row.get("home_logo")),
        "player_team_logo_complete_rows": sum(1 for row in props if row.get("team_logo")),
        "raw_html_leak_fix": "V15_DEDENTED_HTML_BOUNDARY",
        "why_content_on_page1": False,
    })
    out["diagnostics"] = diagnostics
    return out


def build_page1_payload(
    *,
    game_date: str | None = None,
    limit: int = DEFAULT_LIMIT,
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    base_payload = base.build_page1_payload(game_date=game_date, limit=limit, now_provider=now_provider)
    team_index, team_diag = identity.load_ncaa_team_identity()
    events = build_event_index(base_payload, team_index)
    rosters, roster_diag = _team_rosters_for_props(base_payload, events)
    out = enrich_page1_payload(
        base_payload,
        event_index=events,
        team_index=team_index,
        roster_index=rosters,
    )
    diagnostics = dict(out.get("diagnostics") or {})
    diagnostics["team_identity_source"] = team_diag
    diagnostics["roster_identity_sources"] = roster_diag
    diagnostics["identity_enrichment_only"] = True
    out["diagnostics"] = diagnostics
    return out


@router.get("/page1")
def page1(
    game_date: str | None = Query(None, min_length=10, max_length=10),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> dict[str, Any]:
    try:
        return build_page1_payload(game_date=game_date, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "build_event_index",
    "build_page1_payload",
    "enrich_page1_payload",
    "page1",
    "router",
]
