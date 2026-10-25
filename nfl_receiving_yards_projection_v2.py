"""NFL Receiving Yards canonical projection V2.

The formula is intentionally unchanged from the certified baseline model:
expected receptions multiplied by a weighted yards-per-reception estimate using
65% verified player efficiency and 35% verified opponent efficiency allowed.
Identity is canonical Kyre/GSIS identity and sportsbook data is excluded.
"""
from __future__ import annotations

import math
from typing import Any

MODEL_VERSION = "NFL RECEIVING YARDS CANONICAL PROJECTION V2"
SCHEMA_VERSION = "nfl_receiving_yards_projection_v2"
EFFICIENCY_WEIGHTS = {
    "player_yards_per_reception": 0.65,
    "opponent_yards_per_reception_allowed": 0.35,
}
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _withheld(reason: str, *, player: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = player or {}
    return {
        "ready": False,
        "reason": reason,
        "canonical_player_id": _text(raw.get("canonical_player_id")),
        "player_name": _text(raw.get("player_name")),
        "projection_yards": None,
        "expected_receptions": None,
        "expected_yards_per_reception": None,
        "sportsbook_influence": 0.0,
        "market_used": False,
    }


def build_player_projection(
    *,
    canonical_game_id: str,
    player: dict[str, Any],
    opponent_pass_defense: dict[str, Any],
) -> dict[str, Any]:
    game_id = _text(canonical_game_id)
    player_id = _text(player.get("canonical_player_id"))
    team_id = _text(player.get("canonical_team_id"))
    opponent_id = _text(opponent_pass_defense.get("canonical_team_id"))
    if not game_id.startswith("kyre:nfl:game:"):
        return _withheld("canonical game identity required", player=player)
    if not player_id.startswith("kyre:nfl:player:"):
        return _withheld("canonical player identity required", player=player)
    if not team_id.startswith("kyre:nfl:team:") or not opponent_id.startswith("kyre:nfl:team:") or team_id == opponent_id:
        return _withheld("canonical team/opponent identity required", player=player)

    games = _num(player.get("sample_games"))
    receptions = _num(player.get("receptions"))
    yards = _num(player.get("receiving_yards"))
    opponent_ypr = _num(opponent_pass_defense.get("yards_per_reception_allowed"))
    if games is None or games < 1 or receptions is None or receptions <= 0 or yards is None or yards <= 0:
        return _withheld("verified receiving workload required", player=player)
    if opponent_ypr is None or not 0 < opponent_ypr <= 50:
        return _withheld("verified opponent receiving efficiency required", player=player)

    expected_receptions = receptions / games
    player_ypr = yards / receptions
    if not 0 < expected_receptions <= 25 or not 0 < player_ypr <= 50:
        return _withheld("receiving workload outside safe bounds", player=player)

    expected_ypr = (
        player_ypr * EFFICIENCY_WEIGHTS["player_yards_per_reception"]
        + opponent_ypr * EFFICIENCY_WEIGHTS["opponent_yards_per_reception_allowed"]
    )
    projection = expected_receptions * expected_ypr
    if not math.isfinite(projection) or not 0 < projection <= 500:
        return _withheld("projection outside safe bounds", player=player)

    return {
        "ready": True,
        "reason": "",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "canonical_game_id": game_id,
        "canonical_player_id": player_id,
        "canonical_team_id": team_id,
        "opponent_canonical_team_id": opponent_id,
        "player_name": _text(player.get("player_name")),
        "position": _text(player.get("position")),
        "sample_games": int(games),
        "projection_yards": float(projection),
        "expected_receptions": float(expected_receptions),
        "expected_yards_per_reception": float(expected_ypr),
        "player_yards_per_reception": float(player_ypr),
        "efficiency_weights": dict(EFFICIENCY_WEIGHTS),
        "formula": "expected_receptions × expected_yards_per_reception",
        "sportsbook_influence": 0.0,
        "market_used": False,
        "probability_enabled": False,
        "ev_enabled": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


__all__ = [
    "EFFICIENCY_WEIGHTS",
    "MODEL_VERSION",
    "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_player_projection",
]
