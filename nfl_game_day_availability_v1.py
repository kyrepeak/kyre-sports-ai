"""NFL current roster + game-day availability V1.

Data-only contract:
- current team roster comes from ESPN's live team roster endpoint;
- game-day injuries come from the exact ESPN event summary;
- event-specific status overrides the league-wide injury feed;
- unavailable players fail closed for active prop identity.

No projection, probability, market, grading, or staking logic lives here.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_moneyline_hub_v2 as nfl_data

MODEL_VERSION = "NFL CURRENT ROSTER + GAME-DAY AVAILABILITY V1"

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


def _safe(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def is_unavailable_status(status: Any) -> bool:
    value = _safe(status).upper()
    if not value:
        return False
    return any(token in value for token in UNAVAILABLE_TOKENS)


def _player_key(row: dict) -> str:
    athlete_id = _safe(row.get("athlete_id"))
    if athlete_id:
        return f"id:{athlete_id}"
    name = _safe(row.get("name")).lower()
    return f"name:{name}" if name else ""


def merge_injury_maps(league_map: dict | None, event_map: dict | None) -> dict:
    """Merge league + exact-event statuses with event data authoritative."""
    merged: dict[str, list[dict]] = {}
    teams = set((league_map or {}).keys()) | set((event_map or {}).keys())
    for team in teams:
        rows: dict[str, dict] = {}
        for source in ((league_map or {}).get(team, []), (event_map or {}).get(team, [])):
            for item in source or []:
                if not isinstance(item, dict):
                    continue
                row = dict(item)
                key = _player_key(row)
                if key:
                    rows[key] = row
        merged[str(team).upper()] = list(rows.values())
    return merged


@st.cache_data(ttl=60, show_spinner=False)
def load_event_injury_map(game_id: str):
    game_id = _safe(game_id)
    if not game_id.isdigit():
        return {}, {"ok": False, "http": None, "reason": "invalid ESPN event id"}
    payload, diag = nfl_data._json_get(
        f"{nfl_data.ESPN_BASE}/summary?event={game_id}"
    )
    parsed = nfl_data._parse_injuries(payload) if diag.get("ok") else {}
    return parsed, diag


def parse_current_roster(payload: dict, team_abbr: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for group in (payload or {}).get("athletes", []) or []:
        if not isinstance(group, dict):
            continue
        group_position = group.get("position")
        if isinstance(group_position, dict):
            group_position = group_position.get("abbreviation") or group_position.get("name")
        for item in group.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            pos = item.get("position") or {}
            position = _safe(
                pos.get("abbreviation") if isinstance(pos, dict) else pos,
                _safe(group_position, "—"),
            )
            row = {
                "athlete_id": _safe(item.get("id")),
                "name": _safe(item.get("displayName") or item.get("fullName"), "Unknown player"),
                "position": position.upper(),
                "team": _safe(team_abbr).upper(),
            }
            key = _player_key(row)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out


@st.cache_data(ttl=120, show_spinner=False)
def load_current_team_roster(team_abbr: str):
    abbr = _safe(team_abbr).upper()
    team_id = nfl_data.TEAM_IDS.get(abbr, "")
    if not team_id:
        return [], {"ok": False, "http": None, "reason": "unknown team"}
    payload, diag = nfl_data._roster_payload(team_id)
    rows = parse_current_roster(payload, abbr) if diag.get("ok") else []
    return rows, diag


def audit_all_32_rosters() -> dict:
    results = {}
    for abbr in sorted(nfl_data.TEAM_IDS):
        rows, diag = load_current_team_roster(abbr)
        skill = {
            pos: sum(1 for row in rows if row.get("position") == pos)
            for pos in ("QB", "RB", "WR", "TE")
        }
        results[abbr] = {
            "ok": bool(diag.get("ok") and rows),
            "http": diag.get("http"),
            "players": len(rows),
            "skill_counts": skill,
        }
    green = [
        team for team, row in results.items()
        if row["ok"] and row["players"] >= 40 and row["skill_counts"]["QB"] >= 1
    ]
    return {
        "ready": len(green) == 32,
        "teams_verified": len(green),
        "teams_total": 32,
        "teams": results,
    }


__all__ = [
    "MODEL_VERSION",
    "UNAVAILABLE_TOKENS",
    "audit_all_32_rosters",
    "is_unavailable_status",
    "load_current_team_roster",
    "load_event_injury_map",
    "merge_injury_maps",
    "parse_current_roster",
]
