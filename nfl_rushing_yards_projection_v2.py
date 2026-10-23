"""Market-blind NFL Rushing Yards projection model for the Kyre Sports API path."""
from __future__ import annotations

import math
from typing import Any

MODEL_VERSION = "NFL RUSHING YARDS PROJECTION V2"
SCHEMA_VERSION = "nfl_rushing_yards_projection_v2"
PLAYER_EFFICIENCY_WEIGHT = 0.65
OPPONENT_EFFICIENCY_WEIGHT = 0.35
SPORTSBOOK_INFLUENCE = 0.0


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def build_projection(*, player: dict[str, Any], opponent: dict[str, Any]) -> dict[str, Any]:
    carries = _num(player.get("carries_per_game"))
    player_ypc = _num(player.get("yards_per_carry"))
    opponent_ypc = _num(opponent.get("yards_per_carry_allowed"))
    sample_games = int(_num(player.get("sample_games")) or 0)
    inputs = {
        "carries_per_game": carries,
        "player_yards_per_carry": player_ypc,
        "opponent_yards_per_carry_allowed": opponent_ypc,
        "sample_games": sample_games,
    }
    if carries is None or not 0 < carries <= 50:
        return {"ready": False, "reason": "Verified carry workload is required", "projection_yards": None, "inputs": inputs, "sportsbook_influence": 0.0}
    if player_ypc is None or not 0 < player_ypc <= 20:
        return {"ready": False, "reason": "Verified player rushing efficiency is required", "projection_yards": None, "inputs": inputs, "sportsbook_influence": 0.0}
    if opponent_ypc is None or not 0 < opponent_ypc <= 20:
        return {"ready": False, "reason": "Verified opponent rushing efficiency allowed is required", "projection_yards": None, "inputs": inputs, "sportsbook_influence": 0.0}
    if sample_games < 1:
        return {"ready": False, "reason": "Verified workload sample is required", "projection_yards": None, "inputs": inputs, "sportsbook_influence": 0.0}

    expected_ypc = player_ypc * PLAYER_EFFICIENCY_WEIGHT + opponent_ypc * OPPONENT_EFFICIENCY_WEIGHT
    projection = carries * expected_ypc
    if not math.isfinite(projection) or not 0 < projection <= 500:
        return {"ready": False, "reason": "Projection failed sanity bounds", "projection_yards": None, "inputs": inputs, "sportsbook_influence": 0.0}
    return {
        "ready": True,
        "reason": "",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "projection_yards": round(projection, 3),
        "expected_carries": round(carries, 3),
        "expected_yards_per_carry": round(expected_ypc, 3),
        "inputs": inputs,
        "formula": "carries_per_game × (0.65 player YPC + 0.35 opponent YPC allowed)",
        "sportsbook_influence": SPORTSBOOK_INFLUENCE,
        "derived_or_reported": "DERIVED",
    }


__all__ = ["MODEL_VERSION", "SCHEMA_VERSION", "SPORTSBOOK_INFLUENCE", "build_projection"]
