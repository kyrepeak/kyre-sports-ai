"""Step 5.4 read-only MLB model-vs-market edge layer.

Consumes the production model probability already present on a Daily Picks candidate
and the Step 5.3 exact-ID FanDuel no-vig market probability. It derives comparison
metrics only: model-minus-market edge, model fair American odds, and expected value
at the exact attached FanDuel price. It never rewrites model probability, projection,
Pick Strength, simulation results, ranking, selection, persistence, or wagering state.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Mapping

from sports_api.mlb_official_game_id_join_v1 import canonical_official_game_id

DATA_TYPE = "mlb_model_market_edge_context_v1"
SCHEMA_VERSION = 1
SOURCE = "FanDuel"
SUPPORTED_MARKETS = ("Moneyline", "Run Line", "Total")


class MLBModelMarketEdgeError(ValueError):
    """Raised when a Step 5.4 edge cannot be derived safely."""


def _probability(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLBModelMarketEdgeError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out) or not (0.0 < out < 1.0):
        raise MLBModelMarketEdgeError(f"{field} must be strictly between 0 and 1")
    return out


def _american_odds(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLBModelMarketEdgeError("American odds must be numeric")
    out = float(value)
    if not math.isfinite(out) or abs(out) < 100.0:
        raise MLBModelMarketEdgeError("American odds absolute value must be at least 100")
    return out


def probability_to_american_odds(probability: Any) -> float:
    """Convert a fair win probability to American odds."""
    p = _probability(probability, field="probability")
    if p >= 0.5:
        return -(100.0 * p / (1.0 - p))
    return 100.0 * (1.0 - p) / p


def american_odds_profit_per_unit(odds: Any) -> float:
    """Profit on a 1-unit stake if the bet wins at American odds."""
    value = _american_odds(odds)
    if value > 0:
        return value / 100.0
    return 100.0 / (-value)


def expected_value_per_unit(model_probability: Any, odds: Any) -> float:
    """Expected profit per 1-unit stake using the production model probability."""
    p = _probability(model_probability, field="model_probability")
    profit = american_odds_profit_per_unit(odds)
    return p * profit - (1.0 - p)


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _candidate_text(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        _norm(candidate.get(field))
        for field in ("side", "name", "team")
        if _norm(candidate.get(field))
    )


def resolve_candidate_market_side(
    candidate: Mapping[str, Any],
    *,
    away_team: Any = None,
    home_team: Any = None,
) -> str:
    """Resolve a candidate to away/home/over/under without fuzzy matching.

    Game identity has already been established by exact MLB game ID upstream. For
    team markets this function allows only exact normalized team-name equality or
    explicit away/home tokens. Ambiguous candidates fail closed.
    """
    if not isinstance(candidate, Mapping):
        raise MLBModelMarketEdgeError("candidate must be a mapping")

    market = str(candidate.get("market") or "").strip()
    if market not in SUPPORTED_MARKETS:
        raise MLBModelMarketEdgeError("candidate market is not supported by Step 5.4")

    texts = _candidate_text(candidate)
    if market == "Total":
        has_over = any(text == "over" or text.startswith("over") for text in texts)
        has_under = any(text == "under" or text.startswith("under") for text in texts)
        if has_over == has_under:
            raise MLBModelMarketEdgeError("Total side is ambiguous")
        return "over" if has_over else "under"

    away = _norm(away_team)
    home = _norm(home_team)
    if not away or not home or away == home:
        raise MLBModelMarketEdgeError("distinct away/home team names are required")

    away_match = any(text in {"away", away} for text in texts)
    home_match = any(text in {"home", home} for text in texts)

    if away_match == home_match:
        raise MLBModelMarketEdgeError("team-market side is ambiguous")
    return "away" if away_match else "home"


def model_market_edge(
    candidate: Mapping[str, Any],
    market_probability_context: Mapping[str, Any],
    *,
    away_team: Any = None,
    home_team: Any = None,
) -> dict[str, Any]:
    """Derive Step 5.4 comparison metrics for one candidate, or fail closed."""
    if not isinstance(candidate, Mapping):
        raise MLBModelMarketEdgeError("candidate must be a mapping")
    if not isinstance(market_probability_context, Mapping):
        raise MLBModelMarketEdgeError("market probability context must be a mapping")

    game_id = canonical_official_game_id(candidate.get("game_pk"))
    context_game_id = canonical_official_game_id(market_probability_context.get("official_game_id"))
    if game_id != context_game_id:
        raise MLBModelMarketEdgeError("candidate and market context game IDs differ")
    if market_probability_context.get("fallback_matching_used") is not False:
        raise MLBModelMarketEdgeError("Step 5.4 requires exact-ID context with no fallback")
    if str(market_probability_context.get("source") or SOURCE) != SOURCE:
        raise MLBModelMarketEdgeError("Step 5.4 accepts FanDuel context only")

    market = str(candidate.get("market") or "").strip()
    side = resolve_candidate_market_side(candidate, away_team=away_team, home_team=home_team)
    model_p = _probability(candidate.get("probability"), field="model_probability")

    if market == "Moneyline":
        block = market_probability_context.get("moneyline")
    elif market == "Run Line":
        block = market_probability_context.get("run_line")
    elif market == "Total":
        block = market_probability_context.get("total")
    else:
        raise MLBModelMarketEdgeError("candidate market is not supported by Step 5.4")

    if not isinstance(block, Mapping):
        raise MLBModelMarketEdgeError("market probability block is missing")
    side_block = block.get(side)
    if not isinstance(side_block, Mapping):
        raise MLBModelMarketEdgeError("selected market side is missing")

    market_p = _probability(side_block.get("no_vig_probability"), field="market_no_vig_probability")
    odds = _american_odds(side_block.get("odds"))
    edge = model_p - market_p
    ev = expected_value_per_unit(model_p, odds)

    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "official_game_id": game_id,
        "match_method": market_probability_context.get("match_method") or "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "market": market,
        "selected_side": side,
        "model_probability": model_p,
        "market_no_vig_probability": market_p,
        "edge_probability": edge,
        "edge_percentage_points": edge * 100.0,
        "market_odds": odds,
        "model_fair_american_odds": probability_to_american_odds(model_p),
        "expected_value_per_unit": ev,
        "expected_value_percent": ev * 100.0,
        "comparison_only": True,
    }

    if market == "Run Line":
        result["market_line"] = side_block.get("line")
    elif market == "Total":
        result["market_line"] = block.get("line")
    else:
        result["market_line"] = None
    return result


__all__ = [
    "DATA_TYPE",
    "MLBModelMarketEdgeError",
    "SCHEMA_VERSION",
    "SOURCE",
    "SUPPORTED_MARKETS",
    "american_odds_profit_per_unit",
    "expected_value_per_unit",
    "model_market_edge",
    "probability_to_american_odds",
    "resolve_candidate_market_side",
]
