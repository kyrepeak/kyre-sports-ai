"""CFB Player Props Page 2 V1 — recent production and read-only defense context."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import cfb_over_under_matchup_engine_v1 as matchup_engine
import cfb_player_props_history_v1 as history_owner
import cfb_player_props_model_v1 as frozen_model
import cfb_team_data_v2 as team_data
from cfb_player_props_market_v1 import PropObservation
from cfb_player_props_page2_roster_v1 import Page2Player

_DEFENSE_DIMENSION = {
    "passing_yards": "passing",
    "passing_touchdowns": "passing",
    "receiving_yards": "passing",
    "receiving_receptions": "passing",
    "rushing_yards": "rushing",
    "touchdowns": "red_zone",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_recent_production(
    player: Page2Player, market_key: str, *, season: int
) -> dict[str, Any]:
    try:
        history = history_owner.load_verified_player_history(
            player.identity, market_key, season=int(season)
        )
    except Exception:
        history = []
    projection = frozen_model.build_prop_projection(history, market_key)
    values = tuple(projection.get("values") or ())
    return {
        "market_key": market_key,
        "sample_count": int(projection.get("sample_count") or 0),
        "values": values,
        "last3": tuple(values[:3]),
        "season_average": (sum(values) / len(values)) if values else None,
        "model_ready": bool(projection.get("model_ready")),
        "projection": projection.get("projection"),
        "uncertainty": projection.get("uncertainty"),
        "provenance": projection.get("provenance") or (),
        "sportsbook_projection_influence": frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE,
        "history": tuple(history[: frozen_model.MAX_SAMPLE]),
    }


def build_page2_signal(
    player: Page2Player,
    market_key: str,
    history: Sequence[Mapping[str, Any]],
    observations: Sequence[PropObservation],
) -> dict[str, Any]:
    # This is deliberately a pure wrapper. Page 2 does not own a second model.
    return frozen_model.build_page1_signal(
        player.identity, market_key, history, observations
    )


def _game(context: Mapping[str, Any]) -> dict[str, Any]:
    raw = context.get("game")
    game = dict(raw) if isinstance(raw, Mapping) else {}
    game.setdefault("official_game_id", _text(context.get("official_game_id")))
    game.setdefault("game_date", _text(context.get("game_date") or context.get("slate_date")))
    for side in ("away", "home"):
        game.setdefault(f"{side}_team_id", _text(context.get(f"{side}_team_id")))
        game.setdefault(f"{side}_team", _text(context.get(f"{side}_team")))
    return game


def load_game_matchup_context(context: Mapping[str, Any]) -> dict[str, Any]:
    game = _game(context)
    game_day = _text(context.get("game_date") or context.get("slate_date") or game.get("game_date"))
    try:
        profiles, diagnostics = team_data.load_matchup_team_data(game, game_day)
    except Exception:
        profiles, diagnostics = {"away": {}, "home": {}}, {}
    away = profiles.get("away") if isinstance(profiles, Mapping) else {}
    home = profiles.get("home") if isinstance(profiles, Mapping) else {}
    try:
        engine = matchup_engine.build_matchup_engine(game, away or {}, home or {})
    except Exception:
        engine = {"model_ready": False, "away_offense": {}, "home_offense": {}}
    return {
        "context": dict(context),
        "game": game,
        "profiles": profiles,
        "diagnostics": diagnostics,
        "engine": engine,
    }


def _check(dimension: str = "") -> dict[str, Any]:
    return {
        "label": "CHECK",
        "message": "Defense data unavailable",
        "dimension": dimension,
        "defense_rank": None,
        "defense_value": "",
        "edge": None,
        "source": "NCAA matchup evidence",
        "model_influence": 0.0,
    }


def grade_player_matchup(
    player: Page2Player,
    market_key: str,
    matchup_context: Mapping[str, Any],
) -> dict[str, Any]:
    dimension = _DEFENSE_DIMENSION.get(market_key, "")
    if not dimension:
        return _check()
    context = matchup_context.get("context")
    context = context if isinstance(context, Mapping) else {}
    if player.official_team_id == _text(context.get("away_team_id")):
        side_key = "away_offense"
    elif player.official_team_id == _text(context.get("home_team_id")):
        side_key = "home_offense"
    else:
        return _check(dimension)

    engine = matchup_context.get("engine")
    engine = engine if isinstance(engine, Mapping) else {}
    side = engine.get(side_key)
    side = side if isinstance(side, Mapping) else {}
    dimensions = side.get("dimensions")
    dimensions = dimensions if isinstance(dimensions, Mapping) else {}
    row = dimensions.get(dimension)
    row = row if isinstance(row, Mapping) else {}
    if row.get("ready") is not True:
        return _check(dimension)
    try:
        edge = float(row.get("edge"))
    except (TypeError, ValueError):
        return _check(dimension)

    if edge >= 0.12:
        label = "FAVORABLE"
    elif edge <= -0.12:
        label = "TOUGH"
    else:
        label = "NEUTRAL"
    rank = row.get("defense_rank")
    rank_text = f"#{rank}" if rank not in (None, "") else "rank unavailable"
    return {
        "label": label,
        "message": f"Opponent {dimension.replace('_', ' ')} defense {rank_text}",
        "dimension": dimension,
        "defense_rank": rank,
        "defense_value": _text(row.get("defense_value")),
        "edge": edge,
        "source": "NCAA matchup evidence",
        "model_influence": 0.0,
    }


__all__ = [
    "build_page2_signal", "build_recent_production", "grade_player_matchup",
    "load_game_matchup_context",
]
