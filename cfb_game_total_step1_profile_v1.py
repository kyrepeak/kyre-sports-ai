"""Presentation-only exact profile enrichment for CFB Game Total Step 1.

Step 1 needs identity metadata that is intentionally outside the frozen model:
mascot, FBS/FCS classification, current record and head coach. This adapter
fills only those display fields from exact ESPN event/team IDs and existing
certified ESPN Core helpers. It never changes projection, distribution,
qualification, ranking, odds, or selection behavior.
"""
from __future__ import annotations

from typing import Any, Mapping

import requests

import cfb_over_under_data_recovery_v1 as recovery
import cfb_over_under_deep_data_reconciliation_v1 as deep
import cfb_over_under_environment_engine_v1 as environment
import cfb_over_under_history_engine_v1 as history
import cfb_schedule_v3 as schedule

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ESPN_TEAM_DETAIL_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/"
    "teams/{team_id}"
)
FAST_PROFILE_TIMEOUT_SECONDS = 4.0

_UNAVAILABLE = {
    "",
    "—",
    "-",
    "n/a",
    "na",
    "none",
    "unavailable",
    "mascot unavailable",
    "conference unavailable",
    "fbs/fcs unavailable",
    "head coach unavailable",
    "record unavailable",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _usable(value: Any) -> bool:
    text = _clean(value)
    return bool(text) and text.casefold() not in _UNAVAILABLE


def _season(display_game: Mapping[str, Any]) -> int:
    for key in ("game_date", "date", "start_date", "kickoff_iso", "start_time_utc"):
        raw = _clean(display_game.get(key))
        if len(raw) >= 4 and raw[:4].isdigit():
            return int(raw[:4])
    return deep._season(display_game)


def _event_id(display_game: Mapping[str, Any]) -> str:
    return _clean(display_game.get("espn_event_id") or display_game.get("event_id"))


def _exact_directory_team(team_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    team_id = _clean(team_id)
    if not team_id.isdigit():
        return {}
    matches = [
        dict(team)
        for team in recovery._iter_team_objects(payload)
        if _clean(team.get("id")) == team_id
    ]
    return matches[0] if len(matches) == 1 else {}


def _group_ids(value: Any) -> set[str]:
    out: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            raw_id = _clean(node.get("id"))
            if raw_id:
                out.add(raw_id)
            for child in node.values():
                if isinstance(child, (Mapping, list, tuple)):
                    walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(value)
    return out


def _classification(profile: Mapping[str, Any], team_obj: Mapping[str, Any]) -> str:
    # Exact current ESPN team metadata outranks inherited/stale profile labels.
    for key in ("classification", "subdivision", "division"):
        value = _clean(team_obj.get(key)).upper()
        if "FCS" in value:
            return "FCS"
        if "FBS" in value:
            return "FBS"

    ids = _group_ids(team_obj.get("groups") or {})
    if "80" in ids:
        return "FBS"
    if "81" in ids:
        return "FCS"

    for key in ("division_context", "classification", "subdivision", "division", "level", "fbs_fcs"):
        value = _clean(profile.get(key)).upper()
        if value in {"FBS", "FCS"}:
            return value

    source = " ".join(
        _clean(profile.get(key)).casefold()
        for key in ("data_source", "rank_source")
    )
    if "fcs" in source:
        return "FCS"
    return ""




def _fast_get_json(
    url: str,
    params: Mapping[str, Any] | None,
    provider: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        response = requests.get(
            url,
            params=dict(params or {}),
            timeout=FAST_PROFILE_TIMEOUT_SECONDS,
            headers={"User-Agent": "KyreSportsAI/Step1", "Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("provider returned non-object JSON")
        return payload, [{
            "provider": provider,
            "transport": "requests",
            "http": int(response.status_code),
            "bytes": len(response.content or b""),
            "error": "",
        }]
    except Exception as exc:
        return {}, [{
            "provider": provider,
            "transport": "requests",
            "http": None,
            "bytes": 0,
            "error": f"{type(exc).__name__}: {exc}"[:260],
        }]


def _exact_event_summary(event_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    event_id = _clean(event_id)
    if not event_id:
        return {}, []
    return _fast_get_json(
        environment.ESPN_SUMMARY_URL,
        {"event": event_id},
        f"ESPN exact event {event_id} Step 1 summary",
    )


def _exact_team_detail(team_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    team_id = _clean(team_id)
    if not team_id.isdigit():
        return {}, []
    payload, attempts = _fast_get_json(
        ESPN_TEAM_DETAIL_URL.format(team_id=team_id),
        {},
        f"ESPN exact CFB team {team_id} Step 1 profile",
    )
    candidate = payload.get("team") if isinstance(payload, Mapping) else {}
    if isinstance(candidate, Mapping) and _clean(candidate.get("id")) == team_id:
        return dict(candidate), attempts
    if isinstance(payload, Mapping) and _clean(payload.get("id")) == team_id:
        return dict(payload), attempts
    return {}, attempts

def _schedule_team_object(payload: Mapping[str, Any], team_id: str) -> dict[str, Any]:
    team_id = _clean(team_id)
    root = payload.get("team") or {}
    if isinstance(root, Mapping) and _clean(root.get("id")) == team_id:
        return dict(root)

    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        comp = history._competition(event)
        for competitor in comp.get("competitors") or []:
            if not isinstance(competitor, Mapping):
                continue
            team = competitor.get("team") or {}
            if isinstance(team, Mapping) and _clean(team.get("id")) == team_id:
                return dict(team)
    return {}


def _record_from_schedule(
    payload: Mapping[str, Any],
    team_id: str,
    display_game: Mapping[str, Any],
) -> str:
    cutoff = deep._cutoff(display_game)
    wins = losses = ties = 0
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        row = history._event_row(event, team_id)
        if not row:
            continue
        dt = row.get("date_dt")
        if dt is not None and dt >= cutoff:
            continue
        pf = float(row.get("points_for") or 0.0)
        pa = float(row.get("points_against") or 0.0)
        if pf > pa:
            wins += 1
        elif pf < pa:
            losses += 1
        else:
            ties += 1
    games = wins + losses + ties
    if games <= 0:
        return ""
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _merge_team_meta(*rows: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for key, value in row.items():
            if value not in (None, "", [], {}):
                out[key] = value
    return out

def _summary_competitor(summary: Mapping[str, Any], side: str, team_id: str) -> dict[str, Any]:
    competitor = deep._summary_sides(summary).get(side) or {}
    if not isinstance(competitor, Mapping):
        return {}
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        return {}
    exact_id = _clean(team.get("id") or competitor.get("id"))
    if exact_id != _clean(team_id):
        return {}
    return dict(competitor)


def _record_from_summary(competitor: Mapping[str, Any]) -> str:
    return deep._record_summary(competitor, {"total", "overall"})


def _mascot(competitor: Mapping[str, Any], team_obj: Mapping[str, Any]) -> str:
    summary_team = competitor.get("team") or {}
    if not isinstance(summary_team, Mapping):
        summary_team = {}
    for candidate in (
        summary_team.get("name"),
        summary_team.get("nickname"),
        team_obj.get("name"),
        team_obj.get("nickname"),
    ):
        if _usable(candidate):
            return _clean(candidate)
    return ""


def _fill(out: dict[str, Any], key: str, value: Any) -> None:
    if not _usable(out.get(key)) and _usable(value):
        out[key] = _clean(value)


def _enrich_side(
    side: str,
    identity_side: Mapping[str, Any],
    profile: Mapping[str, Any],
    display_game: Mapping[str, Any],
    summary: Mapping[str, Any],
    directory: Mapping[str, Any],
    season: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = dict(profile)
    team_id = _clean(
        identity_side.get("team_id")
        or profile.get("team_id")
        or profile.get("espn_team_id")
        or display_game.get(f"{side}_espn_team_id")
    )
    directory_team: dict[str, Any] = {}
    detail_team, detail_attempts = _exact_team_detail(team_id)
    schedule_payload: dict[str, Any] = {}
    schedule_attempts: list[dict[str, Any]] = []
    schedule_team: dict[str, Any] = {}
    competitor = _summary_competitor(summary, side, team_id)
    summary_team = competitor.get("team") if isinstance(competitor, Mapping) else {}
    if not isinstance(summary_team, Mapping):
        summary_team = {}
    team_obj = _merge_team_meta(detail_team, summary_team)

    _fill(out, "mascot", _mascot(competitor, team_obj))
    _fill(out, "classification", _classification(out, team_obj))
    _fill(out, "division_context", out.get("classification"))

    record = _record_from_summary(competitor)
    if not _usable(record):
        for candidate in (
            out.get("record_text"),
            display_game.get(f"{side}_record_summary"),
        ):
            if _usable(candidate):
                record = _clean(candidate)
                break
    if _usable(record):
        out["record"] = record
        out["record_text"] = record

    # Do not block the live page on another provider round-trip. Step 1 uses
    # the already-reconciled head-coach field and fails closed if it is absent.
    coach_name = _clean(out.get("head_coach"))
    coach_attempts: list[dict[str, Any]] = []
    _fill(out, "head_coach", coach_name)

    diag = {
        "side": side,
        "team_id": team_id,
        "directory_exact": bool(directory_team),
        "detail_team_exact": bool(detail_team),
        "schedule_team_exact": bool(schedule_team),
        "schedule_loaded": bool(schedule_payload),
        "summary_exact": bool(competitor),
        "mascot_ready": _usable(out.get("mascot")),
        "classification_ready": _clean(out.get("classification")).upper() in {"FBS", "FCS"},
        "record_ready": _usable(out.get("record")),
        "head_coach_ready": _usable(out.get("head_coach")),
        "coach_attempts": coach_attempts,
        "detail_attempts": detail_attempts,
        "schedule_attempts": schedule_attempts,
    }
    out["step1_profile_enriched"] = True
    out["step1_profile_exact_team_id"] = team_id
    return out, diag


def enrich_step1_inputs(
    identity: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    display_game: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Fill Step-1-only profile fields using exact ESPN identity.

    Returns enriched away/home display dictionaries and diagnostics. Missing
    provider data remains missing; nothing is guessed from team names.
    """
    identity = identity or {}
    display_game = display_game or {}
    away = away or {}
    home = home or {}
    event_id = _event_id(display_game)

    summary, summary_attempts = _exact_event_summary(event_id)
    # Broad team-directory and schedule fallbacks can each take tens of
    # seconds per transport. Step 1 stays exact and fast: event summary +
    # exact team detail only, otherwise fail closed to CHECK.
    directory: dict[str, Any] = {}

    season = _season(display_game)
    away_out, away_diag = _enrich_side(
        "away",
        identity.get("away") or {},
        away,
        display_game,
        summary,
        directory,
        season,
    )
    home_out, home_diag = _enrich_side(
        "home",
        identity.get("home") or {},
        home,
        display_game,
        summary,
        directory,
        season,
    )
    diag = {
        "event_id": event_id,
        "season": season,
        "summary_loaded": bool(summary),
        "directory_loaded": bool(directory),
        "summary_attempts": summary_attempts,
        "away": away_diag,
        "home": home_diag,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }
    return away_out, home_out, diag


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "ESPN_TEAM_DETAIL_URL",
    "FAST_PROFILE_TIMEOUT_SECONDS",
    "enrich_step1_inputs",
]
