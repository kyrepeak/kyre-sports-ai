"""NFL Rushing Yards V16 — Step 7 render-time player identity gate.

Additive over frozen V15. It re-validates the cached/current context against the
exact ESPN event and current roster IDs immediately before player cards render.

Step 3 live-game repair keeps the frozen shared identity gate authoritative. For
an exact LIVE bridge only, it removes otherwise well-formed API player rows
whose exact athlete ID is absent from the same current-roster allowlist the
shared gate will re-check. Malformed/team-mismatched rows are never hidden and
still fail closed in the shared guard.
"""
from __future__ import annotations

from typing import Any, Mapping

import nfl_prop_app_eligibility_v1 as identity_gate
import nfl_rushing_yards_hub_v1 as base_page
import nfl_rushing_yards_hub_v15 as prior
from nfl_prop_app_eligibility_v1 import guard_context_payload

MODEL_VERSION = "NFL RUSHING YARDS V16 • STEP 7 APP IDENTITY FAIL-CLOSED • LIVE ROSTER RECONCILIATION"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v15"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_ALLOWED_POSITIONS = frozenset({"QB", "RB", "FB", "WR", "TE"})

_ORIGINAL_LOAD = base_page._load_rushing_context


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _is_live_identity_bridge(snapshot: Mapping[str, Any]) -> bool:
    state = _text(snapshot.get("state")).upper()
    identity_state = _text(snapshot.get("identity_state") or state).upper()
    return bool(
        snapshot.get("ready") is True
        and state == "CLOSED"
        and identity_state == "LIVE"
        and snapshot.get("identity_gate_open") is True
        and snapshot.get("prop_gate_open") is not True
    )


def _reconcile_live_roster_payload(
    payload: Any,
    snapshot: Mapping[str, Any],
    roster_loader,
) -> tuple[Any, int]:
    """Drop only exact stale athlete IDs during the verified LIVE identity window.

    Fail-closed invariants:
    - no filtering outside the LIVE bridge;
    - no filtering when team/current-roster identity cannot be proven;
    - malformed rows and team-ID mismatches remain for the shared guard to reject;
    - the shared guard still performs the final authoritative verification.
    """
    if not _is_live_identity_bridge(snapshot) or not isinstance(payload, Mapping):
        return payload, 0
    if payload.get("ready") is not True:
        return payload, 0

    team_by_id = {
        _text(team_id): _text(abbr).upper()
        for team_id, abbr in (snapshot.get("team_by_id") or {}).items()
        if _text(team_id).isdigit() and _text(abbr)
    }
    teams = payload.get("teams")
    if len(team_by_id) != 2 or not isinstance(teams, list) or len(teams) != 2:
        return payload, 0

    filtered_count = 0
    reconciled_teams: list[Any] = []
    for raw_team in teams:
        if not isinstance(raw_team, Mapping):
            reconciled_teams.append(raw_team)
            continue

        team_id = _text(raw_team.get("official_team_id"))
        expected_abbr = team_by_id.get(team_id, "")
        supplied_abbr = _text(raw_team.get("team_abbreviation")).upper()
        if (
            not team_id.isdigit()
            or not expected_abbr
            or (supplied_abbr and supplied_abbr != expected_abbr)
        ):
            reconciled_teams.append(dict(raw_team))
            continue

        current_ids, roster_diag = roster_loader(expected_abbr)
        current_ids = {
            _text(value)
            for value in (current_ids or set())
            if _text(value).isdigit()
        }
        if not (roster_diag or {}).get("ok") or not current_ids:
            reconciled_teams.append(dict(raw_team))
            continue

        raw_players = raw_team.get("players")
        if not isinstance(raw_players, list):
            reconciled_teams.append(dict(raw_team))
            continue

        players: list[Any] = []
        for raw_player in raw_players:
            if not isinstance(raw_player, Mapping):
                players.append(raw_player)
                continue
            athlete_id = _text(raw_player.get("official_athlete_id"))
            player_team_id = _text(raw_player.get("official_team_id"))
            if (
                athlete_id.isdigit()
                and player_team_id == team_id
                and athlete_id not in current_ids
            ):
                filtered_count += 1
                continue
            players.append(dict(raw_player))

        team = dict(raw_team)
        team["players"] = players
        reconciled_teams.append(team)

    out = dict(payload)
    out["teams"] = reconciled_teams
    out["data_available"] = any(
        isinstance(team, Mapping) and bool(team.get("players"))
        for team in reconciled_teams
    )
    return out, filtered_count


def _load_rushing_context_step7(event_id: str) -> dict:
    event_id = str(event_id)
    payload = _ORIGINAL_LOAD(event_id)
    snapshot = identity_gate._load_event_snapshot(event_id)

    roster_cache: dict[str, tuple[set[str], dict[str, Any]]] = {}

    def load_roster(abbr: str) -> tuple[set[str], dict[str, Any]]:
        key = _text(abbr).upper()
        if key not in roster_cache:
            ids, diag = identity_gate._eligible_ids_for_team(key)
            roster_cache[key] = (
                {_text(value) for value in ids if _text(value).isdigit()},
                dict(diag or {}),
            )
        ids, diag = roster_cache[key]
        return set(ids), dict(diag)

    reconciled, filtered_count = _reconcile_live_roster_payload(
        payload,
        snapshot,
        load_roster,
    )
    result = guard_context_payload(
        reconciled,
        event_id,
        allowed_positions=_ALLOWED_POSITIONS,
        snapshot_loader=lambda _event_id: dict(snapshot),
        roster_loader=load_roster,
    )
    if result.get("step7_app_live_identity_verified") is True:
        result["step3_live_roster_filtered_count"] = filtered_count
    return result


def render_nfl_rushing_yards_hub() -> None:
    original = base_page._load_rushing_context
    base_page._load_rushing_context = _load_rushing_context_step7
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        base_page._load_rushing_context = original


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V16 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_load_rushing_context_step7",
    "_reconcile_live_roster_payload",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
