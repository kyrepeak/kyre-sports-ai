"""Step 5.3 read-only MLB market probability layer.

Derives raw implied probability, two-way sportsbook hold, and proportional no-vig
fair probability from the exact FanDuel Moneyline / Run Line / Total prices already
attached by Step 5.2. This module never changes model probabilities, projections,
Pick Strength, simulations, ranking, selection, persistence, or wagering state.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping

from sports_api.mlb_official_game_id_join_v1 import canonical_official_game_id

DATA_TYPE = "mlb_market_probability_context_v1"
SCHEMA_VERSION = 1
SOURCE = "FanDuel"
METHOD = "proportional_two_way_no_vig"


class MLBMarketProbabilityError(ValueError):
    """Raised when a Step 5.3 probability cannot be derived safely."""


def _american_odds(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLBMarketProbabilityError("American odds must be numeric")
    odds = float(value)
    if not math.isfinite(odds):
        raise MLBMarketProbabilityError("American odds must be finite")
    if abs(odds) < 100.0:
        raise MLBMarketProbabilityError("American odds absolute value must be at least 100")
    return odds


def american_odds_to_implied_probability(odds: Any) -> float:
    """Convert standard American odds to raw implied probability in [0, 1]."""
    value = _american_odds(odds)
    if value > 0:
        return 100.0 / (value + 100.0)
    return (-value) / ((-value) + 100.0)


def two_way_no_vig(left_odds: Any, right_odds: Any) -> dict[str, float]:
    """Return raw implied probabilities, hold, and proportional no-vig probabilities."""
    left_raw = american_odds_to_implied_probability(left_odds)
    right_raw = american_odds_to_implied_probability(right_odds)
    overround = left_raw + right_raw
    if not math.isfinite(overround) or overround <= 0.0:
        raise MLBMarketProbabilityError("two-way implied probability sum is invalid")
    return {
        "left_implied_probability": left_raw,
        "right_implied_probability": right_raw,
        "overround_probability": overround,
        "hold_probability": overround - 1.0,
        "left_no_vig_probability": left_raw / overround,
        "right_no_vig_probability": right_raw / overround,
    }


def _pair(left_odds: Any, right_odds: Any, *, left_label: str, right_label: str) -> dict[str, Any]:
    calc = two_way_no_vig(left_odds, right_odds)
    return {
        "method": METHOD,
        "hold_probability": calc["hold_probability"],
        left_label: {
            "odds": deepcopy(left_odds),
            "implied_probability": calc["left_implied_probability"],
            "no_vig_probability": calc["left_no_vig_probability"],
        },
        right_label: {
            "odds": deepcopy(right_odds),
            "implied_probability": calc["right_implied_probability"],
            "no_vig_probability": calc["right_no_vig_probability"],
        },
    }


def market_probability_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Derive Step 5.3 probabilities from one complete Step 5.2 exact-ID context."""
    if not isinstance(context, Mapping):
        raise MLBMarketProbabilityError("market context must be a mapping")
    game_id = canonical_official_game_id(context.get("official_game_id"))
    if str(context.get("sportsbook") or context.get("source") or SOURCE) != SOURCE:
        raise MLBMarketProbabilityError("Step 5.3 accepts FanDuel context only")
    if context.get("fallback_matching_used") is not False:
        raise MLBMarketProbabilityError("Step 5.3 requires exact-ID context with no fallback")

    moneyline = context.get("moneyline")
    run_line = context.get("run_line")
    total = context.get("total")
    if not all(isinstance(v, Mapping) for v in (moneyline, run_line, total)):
        raise MLBMarketProbabilityError("complete ML/RL/Total context is required")

    ml = _pair(
        moneyline.get("away_odds"),
        moneyline.get("home_odds"),
        left_label="away",
        right_label="home",
    )
    rl = _pair(
        run_line.get("away_odds"),
        run_line.get("home_odds"),
        left_label="away",
        right_label="home",
    )
    rl["away"]["line"] = deepcopy(run_line.get("away_line"))
    rl["home"]["line"] = deepcopy(run_line.get("home_line"))

    tot = _pair(
        total.get("over_odds"),
        total.get("under_odds"),
        left_label="over",
        right_label="under",
    )
    tot["line"] = deepcopy(total.get("line"))

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "official_game_id": game_id,
        "match_method": context.get("match_method") or "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "probability_method": METHOD,
        "moneyline": ml,
        "run_line": rl,
        "total": tot,
    }


def derive_market_probability_contexts(step5_2_state: Mapping[str, Any]) -> dict[str, Any]:
    """Derive Step 5.3 contexts for every usable exact-ID Step 5.2 market context."""
    if not isinstance(step5_2_state, Mapping):
        raise MLBMarketProbabilityError("Step 5.2 state must be a mapping")
    contexts = step5_2_state.get("contexts_by_game_id")
    if not isinstance(contexts, Mapping):
        raise MLBMarketProbabilityError("Step 5.2 contexts_by_game_id is required")

    out: dict[int, dict[str, Any]] = {}
    unusable: list[int] = []
    for raw_id, raw_context in contexts.items():
        try:
            game_id = canonical_official_game_id(raw_id)
            derived = market_probability_context(raw_context)
            if derived["official_game_id"] != game_id:
                raise MLBMarketProbabilityError("context key and official_game_id differ")
        except Exception:
            try:
                unusable.append(canonical_official_game_id(raw_id))
            except Exception:
                continue
            continue
        out[game_id] = derived

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "probability_method": METHOD,
        "match_method": step5_2_state.get("match_method") or "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "input_context_count": len(contexts),
        "derived_context_count": len(out),
        "contexts_by_game_id": out,
        "unusable_game_ids": sorted(unusable),
    }


__all__ = [
    "DATA_TYPE",
    "METHOD",
    "MLBMarketProbabilityError",
    "SCHEMA_VERSION",
    "SOURCE",
    "american_odds_to_implied_probability",
    "derive_market_probability_contexts",
    "market_probability_context",
    "two_way_no_vig",
]
