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


def _safe(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def is_unavailable_status(status: Any) -> bool:
    value = _safe(status).upper()
    if not value:
        return False
    return any(token in value for token in UNAVAILABLE_TOKENS)


def _status_text(value: Any) -> str:
    if isinstance(value, dict):
        return _safe(
            value.get("displayName")
            or value.get("description")
            or value.get("name")
            or value.get("abbreviation")
        )
    return _safe(value)


def _status_key(value: Any) -> str:
    return "".join(ch for ch in _safe(value).upper() if ch.isalnum())


def is_prop_eligible_roster_row(row: dict) -> bool:
    """Fail closed on reserve/practice-squad/suspended roster states."""
    active_flag = row.get("active")
    combined = " ".join(
        part for part in (
            _safe(row.get("roster_status")),
            _safe(row.get("group_label")),
        )
        if part
    ).upper()
    combined_key = _status_key(combined)

    active_match = any(
        token in combined or _status_key(token) in combined_key
        for token in ROSTER_ACTIVE_OVERRIDE_TOKENS
    )
    if active_match:
        return active_flag is not False
    if active_flag is False:
        return False

    ineligible_match = any(
        token in combined or _status_key(token) in combined_key
        for token in ROSTER_INELIGIBLE_TOKENS
    )
    if ineligible_match:
        return False
    return True


def current_prop_eligible_players(team_abbr: str) -> tuple[list[dict], dict]:
    rows, diag = load_current_team_roster(team_abbr)
    eligible = [row for row in rows if row.get("prop_eligible")]
    return eligible, diag


def current_prop_eligible_keys(team_abbr: str) -> tuple[set[str], set[str], dict]:
    rows, diag = current_prop_eligible_players(team_abbr)
    ids = {_safe(row.get("athlete_id")) for row in rows if _safe(row.get("athlete_id"))}
    names = {_safe(row.get("name")).lower() for row in rows if _safe(row.get("name"))}
    return ids, names, diag


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


def _team_unavailable_rows(event_map: dict | None, team_abbr: str) -> list[dict]:
    rows = list((event_map or {}).get(_safe(team_abbr).upper(), []) or [])
    return [row for row in rows if is_unavailable_status(row.get("status"))]


def _team_explicit_inactive_rows(event_map: dict | None, team_abbr: str) -> list[dict]:
    rows = list((event_map or {}).get(_safe(team_abbr).upper(), []) or [])
    return [
        row for row in rows
        if "INACTIVE" in _safe(row.get("status")).upper()
    ]


def event_availability_snapshot(
    game_id: str,
    away_abbr: str,
    home_abbr: str,
    game_state: str = "",
    *,
    event_map: dict | None = None,
    event_diag: dict | None = None,
) -> dict:
    """Return fail-closed game-day availability state for one exact event.

    CONFIRMED:
      - both teams have explicit INACTIVE rows before kickoff, or
      - once the game is live/final, both teams have exact-event unavailable rows.
    PENDING:
      - provider is healthy, but final game-day inactive confirmation is not complete.
    UNVERIFIED:
      - exact-event provider failed or team identity is incomplete.

    Only CONFIRMED may open the prop-identity gate.
    """
    game_id = _safe(game_id)
    away = _safe(away_abbr).upper()
    home = _safe(home_abbr).upper()
    state = _safe(game_state).lower()

    if event_map is None or event_diag is None:
        event_map, event_diag = load_event_injury_map(game_id)
    event_diag = event_diag if isinstance(event_diag, dict) else {}

    result = {
        "game_id": game_id,
        "away_abbr": away,
        "home_abbr": home,
        "game_state": state,
        "state": "UNVERIFIED",
        "prop_gate_open": False,
        "provider_ok": bool(event_diag.get("ok")),
        "http": event_diag.get("http"),
        "away_rows": len((event_map or {}).get(away, []) or []),
        "home_rows": len((event_map or {}).get(home, []) or []),
        "away_unavailable": _team_unavailable_rows(event_map, away),
        "home_unavailable": _team_unavailable_rows(event_map, home),
        "away_explicit_inactive": _team_explicit_inactive_rows(event_map, away),
        "home_explicit_inactive": _team_explicit_inactive_rows(event_map, home),
    }

    if not game_id.isdigit() or not away or not home or not result["provider_ok"]:
        return result

    explicit_both = bool(
        result["away_explicit_inactive"] and result["home_explicit_inactive"]
    )
    live_or_final_both = bool(
        state in {"in", "post"}
        and result["away_unavailable"]
        and result["home_unavailable"]
    )

    if explicit_both or live_or_final_both:
        result["state"] = "CONFIRMED"
        result["prop_gate_open"] = True
    else:
        result["state"] = "PENDING"
    return result


@st.cache_data(ttl=60, show_spinner=False)
def load_game_day_scoreboard(game_date: str):
    raw = "".join(ch for ch in _safe(game_date) if ch.isdigit())
    if len(raw) != 8:
        return [], {"ok": False, "http": None, "reason": "invalid YYYY-MM-DD date"}

    payload, diag = nfl_data._json_get(
        f"{nfl_data.ESPN_BASE}/scoreboard?dates={raw}"
    )
    games: list[dict] = []
    if diag.get("ok"):
        for event in (payload or {}).get("events", []) or []:
            competition = ((event.get("competitions") or [{}])[0] or {})
            status = ((competition.get("status") or event.get("status") or {}).get("type") or {})
            row = {
                "game_id": _safe(event.get("id")),
                "state": _safe(status.get("state")).lower(),
                "away_abbr": "",
                "home_abbr": "",
            }
            for competitor in competition.get("competitors", []) or []:
                team = competitor.get("team") or {}
                abbr = _safe(team.get("abbreviation")).upper()
                side = _safe(competitor.get("homeAway")).lower()
                if side == "away":
                    row["away_abbr"] = abbr
                elif side == "home":
                    row["home_abbr"] = abbr
            if row["game_id"] and row["away_abbr"] and row["home_abbr"]:
                games.append(row)
    return games, diag


def audit_game_day_availability(game_date: str) -> dict:
    games, scoreboard_diag = load_game_day_scoreboard(game_date)
    rows: list[dict] = []
    teams: set[str] = set()
    for game in games:
        snapshot = event_availability_snapshot(
            game["game_id"],
            game["away_abbr"],
            game["home_abbr"],
            game.get("state", ""),
        )
        rows.append(snapshot)
        teams.update((game["away_abbr"], game["home_abbr"]))

    unverified = [row for row in rows if row.get("state") == "UNVERIFIED"]
    confirmed = [row for row in rows if row.get("state") == "CONFIRMED"]
    pending = [row for row in rows if row.get("state") == "PENDING"]
    return {
        "ready": bool(scoreboard_diag.get("ok") and games and not unverified),
        "scoreboard_http": scoreboard_diag.get("http"),
        "games_total": len(rows),
        "teams_total": len(teams),
        "confirmed_games": len(confirmed),
        "pending_games": len(pending),
        "unverified_games": len(unverified),
        "games": rows,
    }


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
        group_label = _safe(
            group.get("displayName")
            or group.get("name")
            or group.get("label")
            or group_position
        )
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
                "roster_status": _status_text(item.get("status")),
                "active": item.get("active"),
                "group_label": group_label,
            }
            row["prop_eligible"] = is_prop_eligible_roster_row(row)
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
        eligible = [row for row in rows if row.get("prop_eligible")]
        skill = {
            pos: sum(1 for row in eligible if row.get("position") == pos)
            for pos in ("QB", "RB", "WR", "TE")
        }
        results[abbr] = {
            "ok": bool(diag.get("ok") and rows),
            "http": diag.get("http"),
            "players": len(rows),
            "prop_eligible_players": len(eligible),
            "transaction_excluded_players": len(rows) - len(eligible),
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
    "ROSTER_INELIGIBLE_TOKENS",
    "ROSTER_ACTIVE_OVERRIDE_TOKENS",
    "current_prop_eligible_keys",
    "current_prop_eligible_players",
    "is_prop_eligible_roster_row",
    "audit_all_32_rosters",
    "audit_game_day_availability",
    "event_availability_snapshot",
    "is_unavailable_status",
    "load_current_team_roster",
    "load_event_injury_map",
    "load_game_day_scoreboard",
    "merge_injury_maps",
    "parse_current_roster",
]
