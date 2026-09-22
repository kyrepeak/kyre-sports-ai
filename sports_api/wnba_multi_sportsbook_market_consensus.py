"""Step 5H: WNBA multi-sportsbook best-price and market-consensus engine.

Consumes one frozen Step 5F prop-threshold probability result and two or more
caller-supplied same-line two-way sportsbook quotes. Each quote is evaluated
independently through frozen Step 5G market math. Stale quotes are excluded from
best-price/consensus calculations by default but remain visible in the audit
trail.

Sportsbook information remains post-projection market context. It cannot alter
minutes, projection centers, empirical distributions, Monte Carlo draws, or
Step 5F model probabilities.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite, sqrt
from statistics import median
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
from sports_api.wnba_sportsbook_market_edge import (
    DEFAULT_MAX_MARKET_AGE_MINUTES,
    MARKET_FUTURE_TOLERANCE_SECONDS,
    MAX_ABS_AMERICAN_ODDS,
    MAX_MARKET_AGE_MINUTES,
    MAX_MINIMUM_REQUIRED_EV,
    MODEL_VERSION as MARKET_EDGE_MODEL_VERSION,
    WNBASportsbookMarketModelInputError,
    WNBASportsbookMarketNotReadyError,
    WNBASportsbookMarketUpstreamError,
    compare_threshold_to_sportsbook_market,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5H multi-sportsbook market consensus engine"
MODEL_VERSION = "wnba_step_5h_multi_sportsbook_market_consensus_v1"
MODEL_FAMILY = "post_projection_multi_book_best_price_and_consensus"

MIN_SPORTSBOOK_QUOTES = 2
MAX_SPORTSBOOK_QUOTES = 25
SIDES = ("over", "under")
SCENARIO_KEYS = ("low", "base", "high")
MAX_RECENT_GAMES = 20
MIN_DISTRIBUTION_GAMES = 1
MAX_DISTRIBUTION_GAMES = 50


class WNBAMultiSportsbookNotReadyError(RuntimeError):
    pass


class WNBAMultiSportsbookNotFoundError(LookupError):
    pass


class WNBAMultiSportsbookUpstreamError(RuntimeError):
    pass


class WNBAMultiSportsbookModelInputError(RuntimeError):
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
    return " ".join(text.split())


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


def _normalize_quotes(quotes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(quotes, list):
        raise ValueError("WNBA sportsbook quotes must be provided as a list.")
    if not MIN_SPORTSBOOK_QUOTES <= len(quotes) <= MAX_SPORTSBOOK_QUOTES:
        raise ValueError(
            f"WNBA Step 5H requires from {MIN_SPORTSBOOK_QUOTES} through "
            f"{MAX_SPORTSBOOK_QUOTES} sportsbook quotes."
        )
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(quotes):
        if not isinstance(row, dict):
            raise ValueError(f"WNBA sportsbook quote at index {index} must be an object.")
        sportsbook = _sportsbook(row.get("sportsbook"))
        key = sportsbook.casefold()
        if key in seen:
            raise ValueError(
                f"WNBA duplicate sportsbook quote {sportsbook!r} is not allowed; "
                "one book cannot be counted twice in consensus."
            )
        seen.add(key)
        over_odds = _american_odds(row.get("over_odds"), f"quotes[{index}].over_odds")
        under_odds = _american_odds(row.get("under_odds"), f"quotes[{index}].under_odds")
        captured = _parse_market_timestamp(row.get("market_captured_at_utc"))
        normalized.append(
            {
                "sportsbook": sportsbook,
                "sportsbook_key": key,
                "over_odds": over_odds,
                "under_odds": under_odds,
                "market_captured_at_utc": captured.isoformat(),
            }
        )
    normalized.sort(key=lambda item: (item["sportsbook_key"], item["sportsbook"]))
    return normalized


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
            "range": None,
            "population_stddev": None,
        }
    count = len(values)
    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / count
    return {
        "count": count,
        "mean": round(mean, 10),
        "median": round(float(median(values)), 10),
        "minimum": round(min(values), 10),
        "maximum": round(max(values), 10),
        "range": round(max(values) - min(values), 10),
        "population_stddev": round(sqrt(max(0.0, variance)), 10),
    }


def _analysis_identity(analysis: dict[str, Any], threshold: dict[str, Any], quote: dict[str, Any]) -> None:
    if not isinstance(analysis, dict) or analysis.get("model_version") != MARKET_EDGE_MODEL_VERSION:
        raise WNBAMultiSportsbookUpstreamError(
            "Step 5H received an unexpected Step 5G market-analysis payload."
        )
    if analysis.get("step_5f_reference", {}).get("probability_fingerprint_sha256") != threshold.get(
        "probability_fingerprint_sha256"
    ):
        raise WNBAMultiSportsbookUpstreamError(
            "Step 5G market analysis does not reference the frozen Step 5F probability."
        )
    market_input = analysis.get("market_input")
    if not isinstance(market_input, dict):
        raise WNBAMultiSportsbookUpstreamError("Step 5G market input metadata is missing.")
    expected = {
        "sportsbook": quote["sportsbook"],
        "over_odds": quote["over_odds"],
        "under_odds": quote["under_odds"],
        "captured_at_utc": quote["market_captured_at_utc"],
    }
    for key, value in expected.items():
        if market_input.get(key) != value:
            raise WNBAMultiSportsbookUpstreamError(
                f"Step 5G market analysis disagrees with normalized quote on {key}."
            )


def _best_price(analyses: list[dict[str, Any]], side: str) -> dict[str, Any] | None:
    if not analyses:
        return None
    rows = []
    for analysis in analyses:
        quote = analysis.get("sportsbook_quote", {}).get(side, {})
        decimal_odds = _to_float(quote.get("decimal_odds"))
        american_odds = _to_int(quote.get("american_odds"))
        sportsbook = _clean(analysis.get("market_input", {}).get("sportsbook"))
        if decimal_odds is None or american_odds is None or not sportsbook:
            raise WNBAMultiSportsbookUpstreamError(
                f"Step 5G {side} price fields are malformed."
            )
        rows.append(
            {
                "sportsbook": sportsbook,
                "american_odds": american_odds,
                "decimal_odds": decimal_odds,
                "market_captured_at_utc": analysis["market_input"]["captured_at_utc"],
            }
        )
    best_decimal = max(row["decimal_odds"] for row in rows)
    winners = [row for row in rows if abs(row["decimal_odds"] - best_decimal) <= 1e-12]
    winners.sort(key=lambda row: row["sportsbook"].casefold())
    return {
        "side": side,
        "best_decimal_odds": round(best_decimal, 8),
        "best_american_odds": winners[0]["american_odds"],
        "sportsbooks": winners,
        "tie_count": len(winners),
        "eligible_quote_count": len(rows),
        "selection_rule": "highest_decimal_payout_for_same_stat_and_line",
    }


def _rankings(analyses: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
    rows = []
    for analysis in analyses:
        sportsbook = analysis["market_input"]["sportsbook"]
        quote = analysis["sportsbook_quote"][side]
        summary = analysis["side_summaries"][side]
        rows.append(
            {
                "sportsbook": sportsbook,
                "american_odds": quote["american_odds"],
                "decimal_odds": quote["decimal_odds"],
                "base_ev_per_unit": summary["base_ev_per_unit"],
                "base_ev_percentage": summary["base_ev_percentage"],
                "risk_adjusted_ev_per_unit": summary["risk_adjusted_ev_per_unit"],
                "risk_adjusted_ev_percentage": summary["risk_adjusted_ev_percentage"],
                "base_no_vig_edge_probability": summary["base"]["edge"][
                    "vs_no_vig_market_probability"
                ],
                "base_no_vig_edge_percentage_points": summary["base"]["edge"][
                    "vs_no_vig_market_percentage_points"
                ],
                "positive_ev_in_base": summary["positive_ev_in_base"],
                "positive_ev_in_all_conditional_scenarios": summary[
                    "positive_ev_in_all_conditional_scenarios"
                ],
                "meets_base_minimum_required_ev": summary["price_thresholds"][
                    "offered_price_meets_base_minimum_required_ev"
                ],
                "meets_minimum_required_ev_in_all_scenarios": summary["price_thresholds"][
                    "offered_price_meets_minimum_required_ev_in_all_scenarios"
                ],
                "market_captured_at_utc": analysis["market_input"]["captured_at_utc"],
            }
        )
    rows.sort(
        key=lambda row: (
            -row["base_ev_per_unit"],
            -row["risk_adjusted_ev_per_unit"],
            -row["decimal_odds"],
            row["sportsbook"].casefold(),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["base_ev_rank"] = index
    risk_sorted = sorted(
        rows,
        key=lambda row: (
            -row["risk_adjusted_ev_per_unit"],
            -row["base_ev_per_unit"],
            -row["decimal_odds"],
            row["sportsbook"].casefold(),
        ),
    )
    risk_rank = {row["sportsbook"].casefold(): index for index, row in enumerate(risk_sorted, start=1)}
    for row in rows:
        row["risk_adjusted_ev_rank"] = risk_rank[row["sportsbook"].casefold()]
    return rows


def _playable_books(rankings: list[dict[str, Any]]) -> dict[str, Any]:
    base = [
        {
            "sportsbook": row["sportsbook"],
            "american_odds": row["american_odds"],
            "decimal_odds": row["decimal_odds"],
            "base_ev_percentage": row["base_ev_percentage"],
        }
        for row in rankings
        if row["meets_base_minimum_required_ev"]
    ]
    conservative = [
        {
            "sportsbook": row["sportsbook"],
            "american_odds": row["american_odds"],
            "decimal_odds": row["decimal_odds"],
            "risk_adjusted_ev_percentage": row["risk_adjusted_ev_percentage"],
        }
        for row in rankings
        if row["meets_minimum_required_ev_in_all_scenarios"]
    ]
    return {
        "base_scenario": base,
        "all_conditional_scenarios": conservative,
        "base_count": len(base),
        "all_scenarios_count": len(conservative),
    }


def _consensus(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    if not analyses:
        raise WNBAMultiSportsbookNotReadyError(
            "Step 5H has no eligible sportsbook quotes after freshness filtering."
        )
    raw_over = []
    raw_under = []
    no_vig_over = []
    no_vig_under = []
    margins = []
    capture_times = []
    books = []
    for analysis in analyses:
        quote = analysis["sportsbook_quote"]
        raw_over.append(float(quote["over"]["raw_implied_probability"]))
        raw_under.append(float(quote["under"]["raw_implied_probability"]))
        no_vig_over.append(float(quote["over"]["no_vig_probability"]))
        no_vig_under.append(float(quote["under"]["no_vig_probability"]))
        margins.append(float(quote["sportsbook_margin_probability"]))
        capture_times.append(_parse_market_timestamp(analysis["market_input"]["captured_at_utc"]))
        books.append(analysis["market_input"]["sportsbook"])
    book_count = len(analyses)
    capture_span = (
        (max(capture_times) - min(capture_times)).total_seconds()
        if len(capture_times) > 1
        else 0.0
    )
    over_mean = sum(no_vig_over) / book_count
    under_mean = sum(no_vig_under) / book_count
    multi_available = book_count >= 2
    return {
        "available": multi_available,
        "eligible_book_count": book_count,
        "sportsbooks": books,
        "reason_if_unavailable": (
            None
            if multi_available
            else "At least two eligible books are required for a true multi-book consensus."
        ),
        "method": "equal_weight_one_book_one_vote_average_of_each_books_two_way_market",
        "book_weighting": "equal_unweighted",
        "raw_implied_probability": {
            "over": _summary(raw_over),
            "under": _summary(raw_under),
            "average_two_sided_sum": round(
                (sum(raw_over) + sum(raw_under)) / book_count, 10
            ),
        },
        "no_vig_probability": {
            "over": _summary(no_vig_over),
            "under": _summary(no_vig_under),
            "consensus_over": round(over_mean, 10),
            "consensus_under": round(under_mean, 10),
            "consensus_sum": round(over_mean + under_mean, 10),
            "over_dispersion_percentage_points": {
                "range": round((max(no_vig_over) - min(no_vig_over)) * 100.0, 6),
                "population_stddev": round(_summary(no_vig_over)["population_stddev"] * 100.0, 6),
            },
        },
        "sportsbook_margin": {
            "probability": _summary(margins),
            "percentage": {
                key: (
                    round(value * 100.0, 6)
                    if isinstance(value, (int, float)) and key != "count"
                    else value
                )
                for key, value in _summary(margins).items()
            },
        },
        "quote_capture_span": {
            "earliest_captured_at_utc": min(capture_times).isoformat(),
            "latest_captured_at_utc": max(capture_times).isoformat(),
            "span_seconds": round(capture_span, 3),
            "span_minutes": round(capture_span / 60.0, 6),
        },
    }


def _market_vs_model(threshold: dict[str, Any], consensus: dict[str, Any]) -> dict[str, Any]:
    primary = threshold.get("primary_result")
    if not isinstance(primary, dict):
        raise WNBAMultiSportsbookUpstreamError("Step 5F primary BASE result is missing.")
    fair = primary.get("fair_odds")
    if not isinstance(fair, dict):
        raise WNBAMultiSportsbookUpstreamError("Step 5F BASE fair-odds object is missing.")
    model = {}
    for side in SIDES:
        row = fair.get(side)
        if not isinstance(row, dict) or row.get("available") is not True:
            raise WNBAMultiSportsbookNotReadyError(
                f"Step 5F BASE fair {side} probability is unavailable."
            )
        probability = _to_float(row.get("fair_probability"))
        if probability is None:
            raise WNBAMultiSportsbookUpstreamError(
                f"Step 5F BASE fair {side} probability is invalid."
            )
        model[side] = probability
    market_over = consensus["no_vig_probability"]["consensus_over"]
    market_under = consensus["no_vig_probability"]["consensus_under"]
    return {
        "model_base_resolved_fair_probability": {
            "over": round(model["over"], 10),
            "under": round(model["under"], 10),
        },
        "consensus_no_vig_probability": {
            "over": market_over,
            "under": market_under,
        },
        "model_edge_vs_consensus_no_vig": {
            "over_probability": round(model["over"] - market_over, 10),
            "under_probability": round(model["under"] - market_under, 10),
            "over_percentage_points": round((model["over"] - market_over) * 100.0, 6),
            "under_percentage_points": round((model["under"] - market_under) * 100.0, 6),
        },
        "model_favored_side": (
            "balanced"
            if abs(model["over"] - model["under"]) < 1e-12
            else ("over" if model["over"] > model["under"] else "under")
        ),
        "market_consensus_favored_side": (
            "balanced"
            if abs(market_over - market_under) < 1e-12
            else ("over" if market_over > market_under else "under")
        ),
    }


def _best_overall(rankings_by_side: dict[str, list[dict[str, Any]]], field: str) -> dict[str, Any] | None:
    candidates = []
    for side, rows in rankings_by_side.items():
        for row in rows:
            candidates.append({**row, "side": side})
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (
            -row[field],
            -row["decimal_odds"],
            row["sportsbook"].casefold(),
            row["side"],
        )
    )
    best = candidates[0]
    if best[field] <= 0.0:
        return None
    return deepcopy(best)


def build_multi_sportsbook_market_consensus(
    threshold: dict[str, Any],
    quotes: list[dict[str, Any]],
    *,
    minimum_required_ev: float = 0.0,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    normalized_quotes = _normalize_quotes(quotes)
    minimum_required_ev = _minimum_required_ev(minimum_required_ev)
    max_market_age_minutes = _market_age_limit(max_market_age_minutes)
    exclude_stale_quotes = _bool(exclude_stale_quotes, "exclude_stale_quotes")
    evaluated = evaluated_at or _utc_now()
    if evaluated.tzinfo is None or evaluated.utcoffset() is None:
        raise ValueError("WNBA evaluated_at must be timezone-aware.")
    evaluated = evaluated.astimezone(timezone.utc)

    eligible = []
    excluded = []
    for quote in normalized_quotes:
        try:
            analysis = compare_threshold_to_sportsbook_market(
                threshold,
                sportsbook=quote["sportsbook"],
                over_odds=quote["over_odds"],
                under_odds=quote["under_odds"],
                market_captured_at_utc=quote["market_captured_at_utc"],
                minimum_required_ev=minimum_required_ev,
                max_market_age_minutes=max_market_age_minutes,
                require_fresh_market=False,
                evaluated_at=evaluated,
            )
        except WNBASportsbookMarketNotReadyError as exc:
            raise WNBAMultiSportsbookNotReadyError(str(exc)) from exc
        except WNBASportsbookMarketModelInputError as exc:
            raise WNBAMultiSportsbookModelInputError(str(exc)) from exc
        except WNBASportsbookMarketUpstreamError as exc:
            raise WNBAMultiSportsbookUpstreamError(str(exc)) from exc

        _analysis_identity(analysis, threshold, quote)
        stale = analysis.get("market_freshness", {}).get("stale") is True
        audit_row = {
            "sportsbook": quote["sportsbook"],
            "sportsbook_key": quote["sportsbook_key"],
            "market_analysis_id": analysis.get("market_analysis_id"),
            "market_analysis_fingerprint_sha256": analysis.get(
                "market_analysis_fingerprint_sha256"
            ),
            "market_captured_at_utc": quote["market_captured_at_utc"],
            "over_odds": quote["over_odds"],
            "under_odds": quote["under_odds"],
            "freshness": deepcopy(analysis.get("market_freshness")),
        }
        if stale and exclude_stale_quotes:
            excluded.append(
                {
                    **audit_row,
                    "eligible": False,
                    "exclusion_reason": "stale_market_quote",
                }
            )
        else:
            eligible.append(analysis)

    if not eligible:
        raise WNBAMultiSportsbookNotReadyError(
            "Step 5H has no eligible sportsbook quotes after stale-quote filtering."
        )

    consensus = _consensus(eligible)
    best_prices = {side: _best_price(eligible, side) for side in SIDES}
    rankings_by_side = {side: _rankings(eligible, side) for side in SIDES}
    playable = {side: _playable_books(rankings_by_side[side]) for side in SIDES}
    model_market = _market_vs_model(threshold, consensus)
    best_base = _best_overall(rankings_by_side, "base_ev_per_unit")
    best_risk = _best_overall(rankings_by_side, "risk_adjusted_ev_per_unit")

    eligible_audit = []
    for analysis in eligible:
        eligible_audit.append(
            {
                "sportsbook": analysis["market_input"]["sportsbook"],
                "sportsbook_key": analysis["market_input"]["sportsbook"].casefold(),
                "market_analysis_id": analysis.get("market_analysis_id"),
                "market_analysis_fingerprint_sha256": analysis.get(
                    "market_analysis_fingerprint_sha256"
                ),
                "market_captured_at_utc": analysis["market_input"]["captured_at_utc"],
                "over_odds": analysis["market_input"]["over_odds"],
                "under_odds": analysis["market_input"]["under_odds"],
                "freshness": deepcopy(analysis.get("market_freshness")),
                "eligible": True,
                "exclusion_reason": None,
            }
        )
    quote_audit = sorted(eligible_audit + excluded, key=lambda row: row["sportsbook_key"])

    first = eligible[0]
    player_id = _to_int(first.get("player_id"))
    game_id = _clean(first.get("game_id"))
    team_key = _clean(first.get("team_key"))
    opponent_key = _clean(first.get("opponent_team_key"))
    prop = first.get("prop")
    if (
        player_id is None
        or not game_id
        or not team_key
        or not opponent_key
        or not isinstance(prop, dict)
    ):
        raise WNBAMultiSportsbookUpstreamError("Step 5G identity fields are malformed.")
    for analysis in eligible[1:]:
        if (
            _to_int(analysis.get("player_id")) != player_id
            or _clean(analysis.get("game_id")) != game_id
            or _clean(analysis.get("team_key")) != team_key
            or _clean(analysis.get("opponent_team_key")) != opponent_key
            or analysis.get("prop") != prop
        ):
            raise WNBAMultiSportsbookUpstreamError(
                "Eligible Step 5G analyses disagree on player/game/team/prop identity."
            )

    model_config = {
        "model_version": MODEL_VERSION,
        "threshold_model_version": THRESHOLD_MODEL_VERSION,
        "market_edge_model_version": MARKET_EDGE_MODEL_VERSION,
        "minimum_required_ev": minimum_required_ev,
        "max_market_age_minutes": max_market_age_minutes,
        "exclude_stale_quotes": exclude_stale_quotes,
        "consensus_method": "equal_weight_average_of_per_book_two_way_no_vig_probabilities",
        "book_weighting": "equal_unweighted",
        "minimum_input_books": MIN_SPORTSBOOK_QUOTES,
        "scenario_weights": None,
        "sportsbook_market_cannot_change_basketball_model": True,
    }
    fingerprint_quotes = [
        {
            "sportsbook": row["sportsbook"],
            "sportsbook_key": row["sportsbook_key"],
            "over_odds": row["over_odds"],
            "under_odds": row["under_odds"],
            "market_captured_at_utc": row["market_captured_at_utc"],
            "eligible": row["eligible"],
            "exclusion_reason": row["exclusion_reason"],
            "market_analysis_fingerprint_sha256": row[
                "market_analysis_fingerprint_sha256"
            ],
        }
        for row in quote_audit
    ]
    fingerprint_payload = {
        "step_5f_probability_fingerprint_sha256": threshold.get(
            "probability_fingerprint_sha256"
        ),
        "quotes": fingerprint_quotes,
        "model_config": model_config,
        "consensus": consensus,
        "best_prices": best_prices,
        "rankings_by_side": rankings_by_side,
        "playable_books": playable,
        "model_vs_consensus": model_market,
        "best_positive_base_ev_quote": best_base,
        "best_positive_risk_adjusted_ev_quote": best_risk,
    }
    result_hash = _canonical_hash(fingerprint_payload)

    stale_count = sum(1 for row in quote_audit if row["freshness"].get("stale") is True)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_multi_sportsbook_best_price_market_consensus_and_ev",
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "market_consensus_id": f"wnba-5h-{game_id}-{player_id}-{prop.get('stat')}-{result_hash[:16]}",
        "market_consensus_fingerprint_sha256": result_hash,
        "season": threshold.get("season"),
        "season_type": threshold.get("season_type"),
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "prop": deepcopy(prop),
        "step_5f_reference": {
            "model_version": threshold.get("model_version"),
            "probability_id": threshold.get("probability_id"),
            "probability_fingerprint_sha256": threshold.get(
                "probability_fingerprint_sha256"
            ),
        },
        "snapshot_reference": deepcopy(threshold.get("snapshot_reference")),
        "quote_set": {
            "input_quote_count": len(normalized_quotes),
            "eligible_quote_count": len(eligible),
            "excluded_quote_count": len(excluded),
            "stale_quote_count": stale_count,
            "exclude_stale_quotes": exclude_stale_quotes,
            "max_market_age_minutes": max_market_age_minutes,
            "evaluated_at_utc": evaluated.isoformat(),
            "quotes": quote_audit,
        },
        "consensus": consensus,
        "model_vs_market_consensus": model_market,
        "best_prices": best_prices,
        "ev_rankings": rankings_by_side,
        "playable_books": playable,
        "decision_summary": {
            "best_positive_base_ev_quote": best_base,
            "best_positive_risk_adjusted_ev_quote": best_risk,
            "no_base_value_quote_forced_when_all_nonpositive": best_base is None,
            "no_risk_adjusted_value_quote_forced_when_all_nonpositive": best_risk is None,
            "multi_book_consensus_available": consensus["available"],
        },
        "model_config": model_config,
        "market_semantics": {
            "all_quotes_are_caller_supplied_not_fetched_or_verified": True,
            "best_price_uses_highest_decimal_payout_at_same_stat_and_line": True,
            "consensus_raw_probability_still_contains_each_books_margin": True,
            "consensus_no_vig_probability_averages_each_books_two_way_no_vig_probability": True,
            "each_eligible_book_has_equal_weight": True,
            "no_handle_or_liquidity_weighting_invented": True,
            "stale_quotes_are_excluded_by_default": True,
            "market_consensus_is_context_not_a_basketball_model_input": True,
            "risk_adjusted_ev_remains_worst_low_base_high_conditional_ev": True,
        },
        "guardrails": {
            "market_enters_only_after_step_5f_probability_is_frozen": True,
            "step_5g_math_applied_independently_to_each_book": True,
            "one_step_5f_probability_shared_across_all_books": True,
            "duplicate_sportsbook_quotes_rejected": True,
            "two_sided_prices_required_for_every_book": True,
            "stale_quote_exclusion_is_explicit": True,
            "no_book_can_change_projection_means": True,
            "no_book_can_change_monte_carlo_draws": True,
            "no_book_can_change_step_5f_probability": True,
            "no_scenario_weights_invented": True,
            "no_forced_bet_or_value_side": True,
            "no_kelly_stake_created": True,
            "no_bet_size_created": True,
            "no_named_defender_assignment_inferred": True,
        },
        "verification": {
            "minimum_two_distinct_input_books_checked": True,
            "all_book_names_deduplicated_case_insensitively": True,
            "all_market_timestamps_timezone_aware": True,
            "all_step_5g_analyses_reference_same_step_5f_fingerprint": True,
            "all_eligible_books_share_same_player_game_team_prop_identity": True,
            "all_no_vig_probabilities_recomputed_by_step_5g": True,
            "best_price_selected_from_eligible_quotes_only": True,
            "consensus_created_from_eligible_quotes_only": True,
            "market_consensus_fingerprint_created": True,
        },
    }


def get_player_game_multi_sportsbook_market_consensus(
    player_id: int,
    game_id: str,
    season: int,
    *,
    stat: str,
    line: float,
    quotes: list[dict[str, Any]],
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
    exclude_stale_quotes: bool = True,
) -> dict[str, Any]:
    player_id = _positive_player_id(player_id)
    game_id = _game_id(game_id)
    stat = _stat(stat)
    line = _line(line)
    normalized_quotes = _normalize_quotes(quotes)
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
    exclude_stale_quotes = _bool(exclude_stale_quotes, "exclude_stale_quotes")

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
        raise WNBAMultiSportsbookNotFoundError(str(exc)) from exc
    except WNBAPropThresholdNotReadyError as exc:
        raise WNBAMultiSportsbookNotReadyError(str(exc)) from exc
    except WNBAPropThresholdModelInputError as exc:
        raise WNBAMultiSportsbookModelInputError(str(exc)) from exc
    except WNBAPropThresholdUpstreamError as exc:
        raise WNBAMultiSportsbookUpstreamError(str(exc)) from exc

    return build_multi_sportsbook_market_consensus(
        threshold,
        normalized_quotes,
        minimum_required_ev=minimum_required_ev,
        max_market_age_minutes=max_market_age_minutes,
        exclude_stale_quotes=exclude_stale_quotes,
    )
