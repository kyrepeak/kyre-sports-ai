"""Step 9B: compare frozen Step-9A fair probabilities with one exact sportsbook quote.

Sportsbook information enters only after the basketball projection and threshold
probabilities are frozen. This layer accepts a caller-supplied same-line two-way
quote, removes vig by proportional normalization, measures model edge, computes
standard push-refund EV, and derives the minimum playable price for a requested EV.

It never calls a sportsbook, never changes Step 8/9A probabilities, never ranks
across props, and never mutates Supabase/persistence or activates production.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping

from sports_api.wnba_step9_threshold_pricing import (
    MODEL_VERSION as STEP9A_MODEL_VERSION,
    RELEASE_ID as STEP9A_RELEASE_ID,
    SCHEMA_VERSION as STEP9A_SCHEMA_VERSION,
)

SOURCE = "Kyre Sports API WNBA Step 9B sportsbook market comparison"
SCHEMA_VERSION = "wnba_step_9b_sportsbook_market_comparison_v1"
MODEL_VERSION = "wnba_step9b_post_projection_market_comparison_2026_regular_v1"
RELEASE_ID = "wnba_step9b_sportsbook_market_comparison_2026_regular_season_v1"
STEP9B_MARKET_COMPARISON_ENABLED_ENV = "WNBA_STEP9B_MARKET_COMPARISON_ENABLED"
STEP9A_FROZEN_SHA = "3b9acde91250d0e7a1767f3861765d4366f510ba"
MAX_ABS_AMERICAN_ODDS = 100_000
DEFAULT_MAX_MARKET_AGE_MINUTES = 10
MAX_MARKET_AGE_MINUTES = 1_440
MARKET_FUTURE_TOLERANCE_SECONDS = 120
MAX_MINIMUM_REQUIRED_EV = 1.0
_SIDES = ("over", "under")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep9MarketComparisonDisabledError(RuntimeError):
    """Raised when Step 9B is not explicitly enabled in this process."""


class WNBAStep9MarketComparisonNotReadyError(RuntimeError):
    """Raised when the quote is stale or Step 9A cannot support comparison."""


class WNBAStep9MarketComparisonUpstreamError(RuntimeError):
    """Raised when the frozen Step-9A payload is malformed or tampered."""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step9b_market_comparison_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP9B_MARKET_COMPARISON_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep9MarketComparisonDisabledError(
            "Step 9B refuses production switches: " + ", ".join(bad)
        )
    if not _truthy(source.get(STEP9B_MARKET_COMPARISON_ENABLED_ENV)):
        raise WNBAStep9MarketComparisonDisabledError(
            f"Step 9B requires {STEP9B_MARKET_COMPARISON_ENABLED_ENV}=true."
        )


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(
        len(text) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in text)
    )


def _sportsbook(value: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 80:
        raise ValueError("WNBA sportsbook must be a non-empty string of at most 80 characters.")
    return text


def _american_odds(value: int, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(
            f"WNBA {label} must be integer American odds with absolute value at least 100."
        )
    try:
        number_float = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"WNBA {label} must be integer American odds with absolute value at least 100."
        ) from exc
    if not math.isfinite(number_float) or not number_float.is_integer():
        raise ValueError(
            f"WNBA {label} must be integer American odds with absolute value at least 100."
        )
    number = int(number_float)
    if abs(number) < 100 or abs(number) > MAX_ABS_AMERICAN_ODDS:
        raise ValueError(
            f"WNBA {label} must have absolute value from 100 through {MAX_ABS_AMERICAN_ODDS}."
        )
    return number


def _minimum_required_ev(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("WNBA minimum_required_ev must be a number from 0 through 1.0.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("WNBA minimum_required_ev must be a number from 0 through 1.0.") from exc
    if not math.isfinite(number) or not 0.0 <= number <= MAX_MINIMUM_REQUIRED_EV:
        raise ValueError("WNBA minimum_required_ev must be a number from 0 through 1.0.")
    return round(number, 8)


def _market_age_limit(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= MAX_MARKET_AGE_MINUTES
    ):
        raise ValueError("WNBA max_market_age_minutes must be an integer from 1 through 1440.")
    return value


def _parse_market_timestamp(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(
            "WNBA market_captured_at_utc is required and must be timezone-aware ISO-8601."
        )
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            "WNBA market_captured_at_utc must be timezone-aware ISO-8601."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("WNBA market_captured_at_utc must include a timezone offset or Z.")
    return parsed.astimezone(timezone.utc)


def _evaluated_at(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("WNBA evaluated_at must be timezone-aware.")
    return result.astimezone(timezone.utc)


def _american_to_decimal(odds: int) -> float:
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def _american_implied_probability(odds: int) -> float:
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def _decimal_to_american(decimal_odds: float) -> int | None:
    if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
        return None
    if abs(decimal_odds - 2.0) < 1e-12:
        return 100
    if decimal_odds > 2.0:
        return int(round((decimal_odds - 1.0) * 100.0))
    return int(round(-100.0 / (decimal_odds - 1.0)))


def _validate_pricing_hash(pricing: Mapping[str, Any]) -> str:
    observed = str(pricing.get("pricing_content_sha256") or "").strip().lower()
    if not _valid_sha256(observed):
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B requires a valid Step-9A pricing_content_sha256."
        )
    surface = dict(pricing)
    surface.pop("generated_at_utc", None)
    surface.pop("pricing_content_sha256", None)
    expected = _canonical_hash(surface)
    if observed != expected:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B detected a Step-9A pricing content-hash mismatch."
        )
    return observed


def _probability(record: Any, label: str) -> float:
    if not isinstance(record, Mapping):
        raise WNBAStep9MarketComparisonUpstreamError(
            f"Step 9B missing Step-9A {label} probability record."
        )
    try:
        result = float(record.get("probability"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MarketComparisonUpstreamError(
            f"Step 9B invalid Step-9A {label} probability."
        ) from exc
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise WNBAStep9MarketComparisonUpstreamError(
            f"Step 9B invalid Step-9A {label} probability."
        )
    return result


def _fair_probability(record: Any, label: str) -> float:
    if not isinstance(record, Mapping):
        raise WNBAStep9MarketComparisonUpstreamError(
            f"Step 9B missing Step-9A fair {label} record."
        )
    try:
        result = float(record.get("fair_probability"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MarketComparisonUpstreamError(
            f"Step 9B invalid Step-9A fair {label} probability."
        ) from exc
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise WNBAStep9MarketComparisonUpstreamError(
            f"Step 9B invalid Step-9A fair {label} probability."
        )
    return result


def _validate_step9a_pricing(
    pricing: Mapping[str, Any],
) -> tuple[str, int, str, str, str, float, str, dict[str, float]]:
    if not isinstance(pricing, Mapping):
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B requires a Step-9A pricing object."
        )
    if pricing.get("data_type") != "post_projection_prop_threshold_pricing":
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B received the wrong Step-9A data type."
        )
    if pricing.get("schema_version") != STEP9A_SCHEMA_VERSION:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B received an unsupported Step-9A schema version."
        )
    if pricing.get("model_version") != STEP9A_MODEL_VERSION:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B received an unsupported Step-9A model version."
        )
    if pricing.get("release_id") != STEP9A_RELEASE_ID:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B received an unsupported Step-9A release identity."
        )
    game_id = str(pricing.get("game_id") or "").strip()
    try:
        player_id = int(pricing.get("player_id"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B received an invalid Step-9A player identity."
        ) from exc
    team_key = str(pricing.get("team_key") or "").strip()
    opponent_key = str(pricing.get("opponent_team_key") or "").strip()
    prop = pricing.get("prop")
    if (
        len(game_id) != 10
        or not game_id.isdigit()
        or player_id <= 0
        or not team_key
        or not opponent_key
        or team_key == opponent_key
        or not isinstance(prop, Mapping)
    ):
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B received malformed Step-9A game/player/team identity."
        )
    stat = str(prop.get("stat") or "").strip()
    try:
        line = float(prop.get("line"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B received an invalid Step-9A prop line."
        ) from exc
    if stat not in {"points", "rebounds", "assists", "pra"} or not math.isfinite(line):
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B received an invalid Step-9A prop identity."
        )
    if prop.get("line_does_not_change_basketball_projection") is not True:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B requires Step 9A to preserve the post-projection threshold guardrail."
        )

    raw = pricing.get("raw_probabilities")
    resolved = pricing.get("resolved_non_push")
    precision = pricing.get("precision")
    step8_lineage = pricing.get("step8_lineage")
    guardrails = pricing.get("guardrails")
    if not all(
        isinstance(item, Mapping)
        for item in (raw, resolved, precision, step8_lineage, guardrails)
    ):
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B requires complete Step-9A pricing evidence."
        )
    p_over = _probability(raw.get("over"), "over")
    p_push = _probability(raw.get("push"), "push")
    p_under = _probability(raw.get("under"), "under")
    if abs((p_over + p_push + p_under) - 1.0) > 2e-8:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B Step-9A raw probabilities do not sum to one."
        )
    resolved_probability = p_over + p_under
    try:
        declared_resolved = float(resolved.get("probability"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B invalid Step-9A resolved probability."
        ) from exc
    if abs(declared_resolved - resolved_probability) > 2e-8 or resolved_probability <= 0.0:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B Step-9A resolved probability is inconsistent."
        )
    fair_over = _fair_probability(resolved.get("over"), "over")
    fair_under = _fair_probability(resolved.get("under"), "under")
    if (
        abs(fair_over - p_over / resolved_probability) > 2e-8
        or abs(fair_under - p_under / resolved_probability) > 2e-8
        or abs((fair_over + fair_under) - 1.0) > 2e-8
    ):
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B Step-9A resolved fair probabilities are inconsistent."
        )
    if precision.get("step8_converged") is not True:
        raise WNBAStep9MarketComparisonNotReadyError(
            "Step 9B requires Step 9A to reference a converged Step-8 distribution."
        )
    if guardrails.get("post_projection_only") is not True:
        raise WNBAStep9MarketComparisonUpstreamError(
            "Step 9B requires Step 9A to remain post-projection only."
        )
    for key in (
        "sportsbook_quote_consumed",
        "sportsbook_called",
        "vig_removed",
        "edge_calculated",
        "expected_value_calculated",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    ):
        if guardrails.get(key) is not False:
            raise WNBAStep9MarketComparisonUpstreamError(
                f"Step 9B requires frozen Step-9A guardrail {key!r} to be false."
            )
    step9a_hash = _validate_pricing_hash(pricing)
    return (
        game_id,
        player_id,
        team_key,
        opponent_key,
        stat,
        line,
        step9a_hash,
        {"over": p_over, "push": p_push, "under": p_under,
         "fair_over": fair_over, "fair_under": fair_under},
    )


def _market_quote(over_odds: int, under_odds: int) -> dict[str, Any]:
    over_decimal = _american_to_decimal(over_odds)
    under_decimal = _american_to_decimal(under_odds)
    over_implied = _american_implied_probability(over_odds)
    under_implied = _american_implied_probability(under_odds)
    total_implied = over_implied + under_implied
    if total_implied <= 0.0:
        raise ValueError("WNBA two-way sportsbook implied probability sum must be positive.")
    no_vig_over = over_implied / total_implied
    no_vig_under = under_implied / total_implied
    return {
        "over": {
            "american_odds": over_odds,
            "decimal_odds": round(over_decimal, 8),
            "profit_multiple_per_unit_staked": round(over_decimal - 1.0, 8),
            "raw_implied_probability": round(over_implied, 10),
            "raw_implied_percentage": round(over_implied * 100.0, 6),
            "no_vig_probability": round(no_vig_over, 10),
            "no_vig_percentage": round(no_vig_over * 100.0, 6),
        },
        "under": {
            "american_odds": under_odds,
            "decimal_odds": round(under_decimal, 8),
            "profit_multiple_per_unit_staked": round(under_decimal - 1.0, 8),
            "raw_implied_probability": round(under_implied, 10),
            "raw_implied_percentage": round(under_implied * 100.0, 6),
            "no_vig_probability": round(no_vig_under, 10),
            "no_vig_percentage": round(no_vig_under * 100.0, 6),
        },
        "two_sided_raw_implied_probability_sum": round(total_implied, 10),
        "sportsbook_margin_probability": round(total_implied - 1.0, 10),
        "sportsbook_margin_percentage": round((total_implied - 1.0) * 100.0, 6),
        "no_vig_method": "proportional_normalization_of_two_sided_raw_implied_probabilities",
        "no_vig_probability_sum": round(no_vig_over + no_vig_under, 10),
    }


def _market_freshness(
    captured_at: datetime,
    *,
    evaluated_at: datetime,
    max_age_minutes: int,
    require_fresh_market: bool,
) -> dict[str, Any]:
    delta_seconds = (evaluated_at - captured_at).total_seconds()
    if delta_seconds < -MARKET_FUTURE_TOLERANCE_SECONDS:
        raise ValueError(
            "WNBA market_captured_at_utc cannot be more than 120 seconds in the future."
        )
    age_seconds = max(0.0, delta_seconds)
    stale = age_seconds > max_age_minutes * 60.0
    if stale and require_fresh_market:
        raise WNBAStep9MarketComparisonNotReadyError(
            f"Sportsbook market quote is stale: age {age_seconds / 60.0:.2f} minutes exceeds "
            f"the {max_age_minutes}-minute limit."
        )
    return {
        "status": "stale" if stale else "fresh",
        "fresh": not stale,
        "stale": stale,
        "require_fresh_market": require_fresh_market,
        "max_market_age_minutes": max_age_minutes,
        "market_age_seconds": round(age_seconds, 3),
        "market_age_minutes": round(age_seconds / 60.0, 6),
        "captured_at_utc": captured_at.isoformat(),
        "evaluated_at_utc": evaluated_at.isoformat(),
        "future_clock_tolerance_seconds": MARKET_FUTURE_TOLERANCE_SECONDS,
    }


def _required_price(
    win_probability: float,
    loss_probability: float,
    minimum_required_ev: float,
) -> dict[str, Any]:
    if win_probability <= 0.0:
        return {
            "available": False,
            "minimum_required_ev_per_unit": minimum_required_ev,
            "minimum_acceptable_decimal_odds": None,
            "minimum_acceptable_american_odds": None,
            "reason": "zero_model_win_probability_cannot_support_finite_positive_payout_threshold",
        }
    required_profit = (minimum_required_ev + loss_probability) / win_probability
    required_decimal = 1.0 + required_profit
    return {
        "available": True,
        "minimum_required_ev_per_unit": minimum_required_ev,
        "minimum_required_ev_percentage": round(minimum_required_ev * 100.0, 6),
        "minimum_acceptable_decimal_odds": round(required_decimal, 8),
        "minimum_acceptable_american_odds": _decimal_to_american(required_decimal),
        "semantics": (
            "Any offered decimal price at or above this threshold meets the requested "
            "model EV under standard win/loss/push-refund settlement."
        ),
    }


def _side_result(
    side: str,
    *,
    probabilities: Mapping[str, float],
    quote: Mapping[str, Any],
    minimum_required_ev: float,
    step9a_pricing: Mapping[str, Any],
) -> dict[str, Any]:
    opposite = "under" if side == "over" else "over"
    p_win = float(probabilities[side])
    p_loss = float(probabilities[opposite])
    p_push = float(probabilities["push"])
    fair = float(probabilities[f"fair_{side}"])
    offered = quote[side]
    raw_implied = float(offered["raw_implied_probability"])
    no_vig = float(offered["no_vig_probability"])
    profit_multiple = float(offered["profit_multiple_per_unit_staked"])
    ev = p_win * profit_multiple - p_loss
    required = _required_price(p_win, p_loss, minimum_required_ev)
    offered_decimal = float(offered["decimal_odds"])
    meets = bool(
        required.get("available")
        and offered_decimal + 1e-12 >= float(required["minimum_acceptable_decimal_odds"])
    )
    fair_record = (step9a_pricing.get("resolved_non_push") or {}).get(side)
    return {
        "side": side,
        "model": {
            "raw_win_probability": round(p_win, 10),
            "raw_loss_probability": round(p_loss, 10),
            "raw_push_probability": round(p_push, 10),
            "resolved_non_push_probability": round(p_win + p_loss, 10),
            "resolved_fair_win_probability": round(fair, 10),
            "resolved_fair_win_percentage": round(fair * 100.0, 6),
            "fair_price_from_step9a": deepcopy(fair_record),
        },
        "market": deepcopy(offered),
        "edge": {
            "vs_raw_sportsbook_implied_probability": round(fair - raw_implied, 10),
            "vs_raw_sportsbook_implied_percentage_points": round(
                (fair - raw_implied) * 100.0, 6
            ),
            "vs_no_vig_market_probability": round(fair - no_vig, 10),
            "vs_no_vig_market_percentage_points": round((fair - no_vig) * 100.0, 6),
        },
        "expected_value": {
            "net_profit_per_unit_staked": round(ev, 10),
            "roi_percentage": round(ev * 100.0, 6),
            "expected_return_including_original_stake": round(1.0 + ev, 10),
            "positive_ev": ev > 0.0,
            "formula": "P(win)*profit_multiple-P(loss); push contributes zero net profit",
        },
        "price_threshold": {
            **required,
            "offered_price_meets_minimum_required_ev": meets,
            "offered_decimal_odds": offered_decimal,
            "offered_american_odds": offered["american_odds"],
        },
    }


def build_step9b_market_comparison(
    pricing: Mapping[str, Any],
    *,
    sportsbook: str,
    over_odds: int,
    under_odds: int,
    market_captured_at_utc: str,
    minimum_required_ev: float = 0.0,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    require_fresh_market: bool = True,
    evaluated_at: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Compare one frozen Step-9A prop line with one exact two-way market quote."""
    _assert_safe_environment(env)
    book = _sportsbook(sportsbook)
    over = _american_odds(over_odds, "over_odds")
    under = _american_odds(under_odds, "under_odds")
    min_ev = _minimum_required_ev(minimum_required_ev)
    max_age = _market_age_limit(max_market_age_minutes)
    if not isinstance(require_fresh_market, bool):
        raise ValueError("WNBA require_fresh_market must be boolean.")
    captured = _parse_market_timestamp(market_captured_at_utc)
    evaluated = _evaluated_at(evaluated_at)

    (
        game_id,
        player_id,
        team_key,
        opponent_key,
        stat,
        line,
        step9a_hash,
        probabilities,
    ) = _validate_step9a_pricing(pricing)
    quote = _market_quote(over, under)
    freshness = _market_freshness(
        captured,
        evaluated_at=evaluated,
        max_age_minutes=max_age,
        require_fresh_market=require_fresh_market,
    )
    over_result = _side_result(
        "over",
        probabilities=probabilities,
        quote=quote,
        minimum_required_ev=min_ev,
        step9a_pricing=pricing,
    )
    under_result = _side_result(
        "under",
        probabilities=probabilities,
        quote=quote,
        minimum_required_ev=min_ev,
        step9a_pricing=pricing,
    )
    ev_over = float(over_result["expected_value"]["net_profit_per_unit_staked"])
    ev_under = float(under_result["expected_value"]["net_profit_per_unit_staked"])
    edge_over = float(over_result["edge"]["vs_no_vig_market_probability"])
    edge_under = float(under_result["edge"]["vs_no_vig_market_probability"])

    result = {
        "data_type": "post_projection_sportsbook_market_comparison",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": evaluated.isoformat(),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "prop": {
            "stat": stat,
            "line": line,
            "line_and_sportsbook_quote_enter_after_projection": True,
        },
        "sportsbook": {
            "name": book,
            "market_freshness": freshness,
            "quote": quote,
            "quote_source": "caller_supplied_exact_two_way_same_line_quote",
            "network_fetch_performed": False,
        },
        "comparison": {
            "over": over_result,
            "under": under_result,
            "higher_ev_side": "over" if ev_over > ev_under else "under" if ev_under > ev_over else "tie",
            "higher_no_vig_edge_side": (
                "over" if edge_over > edge_under else "under" if edge_under > edge_over else "tie"
            ),
            "ranking_or_qualification_applied": False,
        },
        "step9a_lineage": {
            "release_id": STEP9A_RELEASE_ID,
            "model_version": STEP9A_MODEL_VERSION,
            "schema_version": STEP9A_SCHEMA_VERSION,
            "pricing_content_sha256": step9a_hash,
            "frozen_git_sha": STEP9A_FROZEN_SHA,
        },
        "guardrails": {
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9a_probabilities_changed": False,
            "sportsbook_quote_consumed": True,
            "sportsbook_called": False,
            "vig_removed": True,
            "edge_calculated": True,
            "expected_value_calculated": True,
            "cross_sportsbook_consensus_calculated": False,
            "cross_prop_ranking_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    hash_surface = dict(result)
    hash_surface.pop("generated_at_utc", None)
    result["comparison_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return result
