"""Step 6 shared NFL live-market player eligibility gate.

This module reuses the frozen Step 5 exact-ID roster/depth/game-day contract and
adds no market pricing, projection, probability, grading, stake, or wager logic.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from sports_api import nfl_prop_player_eligibility_v1 as elig
from sports_api.collectors import nfl_fanduel_passing_yards as base

MODEL_VERSION = "nfl_prop_market_eligibility_v1"
CORE_DEPTH_BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def build_event_market_eligibility(
    *,
    summary: dict[str, Any],
    official: Mapping[str, Any],
    roster_payloads_by_team: Mapping[str, dict[str, Any]],
    allowed_positions: set[str] | frozenset[str],
    espn_get: Callable[..., tuple[dict[str, Any], str]],
    timeout: int,
) -> dict[str, Any]:
    """Build exact athlete-ID market eligibility from the frozen Step 5 gate."""
    league_injury_payload, league_source = espn_get("injuries", timeout=timeout)
    header = (summary or {}).get("header") or {}
    season = header.get("season") or {}
    try:
        year = int(season.get("year") or 2026)
    except (TypeError, ValueError):
        year = 2026

    eligible_ids_by_team: dict[str, frozenset[str]] = {}
    team_diagnostics: dict[str, dict[str, Any]] = {}
    sources: list[str] = [league_source]

    for side in ("away", "home"):
        team = official.get(side) or {}
        team_id = _text(team.get("team_id"))
        if not team_id.isdigit():
            continue

        depth_payload, depth_source = espn_get(
            f"teams/{team_id}/depthcharts",
            timeout=timeout,
        )
        sources.append(depth_source)
        if not elig.parse_depth_chart(depth_payload, allowed_positions):
            depth_payload = base._get_json(
                f"{CORE_DEPTH_BASE}/seasons/{year}/teams/{team_id}/depthcharts",
                headers=base.ESPN_HEADERS,
                timeout=timeout,
            )
            sources.append("sports.core.api.espn.com")

        pool, diag = elig.build_current_prop_pool(
            team_id=team_id,
            roster_payload=dict(roster_payloads_by_team.get(team_id) or {}),
            depth_payload=depth_payload,
            event_summary=summary,
            league_injury_payload=league_injury_payload,
            allowed_positions=allowed_positions,
        )
        eligible_ids_by_team[team_id] = frozenset(pool)
        team_diagnostics[team_id] = diag

    availability = elig.event_availability_state(summary)
    return {
        "model_version": MODEL_VERSION,
        "availability_state": availability.get("state"),
        "prop_gate_open": availability.get("prop_gate_open") is True,
        "eligible_ids_by_team": eligible_ids_by_team,
        "team_diagnostics": team_diagnostics,
        "espn_sources": sorted(set(sources)),
    }


def market_row_eligible(row: Mapping[str, Any], contract: Mapping[str, Any]) -> bool:
    """Exact-ID membership only. Names never participate in the decision."""
    if contract.get("prop_gate_open") is not True:
        return False
    team_id = _text(row.get("official_team_id"))
    athlete_id = _text(row.get("official_athlete_id"))
    allowed = (contract.get("eligible_ids_by_team") or {}).get(team_id, frozenset())
    return bool(team_id.isdigit() and athlete_id.isdigit() and athlete_id in allowed)


def eligible_player_count(contract: Mapping[str, Any]) -> int:
    return sum(len(ids) for ids in (contract.get("eligible_ids_by_team") or {}).values())


__all__ = [
    "MODEL_VERSION",
    "build_event_market_eligibility",
    "eligible_player_count",
    "market_row_eligible",
]
