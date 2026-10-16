"""NBA Spread Step 10 — deterministic final decision layer.

Consumes only the verified, frozen Step-9 pregame model. It never changes the
Step-9 projection, fair spread, cover probability, source quorum, or sportsbook
influence. Step 10 converts verified probabilities into a no-push edge, assigns
a deterministic production grade / Pick Strength, ranks playable games, and
fails closed to NO PLAY whenever required Step-9 inputs are missing or invalid.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Mapping, Sequence

MODEL_VERSION = "NBA_SPREAD_STEP10_DECISION_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = True
MAY_ACTIVATE_EDGE = True
MAY_ACTIVATE_PICK = True

MIN_PLAY_EDGE_PP = 2.0
MEDIUM_EDGE_PP = 4.0
STRONG_EDGE_PP = 7.0
ELITE_EDGE_PP = 10.0
_EPS = 1e-9


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _phase(record: Mapping[str, object]) -> str:
    text = str(record.get("phase") or "PREGAME").strip().upper()
    return text if text in {"PREGAME", "LIVE", "FINAL"} else "PREGAME"


def _format_line(value: float) -> str:
    return f"{value:+.1f}" if abs(value) > _EPS else "PK"


def pick_strength_for_edge(edge_pp: float) -> tuple[str, str]:
    edge = float(edge_pp)
    if edge >= ELITE_EDGE_PP:
        return "ELITE", "A"
    if edge >= STRONG_EDGE_PP:
        return "STRONG", "A-"
    if edge >= MEDIUM_EDGE_PP:
        return "MEDIUM", "B"
    if edge >= MIN_PLAY_EDGE_PP:
        return "LEAN", "C"
    return "NO PLAY", "WATCH"


def _no_play(record: Mapping[str, object], diagnostic: str) -> dict[str, object]:
    return {
        "version": MODEL_VERSION,
        "verification": "UNAVAILABLE",
        "diagnostic_state": diagnostic,
        "decision_state": "NO_PLAY",
        "phase": _phase(record),
        "snapshot_frozen": bool(record.get("snapshot_frozen")),
        "game_key": str(record.get("game_key") or ""),
        "selected_side": None,
        "selected_team": None,
        "selected_market_spread": None,
        "selected_cover_probability": None,
        "selected_cover_probability_no_push": None,
        "push_probability": None,
        "cover_edge_pp": 0.0,
        "spread_edge_points": 0.0,
        "pick_strength": "NO PLAY",
        "production_grade": "WATCH",
        "pick_text": "NO PLAY",
        "ranking_score": 0.0,
        "slate_rank": None,
        "top_pick": False,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def build_decision_from_step9(step9_record: Mapping[str, object]) -> dict[str, object]:
    """Convert one verified Step-9 snapshot into a deterministic decision.

    Push mass is removed before measuring side edge, so an integer market line
    cannot make both sides look artificially weak simply because a push is
    possible. The decision threshold is intentionally explicit and fixed.
    """
    record = dict(step9_record or {})
    model_raw = record.get("pregame_model")
    if str(record.get("verification") or "") != "VERIFIED" or not isinstance(model_raw, Mapping):
        return _no_play(record, "STEP9_VERIFIED_MODEL_REQUIRED")

    model = dict(model_raw)
    if str(model.get("verification") or "") != "VERIFIED" or str(model.get("cover_verification") or "") != "VERIFIED":
        return _no_play(record, "STEP9_VERIFIED_COVER_REQUIRED")
    if _number(model.get("sportsbook_projection_influence")) not in {0.0}:
        return _no_play(record, "STEP9_PROJECTION_INDEPENDENCE_REQUIRED")

    home_cover = _number(model.get("home_cover_probability"))
    away_cover = _number(model.get("away_cover_probability"))
    push = _number(model.get("push_probability"))
    market_home = _number(model.get("market_home_spread"))
    market_away = _number(model.get("market_away_spread"))
    fair_home = _number(model.get("fair_home_spread"))
    fair_away = _number(model.get("fair_away_spread"))
    if None in {home_cover, away_cover, push, market_home, market_away, fair_home, fair_away}:
        return _no_play(record, "STEP9_DECISION_INPUTS_MISSING")

    assert home_cover is not None and away_cover is not None and push is not None
    assert market_home is not None and market_away is not None
    assert fair_home is not None and fair_away is not None
    if any(value < -_EPS or value > 1.0 + _EPS for value in (home_cover, away_cover, push)):
        return _no_play(record, "STEP9_PROBABILITY_RANGE_INVALID")
    if abs((home_cover + away_cover + push) - 1.0) > 1e-6:
        return _no_play(record, "STEP9_PROBABILITY_SUM_INVALID")
    if abs(market_home + market_away) > 1e-6 or abs(fair_home + fair_away) > 1e-6:
        return _no_play(record, "STEP9_SPREAD_SYMMETRY_INVALID")

    no_push_mass = home_cover + away_cover
    if no_push_mass <= _EPS:
        return _no_play(record, "NO_PUSH_PROBABILITY_UNAVAILABLE")
    home_no_push = home_cover / no_push_mass
    away_no_push = away_cover / no_push_mass
    difference = home_no_push - away_no_push
    if abs(difference) <= _EPS:
        return _no_play(record, "NO_MEANINGFUL_EDGE")

    is_home = difference > 0.0
    selected_side = "HOME" if is_home else "AWAY"
    selected_team = str(model.get("home_tricode") if is_home else model.get("away_tricode") or "").strip().upper()
    selected_market = market_home if is_home else market_away
    selected_cover = home_cover if is_home else away_cover
    selected_no_push = home_no_push if is_home else away_no_push
    cover_edge_pp = max(0.0, (selected_no_push - 0.5) * 100.0)
    spread_edge_points = abs(fair_home - market_home)
    strength, grade = pick_strength_for_edge(cover_edge_pp)

    base = {
        "version": MODEL_VERSION,
        "verification": "VERIFIED",
        "diagnostic_state": "DECISION_READY" if strength != "NO PLAY" else "NO_MEANINGFUL_EDGE",
        "decision_state": "PLAY" if strength != "NO PLAY" else "NO_PLAY",
        "phase": _phase(record),
        "snapshot_frozen": bool(record.get("snapshot_frozen")),
        "game_key": str(record.get("game_key") or model.get("game_key") or ""),
        "selected_side": selected_side,
        "selected_team": selected_team or None,
        "selected_market_spread": float(selected_market),
        "selected_cover_probability": float(selected_cover),
        "selected_cover_probability_no_push": float(selected_no_push),
        "push_probability": float(push),
        "cover_edge_pp": float(cover_edge_pp),
        "spread_edge_points": float(spread_edge_points),
        "pick_strength": strength,
        "production_grade": grade,
        "pick_text": f"{selected_team} {_format_line(selected_market)}" if strength != "NO PLAY" and selected_team else "NO PLAY",
        "ranking_score": float((cover_edge_pp * 1000.0) + (spread_edge_points * 10.0) + selected_no_push),
        "slate_rank": None,
        "top_pick": False,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "step9_fair_home_spread": float(fair_home),
        "step9_market_home_spread": float(market_home),
    }
    return base


def decorate_and_rank_games(games: Sequence[Mapping[str, object]]) -> dict[str, object]:
    decorated: list[dict[str, object]] = []
    playable: list[tuple[int, dict[str, object]]] = []
    for index, raw in enumerate(games):
        game = deepcopy(dict(raw))
        record = game.get("step9_fair_spread")
        if isinstance(record, Mapping):
            decision = build_decision_from_step9(record)
        else:
            decision = _no_play({}, "STEP9_RECORD_REQUIRED")
            decision["game_key"] = str(game.get("game_key") or "")
        game["step10_decision"] = decision
        decorated.append(game)
        if decision.get("decision_state") == "PLAY" and decision.get("verification") == "VERIFIED":
            playable.append((index, decision))

    ordered = sorted(
        playable,
        key=lambda item: (
            -float(item[1]["cover_edge_pp"]),
            -float(item[1]["spread_edge_points"]),
            -float(item[1]["selected_cover_probability_no_push"]),
            str(item[1].get("game_key") or ""),
        ),
    )
    for rank, (index, decision) in enumerate(ordered, start=1):
        decorated[index]["step10_decision"]["slate_rank"] = rank
        decorated[index]["step10_decision"]["top_pick"] = rank == 1

    return {
        "version": MODEL_VERSION,
        "verification": "VERIFIED",
        "games": decorated,
        "play_count": len(ordered),
        "top_pick_game_key": str(ordered[0][1].get("game_key") or "") if ordered else None,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_ACTIVATE_EDGE",
    "MAY_ACTIVATE_PICK",
    "MIN_PLAY_EDGE_PP",
    "pick_strength_for_edge",
    "build_decision_from_step9",
    "decorate_and_rank_games",
]
