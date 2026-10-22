"""Kyre Sports API CFB Top Picks Page 1 Cleanup V4.

Enrichment-only successor above frozen V3: V3 owns ranking, selection,
probability, sportsbook, line, and slate backfill. V4 fills simple Page 1
identity fields from NCAA and current official team rosters.
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
DEFAULT_LIMIT = MAX_LIMIT = 10


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _date_label(kickoff_iso: Any, selected_date: str) -> str:
    text = _clean(kickoff_iso)
    if len(text) >= 10 and text[:10] == selected_date:
        return "TODAY"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%a %b %d").upper()
    except Exception:
        return "DATE NOT_AVAILABLE"


def _unavailable_team(name: Any) -> dict[str, Any]:
    return {"team_name": _clean(name) or "TEAM NOT_AVAILABLE", "school_slug": None, "record_text": "NOT_AVAILABLE", "record_status": "NOT_AVAILABLE", "logo_url": None}


def _team_from_event(raw: Mapping[str, Any] | None, fallback_name: Any, team_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    raw = raw if isinstance(raw, Mapping) else {}
    slug = _clean(raw.get("school_slug") or raw.get("slug")).casefold()
    if slug and slug in team_index:
        row = dict(team_index[slug])
        row.setdefault("school_slug", slug)
        row.setdefault("team_name", _clean(raw.get("team_name") or raw.get("name") or fallback_name))
        return row
    name = _clean(raw.get("team_name") or raw.get("name") or fallback_name)
    matched = identity.find_team_identity(name, team_index)
    if matched:
        return matched
    if raw.get("school_slug") and raw.get("team_name"):
        return dict(raw)
    return _unavailable_team(name)


def build_event_index(payload: Mapping[str, Any], team_index: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    rows = list(payload.get("game_picks") or []) + list(payload.get("player_props") or [])
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        event_id = _clean(raw.get("event_id") or raw.get("official_game_id"))
        if not event_id:
            continue
        away = identity.find_team_identity(raw.get("away_team"), team_index) or _unavailable_team(raw.get("away_team"))
        home = identity.find_team_identity(raw.get("home_team"), team_index) or _unavailable_team(raw.get("home_team"))
        candidate = {"event_id": event_id, "away": away, "home": home}
        prior = events.get(event_id)
        if prior and (_clean(prior["away"].get("team_name")) != _clean(away.get("team_name")) or _clean(prior["home"].get("team_name")) != _clean(home.get("team_name"))):
            events[event_id] = {"event_id": event_id, "away": _unavailable_team(raw.get("away_team")), "home": _unavailable_team(raw.get("home_team")), "identity_status": "CONFLICTING"}
        elif prior is None:
            events[event_id] = candidate
    return events


def _team_rosters_for_props(payload: Mapping[str, Any], event_index: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    teams: dict[str, dict[str, Any]] = {}
    for raw in list(payload.get("player_props") or []):
        if not isinstance(raw, Mapping):
            continue
        event = event_index.get(_clean(raw.get("event_id") or raw.get("official_game_id"))) or {}
        for side in ("away", "home"):
            team = event.get(side)
            if isinstance(team, Mapping):
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


def enrich_page1_payload(payload: Mapping[str, Any], *, event_index: Mapping[str, Mapping[str, Any]], team_index: Mapping[str, Mapping[str, Any]], roster_index: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    out = dict(payload)
    selected_date = _clean(payload.get("selected_date"))
    games: list[dict[str, Any]] = []
    for raw in list(payload.get("game_picks") or []):
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        event = event_index.get(_clean(row.get("event_id") or row.get("official_game_id"))) or {}
        away = _team_from_event(event.get("away"), row.get("away_team"), team_index)
        home = _team_from_event(event.get("home"), row.get("home_team"), team_index)
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
        event = event_index.get(_clean(row.get("event_id") or row.get("official_game_id"))) or {}
        away = _team_from_event(event.get("away"), row.get("away_team"), team_index)
        home = _team_from_event(event.get("home"), row.get("home_team"), team_index)
        row.update({
            "away_record": _clean(away.get("record_text")) or "NOT_AVAILABLE",
            "home_record": _clean(home.get("record_text")) or "NOT_AVAILABLE",
            "away_logo": _clean(away.get("logo_url")) or None,
            "home_logo": _clean(home.get("logo_url")) or None,
            "date_label": _date_label(row.get("kickoff_iso"), selected_date),
            **identity.resolve_player_identity(row.get("player_name"), away, home, roster_index),
        })
        props.append(row)
    out.update(schema_version=SCHEMA_VERSION, model_version=MODEL_VERSION, game_picks=games, player_props=props)
    routing = dict(payload.get("routing") or {})
    routing.update({"application_gateway": "Kyre Sports API", "team_records_primary": "NCAA Winning Percentage", "team_logos_primary": "NCAA official school identity", "player_identity_primary": "Official team roster", "identity_secondary_only_when_needed": True, "consensus_averaging": False, "null_to_zero": False, "fabrication": False})
    out["routing"] = routing
    diagnostics = dict(payload.get("diagnostics") or {})
    diagnostics.update({"verified_game_team_identity_rows": sum(row.get("team_identity_status") == "VERIFIED" for row in games), "verified_player_identity_rows": sum(row.get("identity_status") == "VERIFIED" for row in props), "game_logo_complete_rows": sum(bool(row.get("away_logo") and row.get("home_logo")) for row in games), "player_team_logo_complete_rows": sum(bool(row.get("team_logo")) for row in props), "raw_html_leak_fix": "V15_DEDENTED_HTML_BOUNDARY", "why_content_on_page1": False})
    out["diagnostics"] = diagnostics
    return out


def build_page1_payload(*, game_date: str | None = None, limit: int = DEFAULT_LIMIT, now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    base_payload = base.build_page1_payload(game_date=game_date, limit=limit, now_provider=now_provider)
    team_index, team_diag = identity.load_ncaa_team_identity()
    events = build_event_index(base_payload, team_index)
    rosters, roster_diag = _team_rosters_for_props(base_payload, events)
    out = enrich_page1_payload(base_payload, event_index=events, team_index=team_index, roster_index=rosters)
    diagnostics = dict(out.get("diagnostics") or {})
    diagnostics.update(team_identity_source=team_diag, roster_identity_sources=roster_diag, identity_enrichment_only=True)
    out["diagnostics"] = diagnostics
    return out


@router.get("/page1")
def page1(game_date: str | None = Query(None, min_length=10, max_length=10), limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)) -> dict[str, Any]:
    try:
        return build_page1_payload(game_date=game_date, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = ["DEFAULT_LIMIT", "MAX_LIMIT", "MODEL_VERSION", "SCHEMA_VERSION", "build_event_index", "build_page1_payload", "enrich_page1_payload", "page1", "router"]
