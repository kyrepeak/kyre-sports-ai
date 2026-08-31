"""Step 5.6 read-only MLB market movement and snapshot-freshness layer.

Consumes the certified Step 5.5 price-discipline context plus the live FanDuel
collection timestamp. It records a compact exact-identity market observation and,
when an older observation exists for the same official MLB game/market/side,
compares the two without altering any production model output.

For identical market lines it reports raw break-even probability movement, no-vig
probability movement, American-odds movement, and the EV change caused by price
movement alone while holding the *current* production model probability fixed.
If a Run Line or Total line changes, price comparison is intentionally suppressed
rather than pretending prices at different lines are directly comparable.

No fuzzy matching, model mutation, ranking/selection impact, persistence, or wagering.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping

from sports_api.mlb_model_market_edge_v1 import expected_value_per_unit
from sports_api.mlb_official_game_id_join_v1 import canonical_official_game_id
from sports_api.mlb_price_discipline_v1 import DATA_TYPE as STEP5_5_DATA_TYPE

OBSERVATION_DATA_TYPE = "mlb_market_observation_v1"
DATA_TYPE = "mlb_market_movement_context_v1"
SCHEMA_VERSION = 1
SOURCE = "FanDuel"
SUPPORTED_MARKETS = ("Moneyline", "Run Line", "Total")
TOLERANCE = 1e-12
CLOCK_SKEW_TOLERANCE_SECONDS = 5.0


class MLBMarketMovementError(ValueError):
    """Raised when Step 5.6 cannot prove a movement comparison safely."""


def _finite(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLBMarketMovementError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise MLBMarketMovementError(f"{field} must be finite")
    return out


def _probability(value: Any, *, field: str) -> float:
    out = _finite(value, field=field)
    if not (0.0 < out < 1.0):
        raise MLBMarketMovementError(f"{field} must be strictly between 0 and 1")
    return out


def parse_utc_timestamp(value: Any, *, field: str = "collected_at_utc") -> datetime:
    """Parse an offset-aware ISO timestamp and normalize it to UTC."""
    if not isinstance(value, str) or not value.strip():
        raise MLBMarketMovementError(f"{field} must be a non-empty ISO timestamp")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception as exc:
        raise MLBMarketMovementError(f"{field} is not a valid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MLBMarketMovementError(f"{field} must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def canonical_utc_timestamp(value: Any, *, field: str = "collected_at_utc") -> str:
    return parse_utc_timestamp(value, field=field).isoformat()


def observation_identity(observation: Mapping[str, Any]) -> tuple[int, str, str]:
    """Exact comparison identity; the betting line is compared, not used as fallback identity."""
    if not isinstance(observation, Mapping):
        raise MLBMarketMovementError("observation must be a mapping")
    try:
        game_id = canonical_official_game_id(observation.get("official_game_id"))
    except Exception as exc:
        raise MLBMarketMovementError("official_game_id is invalid") from exc
    market = str(observation.get("market") or "").strip()
    side = str(observation.get("selected_side") or "").strip().lower()
    if market not in SUPPORTED_MARKETS:
        raise MLBMarketMovementError("market is unsupported")
    allowed_sides = {"Moneyline": {"away", "home"}, "Run Line": {"away", "home"}, "Total": {"over", "under"}}
    if side not in allowed_sides[market]:
        raise MLBMarketMovementError("selected_side is unsupported for market")
    return game_id, market, side


def observation_identity_key(observation: Mapping[str, Any]) -> str:
    game_id, market, side = observation_identity(observation)
    return f"{game_id}|{market}|{side}"


def _line(value: Any) -> float | None:
    if value is None:
        return None
    return _finite(value, field="market_line")


def _validate_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(observation, Mapping):
        raise MLBMarketMovementError("observation must be a mapping")
    if observation.get("data_type") != OBSERVATION_DATA_TYPE:
        raise MLBMarketMovementError("unexpected observation data_type")
    if observation.get("schema_version") != SCHEMA_VERSION:
        raise MLBMarketMovementError("unsupported observation schema_version")
    if str(observation.get("source") or "") != SOURCE:
        raise MLBMarketMovementError("Step 5.6 accepts FanDuel observations only")
    if observation.get("fallback_matching_used") is not False:
        raise MLBMarketMovementError("Step 5.6 requires exact-ID observations with no fallback")
    if observation.get("comparison_only") is not True:
        raise MLBMarketMovementError("comparison-only invariant is missing")
    if observation.get("durable_persistence") is not False:
        raise MLBMarketMovementError("market observations must be ephemeral, not durable")

    game_id, market, side = observation_identity(observation)
    odds = _finite(observation.get("market_odds"), field="market_odds")
    if abs(odds) < 100.0:
        raise MLBMarketMovementError("American odds absolute value must be at least 100")
    raw = _probability(observation.get("market_raw_break_even_probability"), field="market_raw_break_even_probability")
    no_vig = _probability(observation.get("market_no_vig_probability"), field="market_no_vig_probability")
    model_p = _probability(observation.get("model_probability"), field="model_probability")
    ev = _finite(observation.get("expected_value_per_unit"), field="expected_value_per_unit")
    zero_ev = _finite(observation.get("zero_ev_american_price_limit"), field="zero_ev_american_price_limit")
    if abs(zero_ev) < 100.0:
        raise MLBMarketMovementError("zero-EV American price limit is invalid")
    collected = canonical_utc_timestamp(observation.get("collected_at_utc"))

    expected_ev = expected_value_per_unit(model_p, odds)
    if not math.isclose(expected_ev, ev, rel_tol=0.0, abs_tol=1e-12):
        raise MLBMarketMovementError("observation EV does not reconcile with its model probability and odds")

    return {
        "data_type": OBSERVATION_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "official_game_id": game_id,
        "match_method": observation.get("match_method") or "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "market": market,
        "selected_side": side,
        "market_line": _line(observation.get("market_line")),
        "market_odds": odds,
        "market_raw_break_even_probability": raw,
        "market_no_vig_probability": no_vig,
        "model_probability": model_p,
        "expected_value_per_unit": ev,
        "zero_ev_american_price_limit": zero_ev,
        "current_price_status": str(observation.get("current_price_status") or ""),
        "collected_at_utc": collected,
        "comparison_only": True,
        "durable_persistence": False,
    }


def build_market_observation(
    step5_5_context: Mapping[str, Any],
    *,
    collected_at_utc: Any,
) -> dict[str, Any]:
    """Freeze the market facts needed for one ephemeral Step 5.6 observation."""
    if not isinstance(step5_5_context, Mapping):
        raise MLBMarketMovementError("Step 5.5 context must be a mapping")
    if step5_5_context.get("data_type") != STEP5_5_DATA_TYPE:
        raise MLBMarketMovementError("Step 5.6 requires the certified Step 5.5 data type")
    if step5_5_context.get("schema_version") != 1:
        raise MLBMarketMovementError("Step 5.5 schema version is unsupported")
    if str(step5_5_context.get("source") or "") != SOURCE:
        raise MLBMarketMovementError("Step 5.6 accepts FanDuel context only")
    if step5_5_context.get("fallback_matching_used") is not False:
        raise MLBMarketMovementError("Step 5.6 requires exact-ID context with no fallback")
    if step5_5_context.get("comparison_only") is not True:
        raise MLBMarketMovementError("Step 5.5 comparison-only invariant is missing")
    for field in ("selection_impact", "ranking_impact", "wagering_impact"):
        if step5_5_context.get(field) is not False:
            raise MLBMarketMovementError(f"Step 5.5 {field} invariant is missing")

    observation = {
        "data_type": OBSERVATION_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "official_game_id": step5_5_context.get("official_game_id"),
        "match_method": step5_5_context.get("match_method") or "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "market": step5_5_context.get("market"),
        "selected_side": step5_5_context.get("selected_side"),
        "market_line": step5_5_context.get("market_line"),
        "market_odds": step5_5_context.get("market_odds"),
        "market_raw_break_even_probability": step5_5_context.get("market_raw_break_even_probability"),
        "market_no_vig_probability": step5_5_context.get("market_no_vig_probability"),
        "model_probability": step5_5_context.get("model_probability"),
        "expected_value_per_unit": step5_5_context.get("expected_value_per_unit"),
        "zero_ev_american_price_limit": step5_5_context.get("zero_ev_american_price_limit"),
        "current_price_status": step5_5_context.get("current_price_status"),
        "collected_at_utc": canonical_utc_timestamp(collected_at_utc),
        "comparison_only": True,
        "durable_persistence": False,
    }
    return _validate_observation(observation)


def _snapshot_age_seconds(collected_at_utc: str, as_of_utc: Any | None) -> float | None:
    if as_of_utc is None:
        return None
    observed = parse_utc_timestamp(collected_at_utc)
    as_of = parse_utc_timestamp(as_of_utc, field="as_of_utc")
    age = (as_of - observed).total_seconds()
    if age < -CLOCK_SKEW_TOLERANCE_SECONDS:
        raise MLBMarketMovementError("as_of_utc is earlier than the current observation")
    return max(0.0, age)


def _same_line(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=0.0, abs_tol=1e-12)


def _same_market_snapshot(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    numeric_fields = (
        "market_odds",
        "market_raw_break_even_probability",
        "market_no_vig_probability",
        "market_line",
    )
    for field in numeric_fields:
        av, bv = a.get(field), b.get(field)
        if av is None or bv is None:
            if av is not None or bv is not None:
                return False
        elif not math.isclose(float(av), float(bv), rel_tol=0.0, abs_tol=1e-12):
            return False
    return True


def compare_market_observations(
    current_observation: Mapping[str, Any],
    previous_observation: Mapping[str, Any] | None = None,
    *,
    as_of_utc: Any | None = None,
) -> dict[str, Any]:
    """Compare two exact-identity FanDuel observations without inventing movement."""
    current = _validate_observation(current_observation)
    current_identity = observation_identity(current)
    age = _snapshot_age_seconds(current["collected_at_utc"], as_of_utc)

    base: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "official_game_id": current["official_game_id"],
        "match_method": current["match_method"],
        "fallback_matching_used": False,
        "market": current["market"],
        "selected_side": current["selected_side"],
        "current_market_line": current["market_line"],
        "current_market_odds": current["market_odds"],
        "current_raw_break_even_probability": current["market_raw_break_even_probability"],
        "current_no_vig_probability": current["market_no_vig_probability"],
        "current_model_probability": current["model_probability"],
        "current_expected_value_per_unit": current["expected_value_per_unit"],
        "current_zero_ev_american_price_limit": current["zero_ev_american_price_limit"],
        "current_price_status": current["current_price_status"],
        "current_collected_at_utc": current["collected_at_utc"],
        "snapshot_age_seconds": age,
        "movement_available": False,
        "price_comparison_comparable": False,
        "movement_status": "NO_PRIOR_OBSERVATION",
        "comparison_only": True,
        "ephemeral_session_history": True,
        "durable_persistence": False,
        "selection_impact": False,
        "ranking_impact": False,
        "wagering_impact": False,
    }

    if previous_observation is None:
        return base

    previous = _validate_observation(previous_observation)
    if observation_identity(previous) != current_identity:
        raise MLBMarketMovementError("current and previous observation identities differ")

    current_dt = parse_utc_timestamp(current["collected_at_utc"])
    previous_dt = parse_utc_timestamp(previous["collected_at_utc"])
    seconds_between = (current_dt - previous_dt).total_seconds()
    if seconds_between < 0:
        raise MLBMarketMovementError("previous observation is newer than current observation")
    if seconds_between == 0:
        if not _same_market_snapshot(current, previous):
            raise MLBMarketMovementError("same-timestamp observations contain conflicting market data")
        base.update({
            "movement_status": "NO_NEW_OBSERVATION",
            "previous_collected_at_utc": previous["collected_at_utc"],
            "previous_market_line": previous["market_line"],
            "previous_market_odds": previous["market_odds"],
            "seconds_since_previous_observation": 0.0,
        })
        return base

    line_same = _same_line(current["market_line"], previous["market_line"])
    base.update({
        "movement_available": True,
        "previous_collected_at_utc": previous["collected_at_utc"],
        "previous_market_line": previous["market_line"],
        "previous_market_odds": previous["market_odds"],
        "previous_raw_break_even_probability": previous["market_raw_break_even_probability"],
        "previous_no_vig_probability": previous["market_no_vig_probability"],
        "seconds_since_previous_observation": seconds_between,
        "line_changed": not line_same,
    })

    if not line_same:
        line_delta = None
        if current["market_line"] is not None and previous["market_line"] is not None:
            line_delta = current["market_line"] - previous["market_line"]
        base.update({
            "movement_status": "LINE_CHANGED",
            "line_delta": line_delta,
            "price_comparison_comparable": False,
            "raw_break_even_probability_delta": None,
            "no_vig_probability_delta": None,
            "american_odds_delta": None,
            "price_only_previous_ev_using_current_model": None,
            "price_only_ev_delta": None,
            "price_direction": "NOT_COMPARABLE_DIFFERENT_LINE",
        })
        return base

    raw_delta = current["market_raw_break_even_probability"] - previous["market_raw_break_even_probability"]
    no_vig_delta = current["market_no_vig_probability"] - previous["market_no_vig_probability"]
    odds_delta = current["market_odds"] - previous["market_odds"]
    previous_ev_using_current_model = expected_value_per_unit(
        current["model_probability"], previous["market_odds"]
    )
    current_ev_using_current_model = expected_value_per_unit(
        current["model_probability"], current["market_odds"]
    )
    if not math.isclose(
        current_ev_using_current_model,
        current["expected_value_per_unit"],
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise MLBMarketMovementError("current observation EV failed current-model reconciliation")
    price_only_ev_delta = current_ev_using_current_model - previous_ev_using_current_model

    if raw_delta > TOLERANCE:
        price_direction = "MORE_EXPENSIVE"
    elif raw_delta < -TOLERANCE:
        price_direction = "BETTER_PRICE"
    else:
        price_direction = "UNCHANGED"

    if no_vig_delta > TOLERANCE:
        no_vig_direction = "MARKET_MORE_BULLISH_ON_SIDE"
    elif no_vig_delta < -TOLERANCE:
        no_vig_direction = "MARKET_LESS_BULLISH_ON_SIDE"
    else:
        no_vig_direction = "UNCHANGED"

    base.update({
        "movement_status": price_direction,
        "price_comparison_comparable": True,
        "raw_break_even_probability_delta": raw_delta,
        "raw_break_even_percentage_points_delta": raw_delta * 100.0,
        "no_vig_probability_delta": no_vig_delta,
        "no_vig_percentage_points_delta": no_vig_delta * 100.0,
        "american_odds_delta": odds_delta,
        "price_only_previous_ev_using_current_model": previous_ev_using_current_model,
        "price_only_current_ev_using_current_model": current_ev_using_current_model,
        "price_only_ev_delta": price_only_ev_delta,
        "price_only_ev_percentage_points_delta": price_only_ev_delta * 100.0,
        "price_direction": price_direction,
        "no_vig_direction": no_vig_direction,
        "line_delta": 0.0 if current["market_line"] is not None else None,
        "ev_comparison_model_probability": current["model_probability"],
        "ev_comparison_holds_current_model_probability_constant": True,
    })
    return base


__all__ = [
    "CLOCK_SKEW_TOLERANCE_SECONDS",
    "DATA_TYPE",
    "MLBMarketMovementError",
    "OBSERVATION_DATA_TYPE",
    "SCHEMA_VERSION",
    "SOURCE",
    "SUPPORTED_MARKETS",
    "build_market_observation",
    "canonical_utc_timestamp",
    "compare_market_observations",
    "observation_identity",
    "observation_identity_key",
    "parse_utc_timestamp",
]
