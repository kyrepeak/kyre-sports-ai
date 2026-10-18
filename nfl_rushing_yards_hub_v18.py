"""NFL Rushing Yards V18 — FanDuel-only player display and team grouping.

Additive over frozen V17. A player is display-eligible only when the current
exact-ID FanDuel Rushing Yards market is ready and carries a finite line. The
surviving players are kept together by team while workload only controls order
inside each team. Projection math and sportsbook influence remain unchanged.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import nfl_rushing_yards_hub_v17 as prior

MODEL_VERSION = "NFL RUSHING YARDS V18 • FANDUEL-ONLY TEAM GROUPING"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v17"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def select_relevant_rushers(
    projections: list[dict[str, Any]],
    players: Mapping[str, Mapping[str, Any]],
    markets: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    eligible: list[tuple[str, float, int, dict[str, Any]]] = []
    team_order: dict[str, int] = {}
    for index, raw in enumerate(projections or []):
        if not isinstance(raw, dict):
            continue
        athlete_id = prior._text(raw.get("official_athlete_id"))
        if not athlete_id:
            continue
        market = markets.get(athlete_id) or {}
        line = prior._number(market.get("line"))
        if market.get("ready") is not True or not math.isfinite(line):
            continue

        player = players.get(athlete_id) or {}
        expected = prior._number(raw.get("expected_carries"))
        usage = prior._number(player.get("carries_per_game"))
        expected_value = expected if math.isfinite(expected) else 0.0
        usage_value = usage if math.isfinite(usage) else 0.0
        workload = max(expected_value, usage_value)
        team_id = prior._text(raw.get("official_team_id") or player.get("official_team_id"), "unknown")
        if team_id not in team_order:
            team_order[team_id] = len(team_order)
        eligible.append((team_id, workload, index, dict(raw)))

    eligible.sort(key=lambda item: (team_order[item[0]], -item[1], item[2]))
    return [row for _, _, _, row in eligible]


def render_nfl_rushing_yards_hub() -> None:
    original = prior.select_relevant_rushers
    prior.select_relevant_rushers = select_relevant_rushers
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        prior.select_relevant_rushers = original


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V18 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "select_relevant_rushers",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
