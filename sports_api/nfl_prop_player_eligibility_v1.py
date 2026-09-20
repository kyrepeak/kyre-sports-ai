"""Shared NFL prop-player eligibility contract.

Exact-ID, fail-closed player identity for current player-prop pools.

A player is eligible only when:
- present on the current ESPN team roster;
- roster status/group is prop-eligible;
- present on the current ESPN depth chart at an allowed position;
- exact-event game-day availability is CONFIRMED;
- the player is not listed unavailable/inactive for that event.

This module contains no projection, probability, market, ranking, or wager logic.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

MODEL_VERSION = "nfl_prop_player_eligibility_v1"

UNAVAILABLE_TOKENS = (
    "OUT",
    "INACTIVE",
    "INJURED RESERVE",
    "IR",
    "PUP",
    "SUSPENDED",
    "NFI",
    "RESERVE",
)

ROSTER_INELIGIBLE_TOKENS = (
    "INJURED RESERVE",
    "RESERVE/IR",
    "RESERVE PUP",
    "RESERVE/PUP",
    "PUP",
    "NFI",
    "SUSPENDED",
    "PRACTICE SQUAD",
    "PRACTICE-SQUAD",
    "EXEMPT",
    "COMMISSIONER",
)

ROSTER_ACTIVE_OVERRIDE_TOKENS = (
    "ACTIVE",
    "ELEVATED",
    "PROMOTED",
)


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _status_text(value: Any) -> str:
    if isinstance(value, dict):
        return _text(
            value.get("displayName")
            or value.get("description")
            or value.get("name")
            or value.get("abbreviation")
        )
    return _text(value)


def _status_key(value: Any) -> str:
    return "".join(ch for ch in _text(value).upper() if ch.isalnum())


def _contains_token(value: Any, tokens: Iterable[str]) -> bool:
    raw = _text(value).upper()
    key = _status_key(raw)
    return any(token in raw or _status_key(token) in key for token in tokens)


def is_unavailable_status(value: Any) -> bool:
    return _contains_token(value, UNAVAILABLE_TOKENS)


def is_roster_row_eligible(*, status: Any, group_label: Any, active: Any) -> bool:
    combined = " ".join(part for part in (_text(status), _text(group_label)) if part)
    if _contains_token(combined, ROSTER_ACTIVE_OVERRIDE_TOKENS):
        return active is not False
    if active is False:
        return False
    if _contains_token(combined, ROSTER_INELIGIBLE_TOKENS):
        return False
    return True


def parse_current_roster(
    payload: dict[str, Any],
    allowed_positions: set[str] | frozenset[str] | None = None,
) -> dict[str, dict[str, Any]]:
    allowed = {str(x).upper() for x in allowed_positions} if allowed_positions else None
    found: dict[str, dict[str, Any]] = {}

    for group in (payload or {}).get("athletes", []) or []:
        if not isinstance(group, dict):
            continue
        group_position = group.get("position")
        if isinstance(group_position, dict):
            group_position = group_position.get("abbreviation") or group_position.get("name")
        group_label = _text(
            group.get("displayName")
            or group.get("name")
            or group.get("label")
            or group_position
        )
        for item in group.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            athlete_id = _text(item.get("id"))
            name = _text(item.get("displayName") or item.get("fullName"))
            position = item.get("position") or {}
            pos = _text(
                position.get("abbreviation") if isinstance(position, dict) else position
            ).upper()
            if not athlete_id.isdigit() or not name or not pos:
                continue
            if allowed is not None and pos not in allowed:
                continue
            status = _status_text(item.get("status"))
            active = item.get("active")
            if not is_roster_row_eligible(
                status=status,
                group_label=group_label,
                active=active,
            ):
                continue
            found[athlete_id] = {
                "official_athlete_id": athlete_id,
                "player_name": name,
                "position": pos,
                "roster_status": status,
                "roster_group": group_label,
            }
    return found


def parse_depth_chart(
    payload: dict[str, Any],
    allowed_positions: set[str] | frozenset[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Parse both ESPN Site (depthCharts) and ESPN Core (items) depth shapes."""
    allowed = {str(x).upper() for x in allowed_positions} if allowed_positions else None
    found: dict[str, dict[str, Any]] = {}
    charts = (payload or {}).get("depthCharts")
    if not isinstance(charts, list):
        charts = (payload or {}).get("items") or []
    for chart in charts or []:
        if not isinstance(chart, dict):
            continue
        positions = chart.get("positions") or {}
        blocks = list(positions.values()) if isinstance(positions, dict) else positions
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            pos_obj = block.get("position") or {}
            pos = _text(
                pos_obj.get("abbreviation") if isinstance(pos_obj, dict) else pos_obj
            ).upper()
            if not pos or (allowed is not None and pos not in allowed):
                continue
            for idx, entry in enumerate(block.get("athletes", []) or [], start=1):
                if not isinstance(entry, dict):
                    continue
                athlete = entry.get("athlete") or {}
                athlete_id = _text(athlete.get("id")) if isinstance(athlete, dict) else ""
                name = _text(
                    athlete.get("displayName") or athlete.get("fullName")
                ) if isinstance(athlete, dict) else ""
                ref = _text(
                    athlete.get("$ref") or athlete.get("ref")
                ) if isinstance(athlete, dict) else _text(athlete)
                if not athlete_id and ref:
                    match = re.search(r"/athletes/(\d+)", ref)
                    athlete_id = match.group(1) if match else ""
                if not athlete_id.isdigit():
                    continue
                try:
                    rank = int(entry.get("rank") or idx)
                except (TypeError, ValueError):
                    rank = idx
                prior = found.get(athlete_id)
                if prior is None or rank < int(prior.get("depth_rank") or 99):
                    found[athlete_id] = {
                        "official_athlete_id": athlete_id,
                        "player_name": name,
                        "position": pos,
                        "depth_rank": rank,
                    }
    return found


def event_game_state(summary: dict[str, Any]) -> str:
    header = (summary or {}).get("header") or {}
    competitions = header.get("competitions") or []
    comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    status = comp.get("status") or {}
    status_type = status.get("type") or {}
    return _text(status_type.get("state")).lower()


def event_team_ids(summary: dict[str, Any]) -> list[str]:
    header = (summary or {}).get("header") or {}
    competitions = header.get("competitions") or []
    comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    out: list[str] = []
    for competitor in comp.get("competitors", []) or []:
        if not isinstance(competitor, dict):
            continue
        team_id = _text((competitor.get("team") or {}).get("id"))
        if team_id.isdigit():
            out.append(team_id)
    return list(dict.fromkeys(out))


def event_unavailable_by_team(summary: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_team: dict[str, list[dict[str, Any]]] = {}
    for block in (summary or {}).get("injuries", []) or []:
        if not isinstance(block, dict):
            continue
        team = block.get("team") or {}
        team_id = _text(team.get("id"))
        if not team_id.isdigit():
            continue
        rows = by_team.setdefault(team_id, [])
        nested = block.get("injuries") or block.get("items") or []
        for item in nested:
            if not isinstance(item, dict):
                continue
            athlete = item.get("athlete") or item.get("player") or {}
            athlete_id = _text(athlete.get("id"))
            name = _text(
                athlete.get("displayName")
                or athlete.get("fullName")
                or item.get("name")
            )
            status = _status_text(
                item.get("status") or item.get("type") or item.get("designation")
            )
            if not athlete_id.isdigit() or not is_unavailable_status(status):
                continue
            rows.append({
                "official_athlete_id": athlete_id,
                "player_name": name,
                "status": status,
            })
    return by_team


def event_availability_state(summary: dict[str, Any]) -> dict[str, Any]:
    team_ids = event_team_ids(summary)
    state = event_game_state(summary)
    unavailable = event_unavailable_by_team(summary)
    if len(team_ids) != 2:
        return {
            "state": "UNVERIFIED",
            "prop_gate_open": False,
            "game_state": state,
            "team_ids": team_ids,
            "unavailable": unavailable,
        }

    explicit_both = all(
        any("INACTIVE" in _text(row.get("status")).upper() for row in unavailable.get(team_id, []))
        for team_id in team_ids
    )
    live_or_final_both = (
        state in {"in", "post"}
        and all(bool(unavailable.get(team_id)) for team_id in team_ids)
    )

    availability = "CONFIRMED" if (explicit_both or live_or_final_both) else "PENDING"
    return {
        "state": availability,
        "prop_gate_open": availability == "CONFIRMED",
        "game_state": state,
        "team_ids": team_ids,
        "unavailable": unavailable,
    }


def build_current_prop_pool(
    *,
    team_id: str,
    roster_payload: dict[str, Any],
    depth_payload: dict[str, Any],
    event_summary: dict[str, Any],
    allowed_positions: set[str] | frozenset[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    team_id = _text(team_id)
    availability = event_availability_state(event_summary)
    if team_id not in availability.get("team_ids", []):
        return {}, {**availability, "reason": "team missing from exact event"}
    if not availability.get("prop_gate_open"):
        return {}, {**availability, "reason": "final game-day availability not confirmed"}

    roster = parse_current_roster(roster_payload, allowed_positions)
    depth = parse_depth_chart(depth_payload, allowed_positions)
    unavailable_ids = {
        _text(row.get("official_athlete_id"))
        for row in (availability.get("unavailable") or {}).get(team_id, [])
        if _text(row.get("official_athlete_id")).isdigit()
    }

    pool: dict[str, dict[str, Any]] = {}
    for athlete_id, row in roster.items():
        depth_row = depth.get(athlete_id)
        if not depth_row or athlete_id in unavailable_ids:
            continue
        pool[athlete_id] = {
            **row,
            "depth_rank": depth_row.get("depth_rank"),
            "depth_verified": True,
            "game_day_available": True,
        }

    diag = {
        **availability,
        "reason": "" if pool else "no current depth-chart prop players survived eligibility",
        "current_roster_players": len(roster),
        "current_depth_players": len(depth),
        "unavailable_players": len(unavailable_ids),
        "prop_eligible_players": len(pool),
    }
    return pool, diag


__all__ = [
    "MODEL_VERSION",
    "ROSTER_ACTIVE_OVERRIDE_TOKENS",
    "ROSTER_INELIGIBLE_TOKENS",
    "UNAVAILABLE_TOKENS",
    "build_current_prop_pool",
    "event_availability_state",
    "event_game_state",
    "event_team_ids",
    "event_unavailable_by_team",
    "is_roster_row_eligible",
    "is_unavailable_status",
    "parse_current_roster",
    "parse_depth_chart",
]
