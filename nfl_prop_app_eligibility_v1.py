"""Step 7 render-time NFL player-prop identity gate.

This app-layer contract sits after the frozen Steps 1-6 data/market gates. It
independently re-checks the exact ESPN event plus current roster athlete IDs
immediately before a Streamlit player identity can render.

Fail closed:
- exact event summary/provider unavailable;
- game-day inactive confirmation pending/unverified;
- event already live/final (pregame prop identity is closed);
- event/team IDs disagree with the payload;
- current roster cannot be verified;
- any rendered athlete ID is absent from the current eligible roster;
- duplicate/malformed athlete identity.

Player names never participate in eligibility. Projection, probability, market
prices, grades, rankings, stake sizing and wager actions are untouched.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

MODEL_VERSION = "NFL PROP APP IDENTITY GATE V1 • STEP 7"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

SnapshotLoader = Callable[[str], dict[str, Any]]
RosterLoader = Callable[[str], tuple[set[str], dict[str, Any]]]


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _load_event_snapshot(event_id: str) -> dict[str, Any]:
    """Load one exact ESPN event and return a pregame-only identity snapshot."""
    import nfl_game_day_availability_v1 as game_day
    import nfl_moneyline_hub_v2 as nfl_data

    event_id = _text(event_id)
    if not event_id.isdigit():
        return {
            "ready": False,
            "state": "UNVERIFIED",
            "prop_gate_open": False,
            "reason": "official ESPN event ID is invalid",
            "team_by_id": {},
        }

    payload, diag = nfl_data._json_get(
        f"{nfl_data.ESPN_BASE}/summary?event={event_id}"
    )
    if not diag.get("ok") or not isinstance(payload, dict):
        return {
            "ready": False,
            "state": "UNVERIFIED",
            "prop_gate_open": False,
            "reason": "exact ESPN event summary unavailable",
            "http": diag.get("http"),
            "team_by_id": {},
        }

    header = payload.get("header") or {}
    competitions = header.get("competitions") or []
    comp = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    summary_event_id = _text(header.get("id") or comp.get("id"))
    if summary_event_id != event_id:
        return {
            "ready": False,
            "state": "UNVERIFIED",
            "prop_gate_open": False,
            "reason": "exact ESPN event identity mismatch",
            "http": diag.get("http"),
            "team_by_id": {},
        }

    status = (comp.get("status") or {}).get("type") or {}
    state = _text(status.get("state")).lower()
    teams: dict[str, str] = {}
    sides: dict[str, str] = {}
    for competitor in comp.get("competitors") or []:
        if not isinstance(competitor, dict):
            continue
        team = competitor.get("team") or {}
        team_id = _text(team.get("id"))
        abbr = _text(team.get("abbreviation")).upper()
        side = _text(competitor.get("homeAway")).lower()
        if team_id.isdigit() and abbr:
            teams[team_id] = abbr
            if side in {"away", "home"}:
                sides[side] = abbr

    if len(teams) != 2 or set(sides) != {"away", "home"}:
        return {
            "ready": False,
            "state": "UNVERIFIED",
            "prop_gate_open": False,
            "reason": "exact ESPN event team identity incomplete",
            "http": diag.get("http"),
            "team_by_id": teams,
        }

    # Step 5 permanently closes pregame player-prop identity after kickoff.
    if state in {"in", "post"}:
        return {
            "ready": True,
            "state": "CLOSED",
            "prop_gate_open": False,
            "reason": "pregame player-prop identity closed after kickoff",
            "http": diag.get("http"),
            "team_by_id": teams,
        }

    event_map = nfl_data._parse_injuries(payload)
    availability = game_day.event_availability_snapshot(
        event_id,
        sides["away"],
        sides["home"],
        state,
        event_map=event_map,
        event_diag=diag,
    )
    return {
        "ready": True,
        "state": _text(availability.get("state"), "UNVERIFIED").upper(),
        "prop_gate_open": availability.get("prop_gate_open") is True,
        "reason": "" if availability.get("prop_gate_open") is True else (
            "final game-day inactive confirmation is not verified"
        ),
        "http": diag.get("http"),
        "team_by_id": teams,
    }


def _eligible_ids_for_team(team_abbr: str) -> tuple[set[str], dict[str, Any]]:
    """Current roster membership by exact ESPN athlete ID only."""
    import nfl_game_day_availability_v1 as game_day

    ids, _names, diag = game_day.current_prop_eligible_keys(_text(team_abbr).upper())
    return {str(value) for value in ids if str(value).isdigit()}, dict(diag or {})


def _fail_context(
    payload: Any,
    event_id: str,
    reason: str,
    *,
    state: str = "UNVERIFIED",
) -> dict[str, Any]:
    out = dict(payload) if isinstance(payload, Mapping) else {}
    out.update({
        "ready": False,
        "data_available": False,
        "official_event_id": _text(event_id),
        "teams": [],
        "reason": _text(reason, "Step 7 app identity verification failed closed"),
        "step7_app_identity_verified": False,
        "step7_app_identity_state": _text(state, "UNVERIFIED"),
        "sportsbook_influence": 0.0,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    })
    return out


def guard_context_payload(
    payload: Any,
    official_event_id: str,
    *,
    allowed_positions: set[str] | frozenset[str],
    snapshot_loader: SnapshotLoader | None = None,
    roster_loader: RosterLoader | None = None,
) -> dict[str, Any]:
    """Require exact live event + roster identity for every app player row."""
    event_id = _text(official_event_id)
    if not isinstance(payload, Mapping):
        return _fail_context(payload, event_id, "player context payload is not an object")
    if payload.get("ready") is not True:
        return dict(payload)
    if _text(payload.get("official_event_id")) != event_id or not event_id.isdigit():
        return _fail_context(payload, event_id, "context event identity mismatch")

    snapshot = (snapshot_loader or _load_event_snapshot)(event_id)
    state = _text(snapshot.get("state"), "UNVERIFIED").upper()
    if snapshot.get("ready") is not True or snapshot.get("prop_gate_open") is not True:
        return _fail_context(
            payload,
            event_id,
            _text(snapshot.get("reason"), "exact game-day identity is not verified"),
            state=state,
        )

    team_by_id = {
        _text(team_id): _text(abbr).upper()
        for team_id, abbr in (snapshot.get("team_by_id") or {}).items()
        if _text(team_id).isdigit() and _text(abbr)
    }
    teams = payload.get("teams")
    if not isinstance(teams, list) or len(teams) != 2 or len(team_by_id) != 2:
        return _fail_context(payload, event_id, "two-team exact identity contract failed", state=state)

    allowed = {_text(pos).upper() for pos in allowed_positions}
    load_roster = roster_loader or _eligible_ids_for_team
    verified_teams: list[dict[str, Any]] = []
    seen_athletes: set[str] = set()
    seen_teams: set[str] = set()

    for raw_team in teams:
        if not isinstance(raw_team, Mapping):
            return _fail_context(payload, event_id, "team row is not an object", state=state)
        team_id = _text(raw_team.get("official_team_id"))
        abbr = _text(raw_team.get("team_abbreviation")).upper()
        expected_abbr = team_by_id.get(team_id, "")
        if (
            not team_id.isdigit()
            or not expected_abbr
            or (abbr and abbr != expected_abbr)
            or team_id in seen_teams
        ):
            return _fail_context(payload, event_id, "team identity no longer matches exact event", state=state)
        seen_teams.add(team_id)

        current_ids, roster_diag = load_roster(expected_abbr)
        if not (roster_diag or {}).get("ok") or not current_ids:
            return _fail_context(
                payload,
                event_id,
                f"current roster identity unavailable for {expected_abbr}",
                state=state,
            )

        raw_players = raw_team.get("players") or []
        if not isinstance(raw_players, list):
            return _fail_context(payload, event_id, "player list is invalid", state=state)

        verified_players: list[dict[str, Any]] = []
        for raw_player in raw_players:
            if not isinstance(raw_player, Mapping):
                return _fail_context(payload, event_id, "player row is not an object", state=state)
            athlete_id = _text(raw_player.get("official_athlete_id"))
            player_team_id = _text(raw_player.get("official_team_id"))
            position = _text(raw_player.get("position")).upper()
            if (
                not athlete_id.isdigit()
                or player_team_id != team_id
                or athlete_id in seen_athletes
                or (allowed and position not in allowed)
                or athlete_id not in current_ids
            ):
                return _fail_context(
                    payload,
                    event_id,
                    "one or more app player identities are no longer current-roster verified",
                    state=state,
                )
            seen_athletes.add(athlete_id)
            row = dict(raw_player)
            row["step7_app_identity_verified"] = True
            verified_players.append(row)

        team = dict(raw_team)
        team["team_abbreviation"] = expected_abbr
        team["players"] = verified_players
        verified_teams.append(team)

    out = dict(payload)
    out["teams"] = verified_teams
    out["step7_app_identity_verified"] = True
    out["step7_app_identity_state"] = state
    out["step7_app_identity_version"] = MODEL_VERSION
    return out


def _fail_passing_identity(
    resolved: Any,
    reason: str,
    *,
    state: str = "UNVERIFIED",
) -> dict[str, Any]:
    out = deepcopy(resolved) if isinstance(resolved, Mapping) else {}
    out["ready"] = False
    out["identity_ready"] = False
    out["prop_availability_ready"] = False
    out["reason"] = _text(reason, "Step 7 app identity verification failed closed")
    out["step7_app_identity_verified"] = False
    out["step7_app_identity_state"] = _text(state, "UNVERIFIED")
    for side in ("away", "home"):
        ctx = dict(out.get(side) or {})
        ctx["qbs"] = []
        ctx["qb1"] = {}
        ctx["identity_verified"] = False
        ctx["availability_alert"] = True
        out[side] = ctx
    return out


def guard_passing_identity(
    game: Mapping[str, Any],
    resolved: Any,
    *,
    snapshot_loader: SnapshotLoader | None = None,
    roster_loader: RosterLoader | None = None,
) -> dict[str, Any]:
    """Strip QB identity unless the render-time exact-ID proof is still GREEN."""
    event_id = _text((game or {}).get("game_id"))
    if not isinstance(resolved, Mapping) or resolved.get("ready") is not True:
        return _fail_passing_identity(
            resolved,
            _text((resolved or {}).get("reason") if isinstance(resolved, Mapping) else ""),
        )
    if _text(resolved.get("game_id")) != event_id or not event_id.isdigit():
        return _fail_passing_identity(resolved, "Passing Yards event identity mismatch")

    snapshot = (snapshot_loader or _load_event_snapshot)(event_id)
    state = _text(snapshot.get("state"), "UNVERIFIED").upper()
    if snapshot.get("ready") is not True or snapshot.get("prop_gate_open") is not True:
        return _fail_passing_identity(
            resolved,
            _text(snapshot.get("reason"), "exact game-day identity is not verified"),
            state=state,
        )

    team_by_id = {
        _text(team_id): _text(abbr).upper()
        for team_id, abbr in (snapshot.get("team_by_id") or {}).items()
        if _text(team_id).isdigit() and _text(abbr)
    }
    if len(team_by_id) != 2:
        return _fail_passing_identity(resolved, "Passing Yards event teams are not exact", state=state)

    load_roster = roster_loader or _eligible_ids_for_team
    seen: set[str] = set()
    for side in ("away", "home"):
        ctx = resolved.get(side) or {}
        qb = ctx.get("qb1") or {}
        team_id = _text(ctx.get("team_id"))
        abbr = _text(ctx.get("abbr")).upper()
        athlete_id = _text(qb.get("athlete_id"))
        expected_abbr = team_by_id.get(team_id, "")
        if (
            ctx.get("identity_verified") is not True
            or not athlete_id.isdigit()
            or not team_id.isdigit()
            or not expected_abbr
            or abbr != expected_abbr
            or athlete_id in seen
        ):
            return _fail_passing_identity(resolved, "Passing Yards QB identity is not exact", state=state)

        current_ids, roster_diag = load_roster(expected_abbr)
        if not (roster_diag or {}).get("ok") or athlete_id not in current_ids:
            return _fail_passing_identity(
                resolved,
                f"current roster no longer verifies {expected_abbr} QB identity",
                state=state,
            )
        seen.add(athlete_id)

    out = deepcopy(resolved)
    out["step7_app_identity_verified"] = True
    out["step7_app_identity_state"] = state
    out["step7_app_identity_version"] = MODEL_VERSION
    return out


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "guard_context_payload",
    "guard_passing_identity",
]
