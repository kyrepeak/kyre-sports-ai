"""Read-only Step 5.2 MLB live market context built on the Step 5.1 exact-ID join.

Only an exact official MLB game ID match may attach a FanDuel Moneyline, Run Line,
or Total snapshot to a model game. Team names, dates, start times, and fuzzy
matching are never consulted. Incomplete market rows fail closed and remain
unattached. Inputs are snapshotted; no production model object is mutated.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from sports_api.mlb_official_game_id_join_v1 import (
    MATCH_METHOD,
    MLBOfficialGameIDJoinError,
    canonical_official_game_id,
    join_model_games_to_markets,
)

DATA_TYPE = "mlb_live_market_context_v1"
SCHEMA_VERSION = 1
SOURCE = "FanDuel"
TRANSPORT = "anonymous_public_get_only"
MARKET_KEYS = ("moneyline", "run_line", "total")


def _number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def market_context_from_game(game: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a complete raw market snapshot or None.

    Values are copied exactly from the API row after numeric validation. No
    synthesized line/price, market fallback, or side inference is allowed.
    """
    try:
        game_id = canonical_official_game_id(game.get("official_game_id"))
    except MLBOfficialGameIDJoinError:
        return None

    markets = _mapping(game.get("markets"))
    if markets is None:
        return None
    moneyline = _mapping(markets.get("moneyline"))
    run_line = _mapping(markets.get("run_line"))
    total = _mapping(markets.get("total"))
    if moneyline is None or run_line is None or total is None:
        return None

    required = (
        moneyline.get("away_odds"),
        moneyline.get("home_odds"),
        run_line.get("away_line"),
        run_line.get("away_odds"),
        run_line.get("home_line"),
        run_line.get("home_odds"),
        total.get("line"),
        total.get("over_odds"),
        total.get("under_odds"),
    )
    if not all(_number(value) for value in required):
        return None

    sportsbook = str(game.get("sportsbook") or game.get("source") or SOURCE).strip()
    if sportsbook != SOURCE:
        return None

    return {
        "official_game_id": game_id,
        "sportsbook": SOURCE,
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "scheduled_start_utc": game.get("scheduled_start_utc"),
        "source_event_id": game.get("source_event_id"),
        "moneyline": {
            "away_odds": moneyline.get("away_odds"),
            "home_odds": moneyline.get("home_odds"),
        },
        "run_line": {
            "away_line": run_line.get("away_line"),
            "away_odds": run_line.get("away_odds"),
            "home_line": run_line.get("home_line"),
            "home_odds": run_line.get("home_odds"),
        },
        "total": {
            "line": total.get("line"),
            "over_odds": total.get("over_odds"),
            "under_odds": total.get("under_odds"),
        },
    }


def attach_live_market_context(
    model_games: Iterable[Any],
    market_games: Iterable[Any],
) -> dict[str, Any]:
    """Attach complete FanDuel market context by exact official MLB ID only."""
    joined = join_model_games_to_markets(model_games, market_games)
    contexts: dict[int, dict[str, Any]] = {}
    unusable_ids: list[int] = []

    for matched in joined["matched_games"]:
        game_id = canonical_official_game_id(matched["official_game_id"])
        context = market_context_from_game(matched["market"])
        if context is None:
            unusable_ids.append(game_id)
            continue
        contexts[game_id] = context

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "transport": TRANSPORT,
        "match_method": joined["match_method"],
        "fallback_matching_used": joined["fallback_matching_used"],
        "model_game_id_field": joined["model_game_id_field"],
        "market_game_id_field": joined["market_game_id_field"],
        "model_game_count": joined["model_game_count"],
        "market_game_count": joined["market_game_count"],
        "exact_id_matched_count": joined["matched_count"],
        "attached_count": len(contexts),
        "contexts_by_game_id": contexts,
        "unusable_matched_game_ids": sorted(unusable_ids),
        "unmatched_model_game_ids": list(joined["unmatched_model_game_ids"]),
        "unmatched_market_game_ids": list(joined["unmatched_market_game_ids"]),
        "invalid_model_identities": list(joined["invalid_model_identities"]),
        "invalid_market_identities": list(joined["invalid_market_identities"]),
    }


__all__ = [
    "DATA_TYPE",
    "MARKET_KEYS",
    "SCHEMA_VERSION",
    "SOURCE",
    "TRANSPORT",
    "attach_live_market_context",
    "market_context_from_game",
]
