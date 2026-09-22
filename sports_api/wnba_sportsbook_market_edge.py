"""Step 5G: WNBA sportsbook market comparison, no-vig, edge, and EV engine.

Consumes the frozen Step 5F threshold probability output and a caller-supplied
same-line two-way sportsbook quote. Sportsbook information enters only after the
basketball projection/simulation/probability chain is frozen and cannot alter it.

For standard push-refund settlement, model fair probabilities and sportsbook
implied probabilities are compared on resolved (non-push) outcomes, while EV is
computed from raw model win/loss/push probabilities:
    EV per unit staked = P(win) * profit_multiple - P(loss)
Push contributes zero net profit because the stake is returned.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from typing import Any

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_model_input_readiness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES
from sports_api.wnba_prop_threshold_probability import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_COUNT,
    MAX_BATCH_SIZE,
    MAX_PROP_LINE,
    MAX_SIMULATION_COUNT,
    MIN_BATCH_SIZE,
    MIN_SIMULATION_COUNT,
    MODEL_VERSION as THRESHOLD_MODEL_VERSION,
    SUPPORTED_STATS,
    WNBAPropThresholdModelInputError,
    WNBAPropThresholdNotFoundError,
    WNBAPropThresholdNotReadyError,
    WNBAPropThresholdUpstreamError,
    get_player_game_prop_threshold_probability,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5G sportsbook market edge and EV engine"
MODEL_VERSION = "wnba_step_5g_sportsbook_market_edge_v1"
MODEL_FAMILY = "post_projection_two_way_market_comparison"

SCENARIO_KEYS = ("low", "base", "high")
SIDES = ("over", "under")
MAX_RECENT_GAMES = 20
MIN_DISTRIBUTION_GAMES = 1
MAX_DISTRIBUTION_GAMES = 50
MAX_ABS_AMERICAN_ODDS = 100_000
DEFAULT_MAX_MARKET_AGE_MINUTES = 10
MAX_MARKET_AGE_MINUTES = 1_440
MARKET_FUTURE_TOLERANCE_SECONDS = 120
MAX_MINIMUM_REQUIRED_EV = 1.0


class WNBASportsbookMarketNotReadyError(RuntimeError):
    pass


class WNBASportsbookMarketNotFoundError(LookupError):
    pass


class WNBASportsbookMarketUpstreamError(RuntimeError):
    pass


class WNBASportsbookMarketModelInputError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _positive_player_id(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA player_id must be a positive integer.")
    return value


def _game_id(value: str) -> str:
    result = str(value).strip()
    if len(result) != 10 or not result.isdigit():
        raise ValueError("WNBA game_id must be exactly 10 numeric digits.")
    return result


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(str(value).strip().casefold())
    if result is None:
        raise ValueError(
            f"Unsupported WNBA {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _stat(value: str) -> str:
    text = " ".join(str(value).strip().casefold().split())
    aliases = {
        "points": "points", "point": "points", "pts": "points",
        "rebounds": "rebounds", "rebound": "rebounds", "reb": "rebounds", "rebs": "rebounds",
        "assists": "assists", "assist": "assists", "ast": "assists", "asts": "assists",
        "pra": "pra", "points+rebounds+assists": "pra", "points rebounds assists": "pra",
    }
    result = aliases.get(text)
    if result is None:
        raise ValueError(
            "Unsupported WNBA prop stat "
            f"{value!r}. Allowed canonical values: {', '.join(SUPPORTED_STATS)}."
        )
    return result


def _line(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}."
        ) from exc
    if not isfinite(number) or not 0.0 <= number <= MAX_PROP_LINE:
        raise ValueError(f"WNBA prop line must be a number from 0 through {MAX_PROP_LINE:g}.")
    return round(number, 6)


def _last_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_RECENT_GAMES:
        raise ValueError("WNBA last_n_games must be an integer from 1 through 20.")
    return value


def _distribution_last_n(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not MIN_DISTRIBUTION_GAMES <= value <= MAX_DISTRIBUTION_GAMES
    ):
        raise ValueError("WNBA distribution_last_n_games must be an integer from 1 through 50.")
    return value


def _simulation_count(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not MIN_SIMULATION_COUNT <= value <= MAX_SIMULATION_COUNT
    ):
        raise ValueError(
            f"WNBA simulation_count must be an integer from "
            f"{MIN_SIMULATION_COUNT:,} through {MAX_SIMULATION_COUNT:,}."
        )
    return value


def _batch_size(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not MIN_BATCH_SIZE <= value <= MAX_BATCH_SIZE
    ):
        raise ValueError(
            f"WNBA batch_size must be an integer from "
            f"{MIN_BATCH_SIZE:,} through {MAX_BATCH_SIZE:,}."
        )
    return value


def _random_seed(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value <= 4_294_967_295
    ):
        raise ValueError("WNBA random_seed must be an integer from 0 through 4294967295.")
    return value


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be boolean.")
    return value


def _max_snapshot_age(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 1440:
        raise ValueError("WNBA max_snapshot_age_minutes must be an integer from 1 through 1440.")
    return value


def _market_age_limit(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 1 <= value <= MAX_MARKET_AGE_MINUTES
    ):
        raise ValueError("WNBA max_market_age_minutes must be an integer from 1 through 1440.")
    return value


def _minimum_required_ev(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("WNBA minimum_required_ev must be a number from 0 through 1.0.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("WNBA minimum_required_ev must be a number from 0 through 1.0.") from exc
    if not isfinite(number) or not 0.0 <= number <= MAX_MINIMUM_REQUIRED_EV:
        raise ValueError("WNBA minimum_required_ev must be a number from 0 through 1.0.")
    return round(number, 8)


def _sportsbook(value: str) -> str:
    text = _clean(value)
    if not text or len(text) > 80:
        raise ValueError("WNBA sportsbook must be a non-empty string of at most 80 characters.")
    return text


def _american_odds(value: int, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be integer American odds with absolute value at least 100.")
    try:
        number_float = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"WNBA {label} must be integer American odds with absolute value at least 100."
        ) from exc
    if not isfinite(number_float) or not number_float.is_integer():
        raise ValueError(
            f"WNBA {label} must be integer American odds with absolute value at least 100."
        )
    number = int(number_float)
    if abs(number) < 100 or abs(number) > MAX_ABS_AMERICAN_ODDS:
        raise ValueError(
            f"WNBA {label} must have absolute value from 100 through {MAX_ABS_AMERICAN_ODDS}."
        )
    return number


def _parse_market_timestamp(value: str) -> datetime:
    text = _clean(value)
    if not text:
        raise ValueError("WNBA market_captured_at_utc is required and must be timezone-aware ISO-8601.")
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


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = _clean(value)
    return bool(
        text
        and len(text) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in text)
    )


def _verify_step_5f_fingerprint(threshold: dict[str, Any]) -> None:
    step_5e_ref = threshold.get("step_5e_reference")
    model_config = threshold.get("model_config")
    results = threshold.get("conditional_scenario_results")
    sensitivity = threshold.get("scenario_sensitivity")
    if (
        not isinstance(step_5e_ref, dict)
        or not isinstance(model_config, dict)
        or not isinstance(results, dict)
        or not isinstance(sensitivity, dict)
    ):
        raise WNBASportsbookMarketUpstreamError(
            "Step 5F fingerprint source fields are missing."
        )
    simulation_fingerprint = step_5e_ref.get("simulation_fingerprint_sha256")
    if not _valid_sha256(simulation_fingerprint):
        raise WNBASportsbookMarketUpstreamError(
            "Step 5F references a missing or invalid Step 5E simulation fingerprint."
        )
    payload = {
        "step_5e_simulation_fingerprint_sha256": simulation_fingerprint,
        "model_config": model_config,
        "conditional_threshold_results": results,
        "scenario_sensitivity": sensitivity,
    }
    expected = _canonical_hash(payload)
    observed = _clean(threshold.get("probability_fingerprint_sha256"))
    if observed != expected:
        raise WNBASportsbookMarketUpstreamError(
            "Step 5F probability fingerprint does not match its hash-covered content."
        )


def _validate_threshold(
    threshold: dict[str, Any],
) -> tuple[int, str, str, str, str, float]:
    if not isinstance(threshold, dict):
        raise ValueError("WNBA Step 5G threshold payload must be an object.")
    if threshold.get("model_version") != THRESHOLD_MODEL_VERSION:
        raise WNBASportsbookMarketUpstreamError(
            "Step 5G received an unexpected Step 5F model version."
        )
    if not _valid_sha256(threshold.get("probability_fingerprint_sha256")):
        raise WNBASportsbookMarketUpstreamError(
            "Step 5F probability fingerprint is missing or invalid."
        )
    player_id = _to_int(threshold.get("player_id"))
    game_id = _clean(threshold.get("game_id"))
    team_key = _clean(threshold.get("team_key"))
    opponent_key = _clean(threshold.get("opponent_team_key"))
    prop = threshold.get("prop")
    if (
        player_id is None
        or player_id <= 0
        or not game_id
        or len(game_id) != 10
        or not game_id.isdigit()
        or not team_key
        or not opponent_key
        or team_key == opponent_key
        or not isinstance(prop, dict)
    ):
        raise WNBASportsbookMarketUpstreamError(
            "Step 5F player/game/team/prop identity is malformed."
        )
    stat = _clean(prop.get("stat"))
    line = _to_float(prop.get("line"))
    if stat not in SUPPORTED_STATS or line is None or line < 0 or line > MAX_PROP_LINE:
        raise WNBASportsbookMarketUpstreamError("Step 5F prop identity is invalid.")
    if prop.get("line_does_not_change_basketball_projection") is not True:
        raise WNBASportsbookMarketUpstreamError(
            "Step 5F does not preserve the post-projection threshold guardrail."
        )
    results = threshold.get("conditional_scenario_results")
    if not isinstance(results, dict):
        raise WNBASportsbookMarketUpstreamError(
            "Step 5F conditional scenario results are missing."
        )
    for scenario in SCENARIO_KEYS:
        row = results.get(scenario)
        if not isinstance(row, dict):
            raise WNBASportsbookMarketUpstreamError(
                f"Step 5F is missing {scenario.upper()} threshold results."
            )
        if _clean(row.get("conditional_scenario")) != scenario:
            raise WNBASportsbookMarketUpstreamError(
                f"Step 5F {scenario.upper()} scenario identity is inconsistent."
            )
        if _clean(row.get("stat")) != stat or _to_float(row.get("line")) != line:
            raise WNBASportsbookMarketUpstreamError(
                f"Step 5F {scenario.upper()} prop identity disagrees with top-level prop."
            )
    primary = threshold.get("primary_result")
    if not isinstance(primary, dict) or primary != results.get("base"):
        raise WNBASportsbookMarketUpstreamError(
            "Step 5F primary result does not exactly match its BASE scenario."
        )
    _verify_step_5f_fingerprint(threshold)
    return player_id, game_id, team_key, opponent_key, stat, float(line)


def _american_to_decimal(odds: int) -> float:
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def _american_implied_probability(odds: int) -> float:
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def _decimal_to_american(decimal_odds: float) -> int | None:
    if not isfinite(decimal_odds) or decimal_odds <= 1.0:
        return None
    if abs(decimal_odds - 2.0) < 1e-12:
        return 100
    if decimal_odds > 2.0:
        return int(round((decimal_odds - 1.0) * 100.0))
    return int(round(-100.0 / (decimal_odds - 1.0)))


def _market_quote(over_odds: int, under_odds: int) -> dict[str, Any]:
    over_decimal = _american_to_decimal(over_odds)
    under_decimal = _american_to_decimal(under_odds)
    over_implied = _american_implied_probability(over_odds)
    under_implied = _american_implied_probability(under_odds)
    total_implied = over_implied + under_implied
    if total_implied <= 0:
        raise WNBASportsbookMarketModelInputError(
            "Two-sided sportsbook implied-probability sum must be positive."
        )
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
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("WNBA evaluated_at must be timezone-aware for market freshness checks.")
    evaluated_at = evaluated_at.astimezone(timezone.utc)
    captured_at = captured_at.astimezone(timezone.utc)
    delta_seconds = (evaluated_at - captured_at).total_seconds()
    if delta_seconds < -MARKET_FUTURE_TOLERANCE_SECONDS:
        raise ValueError(
            "WNBA market_captured_at_utc cannot be more than 120 seconds in the future."
        )
    age_seconds = max(0.0, delta_seconds)
    stale = age_seconds > max_age_minutes * 60.0
    status = "stale" if stale else "fresh"
    if stale and require_fresh_market:
        raise WNBASportsbookMarketNotReadyError(
            f"Sportsbook market quote is stale: age {age_seconds / 60.0:.2f} minutes exceeds "
            f"the {max_age_minutes}-minute limit."
        )
    return {
        "status": status,
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


def _probability_from_record(record: dict[str, Any], label: str) -> float:
    if not isinstance(record, dict):
        raise WNBASportsbookMarketUpstreamError(f"Step 5F {label} probability record is missing.")
    probability = _to_float(record.get("probability"))
    if probability is None or not 0.0 <= probability <= 1.0:
        raise WNBASportsbookMarketUpstreamError(f"Step 5F {label} probability is invalid.")
    return probability


def _fair_probability(fair_record: dict[str, Any], label: str) -> float:
    if not isinstance(fair_record, dict) or fair_record.get("available") is not True:
        raise WNBASportsbookMarketNotReadyError(
            f"Step 5F fair {label} probability is unavailable for market comparison."
        )
    probability = _to_float(fair_record.get("fair_probability"))
    if probability is None or not 0.0 < probability <= 1.0:
        raise WNBASportsbookMarketUpstreamError(
            f"Step 5F fair {label} probability is invalid."
        )
    return probability


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
            "model EV under standard win/loss/push settlement."
        ),
    }


def _scenario_side(
    scenario_name: str,
    threshold_scenario: dict[str, Any],
    side: str,
    quote: dict[str, Any],
    minimum_required_ev: float,
) -> dict[str, Any]:
    opposite = "under" if side == "over" else "over"
    raw = threshold_scenario.get("raw_probabilities")
    fair = threshold_scenario.get("fair_odds")
    if not isinstance(raw, dict) or not isinstance(fair, dict):
        raise WNBASportsbookMarketUpstreamError(
            f"Step 5F {scenario_name.upper()} probability/fair-odds fields are missing."
        )
    p_win = _probability_from_record(raw.get(side), f"{scenario_name}.{side}")
    p_loss = _probability_from_record(raw.get(opposite), f"{scenario_name}.{opposite}")
    p_push = _probability_from_record(raw.get("push"), f"{scenario_name}.push")
    if abs((p_win + p_loss + p_push) - 1.0) > 1e-8:
        raise WNBASportsbookMarketUpstreamError(
            f"Step 5F {scenario_name.upper()} raw probabilities do not sum to one."
        )
    model_fair = _fair_probability(fair.get(side), f"{scenario_name}.{side}")
    resolved = p_win + p_loss
    if resolved <= 0.0 or abs(model_fair - p_win / resolved) > 1e-8:
        raise WNBASportsbookMarketUpstreamError(
            f"Step 5F {scenario_name.upper()} resolved fair {side} probability is inconsistent."
        )
    market_side = quote[side]
    offered_decimal = market_side["decimal_odds"]
    profit_multiple = market_side["profit_multiple_per_unit_staked"]
    raw_implied = market_side["raw_implied_probability"]
    no_vig = market_side["no_vig_probability"]
    ev = p_win * profit_multiple - p_loss
    expected_return = 1.0 + ev
    required = _required_price(p_win, p_loss, minimum_required_ev)
    offered_meets_required = bool(
        required.get("available")
        and offered_decimal + 1e-12 >= required["minimum_acceptable_decimal_odds"]
    )
    return {
        "conditional_scenario": scenario_name,
        "side": side,
        "model": {
            "raw_win_probability": round(p_win, 10),
            "raw_loss_probability": round(p_loss, 10),
            "raw_push_probability": round(p_push, 10),
            "resolved_non_push_probability": round(resolved, 10),
            "resolved_fair_win_probability": round(model_fair, 10),
            "resolved_fair_win_percentage": round(model_fair * 100.0, 6),
        },
        "market": deepcopy(market_side),
        "edge": {
            "vs_raw_sportsbook_implied_probability": round(model_fair - raw_implied, 10),
            "vs_raw_sportsbook_implied_percentage_points": round((model_fair - raw_implied) * 100.0, 6),
            "vs_no_vig_market_probability": round(model_fair - no_vig, 10),
            "vs_no_vig_market_percentage_points": round((model_fair - no_vig) * 100.0, 6),
        },
        "expected_value": {
            "net_profit_per_unit_staked": round(ev, 10),
            "roi_percentage": round(ev * 100.0, 6),
            "expected_return_including_original_stake": round(expected_return, 10),
            "positive_ev": ev > 0.0,
            "formula": "P(win)*profit_multiple-P(loss); push contributes zero net profit",
        },
        "price_threshold": {
            **required,
            "offered_price_meets_minimum_required_ev": offered_meets_required,
            "offered_decimal_odds": offered_decimal,
            "offered_american_odds": market_side["american_odds"],
        },
    }


def _scenario_results(
    threshold: dict[str, Any],
    quote: dict[str, Any],
    minimum_required_ev: float,
) -> dict[str, Any]:
    raw = threshold["conditional_scenario_results"]
    out: dict[str, Any] = {}
    for scenario in SCENARIO_KEYS:
        row = raw[scenario]
        out[scenario] = {
            "conditional_scenario": scenario,
            "over": _scenario_side(scenario, row, "over", quote, minimum_required_ev),
            "under": _scenario_side(scenario, row, "under", quote, minimum_required_ev),
        }
    return out


def _side_summary(
    scenario_results: dict[str, Any],
    side: str,
    quote: dict[str, Any],
    minimum_required_ev: float,
) -> dict[str, Any]:
    ev_by = {
        scenario: scenario_results[scenario][side]["expected_value"]["net_profit_per_unit_staked"]
        for scenario in SCENARIO_KEYS
    }
    edge_by = {
        scenario: scenario_results[scenario][side]["edge"]["vs_no_vig_market_probability"]
        for scenario in SCENARIO_KEYS
    }
    required_decimal_by = {
        scenario: scenario_results[scenario][side]["price_threshold"].get(
            "minimum_acceptable_decimal_odds"
        )
        for scenario in SCENARIO_KEYS
    }
    valid_required = [
        value for value in required_decimal_by.values() if isinstance(value, (int, float))
    ]
    conservative_required_decimal = max(valid_required) if valid_required else None
    offered_decimal = quote[side]["decimal_odds"]
    conservative_meets = bool(
        conservative_required_decimal is not None
        and offered_decimal + 1e-12 >= conservative_required_decimal
    )
    base = scenario_results["base"][side]
    worst_ev = min(ev_by.values())
    best_ev = max(ev_by.values())
    return {
        "side": side,
        "base": deepcopy(base),
        "conditional_ev_by_scenario": ev_by,
        "conditional_no_vig_edge_by_scenario": edge_by,
        "base_ev_per_unit": ev_by["base"],
        "base_ev_percentage": round(ev_by["base"] * 100.0, 6),
        "risk_adjusted_ev_per_unit": round(worst_ev, 10),
        "risk_adjusted_ev_percentage": round(worst_ev * 100.0, 6),
        "risk_adjusted_ev_method": "minimum_low_base_high_conditional_scenario_ev_no_scenario_weights",
        "best_conditional_ev_per_unit": round(best_ev, 10),
        "scenario_ev_span": round(best_ev - worst_ev, 10),
        "positive_ev_in_base": ev_by["base"] > 0.0,
        "positive_ev_in_all_conditional_scenarios": all(value > 0.0 for value in ev_by.values()),
        "positive_no_vig_edge_in_all_conditional_scenarios": all(
            value > 0.0 for value in edge_by.values()
        ),
        "price_thresholds": {
            "minimum_required_ev_per_unit": minimum_required_ev,
            "minimum_required_ev_percentage": round(minimum_required_ev * 100.0, 6),
            "required_decimal_odds_by_scenario": required_decimal_by,
            "base_minimum_acceptable_decimal_odds": required_decimal_by["base"],
            "base_minimum_acceptable_american_odds": base["price_threshold"].get(
                "minimum_acceptable_american_odds"
            ),
            "conservative_all_scenarios_minimum_acceptable_decimal_odds": (
                round(conservative_required_decimal, 8)
                if conservative_required_decimal is not None
                else None
            ),
            "conservative_all_scenarios_minimum_acceptable_american_odds": (
                _decimal_to_american(conservative_required_decimal)
                if conservative_required_decimal is not None
                else None
            ),
            "offered_price_meets_base_minimum_required_ev": base["price_threshold"][
                "offered_price_meets_minimum_required_ev"
            ],
            "offered_price_meets_minimum_required_ev_in_all_scenarios": conservative_meets,
        },
    }


def compare_threshold_to_sportsbook_market(
    threshold: dict[str, Any],
    *,
    sportsbook: str,
    over_odds: int,
    under_odds: int,
    market_captured_at_utc: str,
    minimum_required_ev: float = 0.0,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    require_fresh_market: bool = True,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    sportsbook = _sportsbook(sportsbook)
    over_odds = _american_odds(over_odds, "over_odds")
    under_odds = _american_odds(under_odds, "under_odds")
    minimum_required_ev = _minimum_required_ev(minimum_required_ev)
    max_market_age_minutes = _market_age_limit(max_market_age_minutes)
    require_fresh_market = _bool(require_fresh_market, "require_fresh_market")
    captured_at = _parse_market_timestamp(market_captured_at_utc)
    evaluated = evaluated_at or _utc_now()
    freshness = _market_freshness(
        captured_at,
        evaluated_at=evaluated,
        max_age_minutes=max_market_age_minutes,
        require_fresh_market=require_fresh_market,
    )

    player_id, game_id, team_key, opponent_key, stat, line = _validate_threshold(threshold)
    readiness = threshold.get("numerical_readiness")
    if not isinstance(readiness, dict) or readiness.get("ready_for_fair_odds") is not True:
        raise WNBASportsbookMarketNotReadyError(
            "Step 5F is not ready for fair-odds market comparison."
        )

    quote = _market_quote(over_odds, under_odds)
    scenarios = _scenario_results(threshold, quote, minimum_required_ev)
    over_summary = _side_summary(scenarios, "over", quote, minimum_required_ev)
    under_summary = _side_summary(scenarios, "under", quote, minimum_required_ev)

    base_over_ev = over_summary["base_ev_per_unit"]
    base_under_ev = under_summary["base_ev_per_unit"]
    if base_over_ev > 0.0 or base_under_ev > 0.0:
        primary_value_side = "over" if base_over_ev >= base_under_ev else "under"
    else:
        primary_value_side = None
    risk_over = over_summary["risk_adjusted_ev_per_unit"]
    risk_under = under_summary["risk_adjusted_ev_per_unit"]
    if risk_over > 0.0 or risk_under > 0.0:
        conservative_value_side = "over" if risk_over >= risk_under else "under"
    else:
        conservative_value_side = None

    market_input = {
        "source_mode": "caller_supplied_two_way_quote",
        "sportsbook": sportsbook,
        "stat": stat,
        "line": line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "captured_at_utc": captured_at.isoformat(),
    }
    model_config = {
        "model_version": MODEL_VERSION,
        "threshold_model_version": THRESHOLD_MODEL_VERSION,
        "no_vig_method": quote["no_vig_method"],
        "minimum_required_ev": minimum_required_ev,
        "risk_adjusted_ev_method": "minimum_low_base_high_conditional_scenario_ev_no_scenario_weights",
        "market_source_mode": "caller_supplied",
        "sportsbook_quote_cannot_change_basketball_model": True,
    }
    fingerprint_payload = {
        "step_5f_probability_fingerprint_sha256": threshold.get(
            "probability_fingerprint_sha256"
        ),
        "market_input": market_input,
        "model_config": model_config,
        "market_quote_math": quote,
        "conditional_market_results": scenarios,
        "side_summaries": {"over": over_summary, "under": under_summary},
    }
    market_hash = _canonical_hash(fingerprint_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_sportsbook_market_no_vig_edge_and_expected_value",
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "market_analysis_id": f"wnba-5g-{game_id}-{player_id}-{stat}-{market_hash[:16]}",
        "market_analysis_fingerprint_sha256": market_hash,
        "season": threshold.get("season"),
        "season_type": threshold.get("season_type"),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "prop": {
            "stat": stat,
            "line": line,
            "same_threshold_as_step_5f": True,
            "sportsbook_market_does_not_change_projection": True,
        },
        "step_5f_reference": {
            "model_version": threshold.get("model_version"),
            "probability_id": threshold.get("probability_id"),
            "probability_fingerprint_sha256": threshold.get(
                "probability_fingerprint_sha256"
            ),
        },
        "snapshot_reference": deepcopy(threshold.get("snapshot_reference")),
        "market_input": market_input,
        "market_freshness": freshness,
        "sportsbook_quote": quote,
        "conditional_market_results": scenarios,
        "side_summaries": {
            "over": over_summary,
            "under": under_summary,
        },
        "decision_summary": {
            "primary_base_ev_side": primary_value_side,
            "conservative_positive_ev_side": conservative_value_side,
            "base_over_ev_percentage": round(base_over_ev * 100.0, 6),
            "base_under_ev_percentage": round(base_under_ev * 100.0, 6),
            "risk_adjusted_over_ev_percentage": round(risk_over * 100.0, 6),
            "risk_adjusted_under_ev_percentage": round(risk_under * 100.0, 6),
            "no_side_forced_when_both_base_evs_nonpositive": True,
        },
        "model_config": model_config,
        "market_semantics": {
            "sportsbook_quote_is_caller_supplied_not_fetched_or_verified": True,
            "raw_implied_probability_includes_sportsbook_margin": True,
            "no_vig_probability_uses_two_sided_proportional_normalization": True,
            "model_market_edge_uses_resolved_non_push_probabilities": True,
            "ev_uses_raw_win_loss_push_model_probabilities": True,
            "push_returns_stake_and_contributes_zero_net_profit": True,
            "risk_adjusted_ev_is_worst_conditional_scenario_ev_not_a_weighted_forecast": True,
            "minimum_acceptable_price_is_model_derived_not_a_sportsbook_prediction": True,
        },
        "guardrails": {
            "market_enters_only_after_step_5f_probability_is_frozen": True,
            "step_5f_fingerprint_recomputed_before_market_math": True,
            "sportsbook_price_cannot_change_projection_means": True,
            "sportsbook_price_cannot_change_monte_carlo_draws": True,
            "sportsbook_price_cannot_change_step_5f_probability": True,
            "two_sided_prices_required_for_no_vig": True,
            "no_scenario_weights_invented": True,
            "no_value_side_forced_when_base_ev_nonpositive": True,
            "no_kelly_stake_created": True,
            "no_bet_size_created": True,
            "no_named_defender_assignment_inferred": True,
        },
        "verification": {
            "step_5f_model_version_checked": True,
            "step_5f_probability_fingerprint_recomputed": True,
            "step_5f_primary_result_matches_base": True,
            "same_prop_stat_and_line_used_for_market_comparison": True,
            "american_prices_validated": True,
            "two_sided_implied_probabilities_recomputed": True,
            "no_vig_probabilities_sum_to_one": True,
            "all_scenario_evs_recomputed_from_raw_win_loss_push": True,
            "market_capture_timestamp_checked": True,
            "market_analysis_fingerprint_created": True,
        },
    }


def get_player_game_sportsbook_market_edge(
    player_id: int,
    game_id: str,
    season: int,
    *,
    stat: str,
    line: float,
    sportsbook: str,
    over_odds: int,
    under_odds: int,
    market_captured_at_utc: str,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    distribution_last_n_games: int = 10,
    simulation_count: int = DEFAULT_SIMULATION_COUNT,
    batch_size: int = DEFAULT_BATCH_SIZE,
    random_seed: int = DEFAULT_RANDOM_SEED,
    require_current_availability: bool = True,
    max_snapshot_age_minutes: int = DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
    require_convergence: bool = True,
    minimum_required_ev: float = 0.0,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    require_fresh_market: bool = True,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    stat = _stat(stat)
    line = _line(line)
    sportsbook = _sportsbook(sportsbook)
    over_odds = _american_odds(over_odds, "over_odds")
    under_odds = _american_odds(under_odds, "under_odds")
    _parse_market_timestamp(market_captured_at_utc)
    season_type = _choice(season_type, ALLOWED_SEASON_TYPES, "season_type")
    last_n_games = _last_n(last_n_games)
    distribution_last_n_games = _distribution_last_n(distribution_last_n_games)
    simulation_count = _simulation_count(simulation_count)
    batch_size = _batch_size(batch_size)
    random_seed = _random_seed(random_seed)
    require_current_availability = _bool(
        require_current_availability, "require_current_availability"
    )
    max_snapshot_age_minutes = _max_snapshot_age(max_snapshot_age_minutes)
    require_convergence = _bool(require_convergence, "require_convergence")
    minimum_required_ev = _minimum_required_ev(minimum_required_ev)
    max_market_age_minutes = _market_age_limit(max_market_age_minutes)
    require_fresh_market = _bool(require_fresh_market, "require_fresh_market")

    try:
        threshold = get_player_game_prop_threshold_probability(
            player_id,
            game_id,
            season,
            stat=stat,
            line=line,
            season_type=season_type,
            last_n_games=last_n_games,
            distribution_last_n_games=distribution_last_n_games,
            simulation_count=simulation_count,
            batch_size=batch_size,
            random_seed=random_seed,
            require_current_availability=require_current_availability,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            require_convergence=require_convergence,
        )
    except WNBAPropThresholdNotFoundError as exc:
        raise WNBASportsbookMarketNotFoundError(str(exc)) from exc
    except WNBAPropThresholdNotReadyError as exc:
        raise WNBASportsbookMarketNotReadyError(str(exc)) from exc
    except WNBAPropThresholdModelInputError as exc:
        raise WNBASportsbookMarketModelInputError(str(exc)) from exc
    except WNBAPropThresholdUpstreamError as exc:
        raise WNBASportsbookMarketUpstreamError(str(exc)) from exc

    return compare_threshold_to_sportsbook_market(
        threshold,
        sportsbook=sportsbook,
        over_odds=over_odds,
        under_odds=under_odds,
        market_captured_at_utc=market_captured_at_utc,
        minimum_required_ev=minimum_required_ev,
        max_market_age_minutes=max_market_age_minutes,
        require_fresh_market=require_fresh_market,
    )
