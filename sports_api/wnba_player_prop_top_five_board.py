"""WNBA Step 5K: deterministic Top-5 player-prop qualification and ranking board.

Step 5K is a decision-layer consumer of frozen Step 5F probabilities, optional
Step 5H market context, and optional Step 5I historical calibration evidence.
It does not alter the basketball projection, Monte Carlo draws, Step 5F
probabilities, or historical calibration outputs.

The primary board is deliberately model-first: candidates are ranked by their
frozen resolved non-push probability with deterministic scenario-stability
and numerical-readiness qualification gates. Market value is reported on a
separate board and cannot move a candidate on the pure-probability board.
Historical calibration is evidence metadata only unless the caller explicitly
requires mature calibration as a qualification gate; it never rescales a
current probability in Step 5K.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from typing import Any

from sports_api.wnba_historical_backtest_calibration import (
    CALIBRATION_SCHEMA_VERSION,
    MODEL_VERSION as BACKTEST_CALIBRATION_MODEL_VERSION,
)
from sports_api.wnba_multi_sportsbook_market_consensus import (
    MODEL_VERSION as MARKET_CONSENSUS_MODEL_VERSION,
)
from sports_api.wnba_prop_threshold_probability import (
    MODEL_VERSION as THRESHOLD_MODEL_VERSION,
    SUPPORTED_STATS,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5K Top-5 player-prop qualification and ranking engine"
MODEL_VERSION = "wnba_step_5k_player_prop_top_five_board_v1"
BOARD_SCHEMA_VERSION = "wnba_step_5k_top_five_board_v1"
MODEL_FAMILY = "post_probability_deterministic_rank_and_qualification"

SCENARIOS = ("low", "base", "high")
SIDES = ("over", "under")
MIN_CANDIDATES = 1
MAX_CANDIDATES = 500
MIN_TOP_N = 1
MAX_TOP_N = 10
DEFAULT_TOP_N = 5
DEFAULT_MINIMUM_BASE_PROBABILITY = 0.55
DEFAULT_MINIMUM_WORST_SCENARIO_PROBABILITY = 0.50
DEFAULT_MAXIMUM_SCENARIO_SPAN_PERCENTAGE_POINTS = 20.0


class WNBAPlayerPropBoardNotReadyError(RuntimeError):
    pass


class WNBAPlayerPropBoardUpstreamError(RuntimeError):
    pass


class WNBAPlayerPropBoardModelInputError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    try:
        return None if _clean(value) is None else int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        result = float(str(value))
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def _hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha(value: Any) -> bool:
    text = _clean(value)
    return bool(
        text
        and len(text) == 64
        and all(character in "0123456789abcdefABCDEF" for character in text)
    )


def _bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"WNBA Step 5K {label} must be boolean.")
    return value


def _top_n(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not MIN_TOP_N <= value <= MAX_TOP_N:
        raise ValueError(f"WNBA Step 5K top_n must be an integer from {MIN_TOP_N} through {MAX_TOP_N}.")
    return value


def _probability(value: float, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA Step 5K {label} must be a probability from 0 through 1.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"WNBA Step 5K {label} must be a probability from 0 through 1.") from exc
    if not isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"WNBA Step 5K {label} must be a probability from 0 through 1.")
    return round(number, 10)


def _percentage_points(value: float, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA Step 5K {label} must be a number from 0 through 100.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"WNBA Step 5K {label} must be a number from 0 through 100.") from exc
    if not isfinite(number) or not 0.0 <= number <= 100.0:
        raise ValueError(f"WNBA Step 5K {label} must be a number from 0 through 100.")
    return round(number, 6)


def _verify_threshold(threshold: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(threshold, dict):
        raise WNBAPlayerPropBoardModelInputError("Each Step 5K candidate threshold must be an object.")
    if threshold.get("model_version") != THRESHOLD_MODEL_VERSION:
        raise WNBAPlayerPropBoardUpstreamError("Step 5K received an unexpected Step 5F model version.")

    player_id = _int(threshold.get("player_id"))
    game_id = _clean(threshold.get("game_id"))
    team_key = _clean(threshold.get("team_key"))
    opponent_key = _clean(threshold.get("opponent_team_key"))
    prop = threshold.get("prop")
    if player_id is None or player_id <= 0 or not game_id or not team_key or not opponent_key or not isinstance(prop, dict):
        raise WNBAPlayerPropBoardUpstreamError("Step 5F identity fields are malformed.")
    stat = _clean(prop.get("stat"))
    line = _float(prop.get("line"))
    if stat not in SUPPORTED_STATS or line is None or line < 0:
        raise WNBAPlayerPropBoardUpstreamError("Step 5F prop identity is malformed.")

    reference = threshold.get("step_5e_reference")
    config = threshold.get("model_config")
    results = threshold.get("conditional_scenario_results")
    sensitivity = threshold.get("scenario_sensitivity")
    if not all(isinstance(value, dict) for value in (reference, config, results, sensitivity)):
        raise WNBAPlayerPropBoardUpstreamError("Step 5F fingerprint fields are missing.")
    simulation_fingerprint = reference.get("simulation_fingerprint_sha256")
    probability_fingerprint = threshold.get("probability_fingerprint_sha256")
    expected_fingerprint = _hash(
        {
            "step_5e_simulation_fingerprint_sha256": simulation_fingerprint,
            "model_config": config,
            "conditional_threshold_results": results,
            "scenario_sensitivity": sensitivity,
        }
    )
    if (
        not _sha(simulation_fingerprint)
        or not _sha(probability_fingerprint)
        or expected_fingerprint != probability_fingerprint
    ):
        raise WNBAPlayerPropBoardUpstreamError("Step 5F probability fingerprint integrity check failed.")

    scenario_probabilities: dict[str, dict[str, float]] = {}
    scenario_pushes: dict[str, float] = {}
    scenario_means: dict[str, float] = {}
    scenario_favored: dict[str, str] = {}
    max_probability_mc_se = 0.0
    fair_odds_rows: dict[str, dict[str, Any]] = {}

    for scenario_name in SCENARIOS:
        row = results.get(scenario_name)
        if not isinstance(row, dict) or _clean(row.get("conditional_scenario")) != scenario_name:
            raise WNBAPlayerPropBoardUpstreamError(f"Step 5F {scenario_name} scenario is missing.")
        if _clean(row.get("stat")) != stat or _float(row.get("line")) != line:
            raise WNBAPlayerPropBoardUpstreamError(f"Step 5F {scenario_name} prop identity mismatch.")
        fair = row.get("fair_odds")
        raw = row.get("raw_probabilities")
        summary = row.get("source_distribution_summary")
        precision = row.get("threshold_precision")
        if not all(isinstance(value, dict) for value in (fair, raw, summary, precision)):
            raise WNBAPlayerPropBoardUpstreamError(f"Step 5F {scenario_name} probability metadata is missing.")
        side_probabilities: dict[str, float] = {}
        for side in SIDES:
            fair_side = fair.get(side)
            if not isinstance(fair_side, dict) or fair_side.get("available") is not True:
                raise WNBAPlayerPropBoardNotReadyError(
                    f"Step 5F {scenario_name} fair {side} probability is unavailable."
                )
            probability = _float(fair_side.get("fair_probability"))
            if probability is None or not 0.0 <= probability <= 1.0:
                raise WNBAPlayerPropBoardUpstreamError(
                    f"Step 5F {scenario_name} fair {side} probability is invalid."
                )
            side_probabilities[side] = float(probability)
        if abs(sum(side_probabilities.values()) - 1.0) > 1e-8:
            raise WNBAPlayerPropBoardUpstreamError(
                f"Step 5F {scenario_name} resolved fair probabilities do not sum to one."
            )
        push = _float((raw.get("push") or {}).get("probability"))
        mean = _float(summary.get("mean"))
        mc_se = _float(precision.get("maximum_probability_mc_standard_error"))
        if push is None or not 0.0 <= push <= 1.0 or mean is None or mean < 0 or mc_se is None or mc_se < 0:
            raise WNBAPlayerPropBoardUpstreamError(
                f"Step 5F {scenario_name} distribution/precision fields are invalid."
            )
        scenario_probabilities[scenario_name] = side_probabilities
        scenario_pushes[scenario_name] = float(push)
        scenario_means[scenario_name] = float(mean)
        max_probability_mc_se = max(max_probability_mc_se, float(mc_se))
        over_probability = side_probabilities["over"]
        under_probability = side_probabilities["under"]
        scenario_favored[scenario_name] = (
            "balanced"
            if abs(over_probability - under_probability) < 1e-12
            else ("over" if over_probability > under_probability else "under")
        )
        if scenario_name == "base":
            fair_odds_rows = {side: deepcopy(fair[side]) for side in SIDES}

    base_over = scenario_probabilities["base"]["over"]
    base_under = scenario_probabilities["base"]["under"]
    selected_side = (
        "balanced"
        if abs(base_over - base_under) < 1e-12
        else ("over" if base_over > base_under else "under")
    )
    numerical = threshold.get("numerical_readiness")
    if not isinstance(numerical, dict):
        raise WNBAPlayerPropBoardUpstreamError("Step 5F numerical readiness metadata is missing.")

    return {
        "player_id": player_id,
        "game_id": game_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "season": threshold.get("season"),
        "season_type": threshold.get("season_type"),
        "stat": stat,
        "line": float(line),
        "probability_id": threshold.get("probability_id"),
        "probability_fingerprint_sha256": probability_fingerprint,
        "snapshot_reference": deepcopy(threshold.get("snapshot_reference")),
        "selected_side": selected_side,
        "scenario_probabilities": scenario_probabilities,
        "scenario_pushes": scenario_pushes,
        "scenario_means": scenario_means,
        "scenario_favored": scenario_favored,
        "same_favored_side_across_all_scenarios": len(set(scenario_favored.values())) == 1,
        "max_probability_mc_standard_error": max_probability_mc_se,
        "strict_numerical_readiness_passed": numerical.get("strict_numerical_readiness_passed") is True,
        "all_fair_odds_available": numerical.get("all_fair_odds_available") is True,
        "fair_odds_base": fair_odds_rows,
    }


def _verify_calibration_report(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if report is None:
        return None
    if not isinstance(report, dict):
        raise WNBAPlayerPropBoardModelInputError("Step 5K calibration_report must be an object when supplied.")
    if report.get("model_version") != BACKTEST_CALIBRATION_MODEL_VERSION or report.get("schema_version") != CALIBRATION_SCHEMA_VERSION:
        raise WNBAPlayerPropBoardUpstreamError("Step 5K received an unexpected Step 5I calibration report version.")
    observation_hashes = report.get("observation_hashes")
    versions = report.get("probability_model_versions")
    config = report.get("model_config")
    reports = report.get("reports_by_probability_model_version")
    fingerprint = report.get("calibration_report_fingerprint_sha256")
    if not isinstance(observation_hashes, list) or not isinstance(versions, list) or not isinstance(config, dict) or not isinstance(reports, dict):
        raise WNBAPlayerPropBoardUpstreamError("Step 5I calibration fingerprint fields are missing.")
    expected = _hash(
        {
            "observation_hashes": sorted(observation_hashes),
            "probability_model_versions": versions,
            "model_config": config,
            "reports_by_probability_model_version": reports,
        }
    )
    if not _sha(fingerprint) or expected != fingerprint:
        raise WNBAPlayerPropBoardUpstreamError("Step 5I calibration report fingerprint integrity check failed.")
    return report


def _calibration_context(report: dict[str, Any] | None, *, model_version: str, stat: str) -> dict[str, Any]:
    if report is None:
        return {
            "available": False,
            "mature": False,
            "reason": "no_calibration_report_supplied",
            "probability_model_version": model_version,
            "does_not_modify_current_probability": True,
        }
    reports = report["reports_by_probability_model_version"]
    version_report = reports.get(model_version)
    if not isinstance(version_report, dict):
        return {
            "available": False,
            "mature": False,
            "reason": "no_matching_probability_model_version_in_calibration_report",
            "probability_model_version": model_version,
            "calibration_report_id": report.get("calibration_report_id"),
            "does_not_modify_current_probability": True,
        }
    probability = version_report.get("probability") or {}
    calibration = probability.get("calibration") or {}
    stat_slice = (version_report.get("by_stat") or {}).get(stat)
    mature = probability.get("calibration_claim_ready") is True
    return {
        "available": True,
        "mature": mature,
        "reason": None if mature else "calibration_sample_below_maturity_threshold",
        "calibration_report_id": report.get("calibration_report_id"),
        "calibration_report_fingerprint_sha256": report.get("calibration_report_fingerprint_sha256"),
        "probability_model_version": model_version,
        "overall": {
            "total_observation_count": probability.get("total_observation_count"),
            "resolved_observation_count": probability.get("resolved_observation_count"),
            "minimum_resolved_for_calibration_claim": probability.get("minimum_resolved_for_calibration_claim"),
            "calibration_claim_ready": probability.get("calibration_claim_ready"),
            "brier_score": probability.get("brier_score"),
            "log_loss": probability.get("log_loss"),
            "favored_side_hit_rate": probability.get("favored_side_hit_rate"),
            "expected_calibration_error": calibration.get("expected_calibration_error"),
            "maximum_calibration_error": calibration.get("maximum_calibration_error"),
        },
        "stat_slice": deepcopy(stat_slice) if isinstance(stat_slice, dict) else None,
        "does_not_modify_current_probability": True,
    }


def _verify_market_consensus(consensus: dict[str, Any] | None, threshold: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    if consensus is None:
        return {"available": False, "reason": "no_step_5h_market_consensus_supplied"}
    if not isinstance(consensus, dict):
        raise WNBAPlayerPropBoardModelInputError("Step 5K market_consensus must be an object when supplied.")
    if consensus.get("model_version") != MARKET_CONSENSUS_MODEL_VERSION:
        raise WNBAPlayerPropBoardUpstreamError("Step 5K received an unexpected Step 5H model version.")
    reference = consensus.get("step_5f_reference")
    if not isinstance(reference, dict) or reference.get("probability_fingerprint_sha256") != identity["probability_fingerprint_sha256"]:
        raise WNBAPlayerPropBoardUpstreamError("Step 5H does not reference the candidate Step 5F fingerprint.")
    prop = consensus.get("prop")
    expected_identity = {
        "player_id": identity["player_id"],
        "game_id": identity["game_id"],
        "team_key": identity["team_key"],
        "opponent_team_key": identity["opponent_team_key"],
    }
    for key, expected in expected_identity.items():
        actual = _int(consensus.get(key)) if key == "player_id" else _clean(consensus.get(key))
        if actual != expected:
            raise WNBAPlayerPropBoardUpstreamError(f"Step 5H identity mismatch on {key}.")
    if not isinstance(prop, dict) or _clean(prop.get("stat")) != identity["stat"] or _float(prop.get("line")) != identity["line"]:
        raise WNBAPlayerPropBoardUpstreamError("Step 5H prop identity mismatch.")

    model_market = consensus.get("model_vs_market_consensus") or {}
    model_probabilities = model_market.get("model_base_resolved_fair_probability") or {}
    for side in SIDES:
        expected_probability = identity["scenario_probabilities"]["base"][side]
        actual_probability = _float(model_probabilities.get(side))
        if actual_probability is None or abs(actual_probability - expected_probability) > 1e-8:
            raise WNBAPlayerPropBoardUpstreamError(
                f"Step 5H BASE {side} model probability disagrees with frozen Step 5F."
            )

    quote_set = consensus.get("quote_set") or {}
    consensus_summary = consensus.get("consensus") or {}
    true_multi_book = consensus_summary.get("available") is True
    selected_side = identity["selected_side"]
    if selected_side not in SIDES:
        return {
            "available": true_multi_book,
            "reason": "base_model_side_is_balanced",
            "market_consensus_id": consensus.get("market_consensus_id"),
        }

    rankings = (consensus.get("ev_rankings") or {}).get(selected_side)
    best_price = (consensus.get("best_prices") or {}).get(selected_side)
    if rankings is None:
        rankings = []
    if not isinstance(rankings, list):
        raise WNBAPlayerPropBoardUpstreamError("Step 5H selected-side EV rankings are malformed.")
    risk_rows = []
    for row in rankings:
        if not isinstance(row, dict):
            raise WNBAPlayerPropBoardUpstreamError("Step 5H EV ranking row is malformed.")
        risk = _float(row.get("risk_adjusted_ev_per_unit"))
        base_ev = _float(row.get("base_ev_per_unit"))
        decimal_odds = _float(row.get("decimal_odds"))
        sportsbook = _clean(row.get("sportsbook"))
        if risk is None or base_ev is None or decimal_odds is None or not sportsbook:
            raise WNBAPlayerPropBoardUpstreamError("Step 5H selected-side EV fields are malformed.")
        risk_rows.append(row)
    risk_rows.sort(
        key=lambda row: (
            -float(row["risk_adjusted_ev_per_unit"]),
            -float(row["base_ev_per_unit"]),
            -float(row["decimal_odds"]),
            str(row["sportsbook"]).casefold(),
        )
    )
    best_risk = deepcopy(risk_rows[0]) if risk_rows else None
    market_probability = _float(
        (consensus_summary.get("no_vig_probability") or {}).get(
            "consensus_over" if selected_side == "over" else "consensus_under"
        )
    )
    edge = _float(
        (model_market.get("model_edge_vs_consensus_no_vig") or {}).get(
            f"{selected_side}_probability"
        )
    )
    return {
        "available": true_multi_book,
        "reason": None if true_multi_book else "true_multi_book_consensus_unavailable",
        "market_consensus_id": consensus.get("market_consensus_id"),
        "market_consensus_fingerprint_sha256": consensus.get("market_consensus_fingerprint_sha256"),
        "eligible_quote_count": quote_set.get("eligible_quote_count"),
        "excluded_quote_count": quote_set.get("excluded_quote_count"),
        "stale_quote_count": quote_set.get("stale_quote_count"),
        "selected_side": selected_side,
        "consensus_no_vig_probability_selected_side": market_probability,
        "model_edge_vs_consensus_no_vig_probability": edge,
        "best_price_selected_side": deepcopy(best_price) if isinstance(best_price, dict) else None,
        "best_risk_adjusted_ev_quote_selected_side": best_risk,
        "market_cannot_modify_probability_board_rank": True,
    }


def _display_label(candidate: dict[str, Any]) -> str | None:
    value = _clean(candidate.get("player_name"))
    if value and len(value) > 120:
        raise WNBAPlayerPropBoardModelInputError("WNBA Step 5K player_name cannot exceed 120 characters.")
    return value


def _candidate_row(
    candidate: dict[str, Any],
    calibration_report: dict[str, Any] | None,
    *,
    minimum_base_probability: float,
    minimum_worst_scenario_probability: float,
    maximum_scenario_span_percentage_points: float,
    require_same_favored_side_all_scenarios: bool,
    require_strict_numerical_readiness: bool,
    require_mature_calibration: bool,
) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise WNBAPlayerPropBoardModelInputError("Each Step 5K candidate must be an object.")
    threshold = candidate.get("threshold")
    identity = _verify_threshold(threshold)
    calibration = _calibration_context(
        calibration_report,
        model_version=THRESHOLD_MODEL_VERSION,
        stat=identity["stat"],
    )
    market = _verify_market_consensus(candidate.get("market_consensus"), threshold, identity)
    side = identity["selected_side"]
    reasons: list[str] = []

    if side not in SIDES:
        base_probability = 0.5
        probabilities = {name: 0.5 for name in SCENARIOS}
        worst_probability = 0.5
        span = 0.0
        reasons.append("balanced_base_probability")
    else:
        probabilities = {
            name: identity["scenario_probabilities"][name][side]
            for name in SCENARIOS
        }
        base_probability = probabilities["base"]
        worst_probability = min(probabilities.values())
        span = max(probabilities.values()) - min(probabilities.values())

    if base_probability < minimum_base_probability:
        reasons.append("base_probability_below_minimum")
    if worst_probability < minimum_worst_scenario_probability:
        reasons.append("worst_scenario_probability_below_minimum")
    if span * 100.0 > maximum_scenario_span_percentage_points + 1e-12:
        reasons.append("scenario_probability_span_above_maximum")
    if require_same_favored_side_all_scenarios and not identity["same_favored_side_across_all_scenarios"]:
        reasons.append("favored_side_changes_across_scenarios")
    if require_strict_numerical_readiness and not identity["strict_numerical_readiness_passed"]:
        reasons.append("strict_numerical_readiness_failed")
    if not identity["all_fair_odds_available"]:
        reasons.append("fair_odds_not_available_across_all_scenarios")
    if require_mature_calibration and not calibration.get("mature"):
        reasons.append("mature_historical_calibration_required")

    fair_selected = (
        deepcopy(identity["fair_odds_base"].get(side)) if side in SIDES else None
    )
    row = {
        "player_id": identity["player_id"],
        "player_name": _display_label(candidate),
        "game_id": identity["game_id"],
        "team_key": identity["team_key"],
        "opponent_team_key": identity["opponent_team_key"],
        "season": identity["season"],
        "season_type": identity["season_type"],
        "prop": {"stat": identity["stat"], "line": identity["line"]},
        "selected_side": side,
        "probability": {
            "low": round(probabilities["low"], 10),
            "base": round(probabilities["base"], 10),
            "high": round(probabilities["high"], 10),
            "worst_conditional_scenario": round(worst_probability, 10),
            "scenario_span": round(span, 10),
            "scenario_span_percentage_points": round(span * 100.0, 6),
            "base_margin_over_coin_flip_percentage_points": round((base_probability - 0.5) * 100.0, 6),
        },
        "projection_mean": {
            name: round(identity["scenario_means"][name], 10) for name in SCENARIOS
        },
        "raw_push_probability": {
            name: round(identity["scenario_pushes"][name], 10) for name in SCENARIOS
        },
        "base_fair_odds_selected_side": fair_selected,
        "scenario_stability": {
            "favored_side_by_scenario": deepcopy(identity["scenario_favored"]),
            "same_favored_side_across_all_scenarios": identity[
                "same_favored_side_across_all_scenarios"
            ],
        },
        "numerical_readiness": {
            "strict_numerical_readiness_passed": identity["strict_numerical_readiness_passed"],
            "all_fair_odds_available": identity["all_fair_odds_available"],
            "maximum_probability_mc_standard_error": round(
                identity["max_probability_mc_standard_error"], 10
            ),
        },
        "step_5f_reference": {
            "model_version": THRESHOLD_MODEL_VERSION,
            "probability_id": identity["probability_id"],
            "probability_fingerprint_sha256": identity["probability_fingerprint_sha256"],
        },
        "snapshot_reference": identity["snapshot_reference"],
        "historical_calibration": calibration,
        "market_context": market,
        "qualification": {
            "qualified_for_probability_board": len(reasons) == 0,
            "reason_codes": reasons,
        },
        "board_selection": {
            "included_on_probability_board": False,
            "probability_rank": None,
            "suppressed_as_alternate_line": False,
            "included_on_value_board": False,
            "value_rank": None,
        },
    }
    return row


def _probability_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    probability = row["probability"]
    numerical = row["numerical_readiness"]
    prop = row["prop"]
    return (
        -float(probability["base"]),
        -float(probability["worst_conditional_scenario"]),
        float(probability["scenario_span"]),
        float(numerical["maximum_probability_mc_standard_error"]),
        str(row["game_id"]),
        int(row["player_id"]),
        str(prop["stat"]),
        float(prop["line"]),
        str(row["selected_side"]),
    )


def _value_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    quote = row["market_context"]["best_risk_adjusted_ev_quote_selected_side"]
    return (
        -float(quote["risk_adjusted_ev_per_unit"]),
        -float(quote["base_ev_per_unit"]),
        -float(row["probability"]["base"]),
        -float(quote["decimal_odds"]),
        str(quote["sportsbook"]).casefold(),
        str(row["game_id"]),
        int(row["player_id"]),
        str(row["prop"]["stat"]),
        float(row["prop"]["line"]),
    )


def _public_board_row(row: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(row)


def build_player_prop_top_five_board(
    candidates: list[dict[str, Any]],
    *,
    calibration_report: dict[str, Any] | None = None,
    top_n: int = DEFAULT_TOP_N,
    minimum_base_probability: float = DEFAULT_MINIMUM_BASE_PROBABILITY,
    minimum_worst_scenario_probability: float = DEFAULT_MINIMUM_WORST_SCENARIO_PROBABILITY,
    maximum_scenario_span_percentage_points: float = DEFAULT_MAXIMUM_SCENARIO_SPAN_PERCENTAGE_POINTS,
    require_same_favored_side_all_scenarios: bool = True,
    require_strict_numerical_readiness: bool = True,
    require_mature_calibration: bool = False,
    one_line_per_player_stat: bool = True,
) -> dict[str, Any]:
    if not isinstance(candidates, list) or not MIN_CANDIDATES <= len(candidates) <= MAX_CANDIDATES:
        raise ValueError(
            f"WNBA Step 5K candidates must contain {MIN_CANDIDATES} through {MAX_CANDIDATES} records."
        )
    top_n = _top_n(top_n)
    minimum_base_probability = _probability(
        minimum_base_probability, "minimum_base_probability"
    )
    minimum_worst_scenario_probability = _probability(
        minimum_worst_scenario_probability,
        "minimum_worst_scenario_probability",
    )
    maximum_scenario_span_percentage_points = _percentage_points(
        maximum_scenario_span_percentage_points,
        "maximum_scenario_span_percentage_points",
    )
    require_same_favored_side_all_scenarios = _bool(
        require_same_favored_side_all_scenarios,
        "require_same_favored_side_all_scenarios",
    )
    require_strict_numerical_readiness = _bool(
        require_strict_numerical_readiness,
        "require_strict_numerical_readiness",
    )
    require_mature_calibration = _bool(
        require_mature_calibration, "require_mature_calibration"
    )
    one_line_per_player_stat = _bool(
        one_line_per_player_stat, "one_line_per_player_stat"
    )
    calibration_report = _verify_calibration_report(calibration_report)

    rows: list[dict[str, Any]] = []
    logical_keys: set[tuple[Any, ...]] = set()
    fingerprints: set[str] = set()
    for candidate in candidates:
        row = _candidate_row(
            candidate,
            calibration_report,
            minimum_base_probability=minimum_base_probability,
            minimum_worst_scenario_probability=minimum_worst_scenario_probability,
            maximum_scenario_span_percentage_points=maximum_scenario_span_percentage_points,
            require_same_favored_side_all_scenarios=require_same_favored_side_all_scenarios,
            require_strict_numerical_readiness=require_strict_numerical_readiness,
            require_mature_calibration=require_mature_calibration,
        )
        logical_key = (
            row["game_id"],
            row["player_id"],
            row["prop"]["stat"],
            row["prop"]["line"],
        )
        fingerprint = row["step_5f_reference"]["probability_fingerprint_sha256"]
        if logical_key in logical_keys:
            raise WNBAPlayerPropBoardModelInputError(
                "Duplicate Step 5K logical player/game/stat/line candidate is not allowed."
            )
        if fingerprint in fingerprints:
            raise WNBAPlayerPropBoardModelInputError(
                "Duplicate Step 5F probability fingerprint is not allowed on one Step 5K board."
            )
        logical_keys.add(logical_key)
        fingerprints.add(fingerprint)
        rows.append(row)

    qualified = [
        row for row in rows if row["qualification"]["qualified_for_probability_board"]
    ]
    qualified.sort(key=_probability_sort_key)

    probability_pool: list[dict[str, Any]] = []
    if one_line_per_player_stat:
        seen_groups: set[tuple[Any, ...]] = set()
        for row in qualified:
            group = (row["game_id"], row["player_id"], row["prop"]["stat"])
            if group in seen_groups:
                row["board_selection"]["suppressed_as_alternate_line"] = True
                continue
            seen_groups.add(group)
            probability_pool.append(row)
    else:
        probability_pool = list(qualified)

    probability_selected = probability_pool[:top_n]
    for index, row in enumerate(probability_selected, start=1):
        row["board_selection"]["included_on_probability_board"] = True
        row["board_selection"]["probability_rank"] = index

    value_pool = []
    for row in probability_pool:
        market = row.get("market_context") or {}
        quote = market.get("best_risk_adjusted_ev_quote_selected_side")
        if not market.get("available") or not isinstance(quote, dict):
            continue
        risk_ev = _float(quote.get("risk_adjusted_ev_per_unit"))
        if risk_ev is None or risk_ev <= 0.0:
            continue
        value_pool.append(row)
    value_pool.sort(key=_value_sort_key)
    value_selected = value_pool[:top_n]
    for index, row in enumerate(value_selected, start=1):
        row["board_selection"]["included_on_value_board"] = True
        row["board_selection"]["value_rank"] = index

    config = {
        "model_version": MODEL_VERSION,
        "threshold_model_version": THRESHOLD_MODEL_VERSION,
        "market_consensus_model_version": MARKET_CONSENSUS_MODEL_VERSION,
        "backtest_calibration_model_version": BACKTEST_CALIBRATION_MODEL_VERSION,
        "top_n": top_n,
        "minimum_base_probability": minimum_base_probability,
        "minimum_worst_scenario_probability": minimum_worst_scenario_probability,
        "maximum_scenario_span_percentage_points": maximum_scenario_span_percentage_points,
        "require_same_favored_side_all_scenarios": require_same_favored_side_all_scenarios,
        "require_strict_numerical_readiness": require_strict_numerical_readiness,
        "require_mature_calibration": require_mature_calibration,
        "one_line_per_player_stat": one_line_per_player_stat,
        "primary_ranking_method": "base_resolved_fair_probability_descending",
        "primary_tiebreakers": [
            "worst_conditional_scenario_probability_descending",
            "scenario_probability_span_ascending",
            "maximum_probability_mc_standard_error_ascending",
            "deterministic_identity",
        ],
        "value_ranking_method": "best_selected_side_risk_adjusted_ev_descending",
        "market_never_changes_primary_probability_rank": True,
        "calibration_never_rescales_current_probability": True,
    }
    all_rows = [_public_board_row(row) for row in rows]
    probability_board = [_public_board_row(row) for row in probability_selected]
    value_board = [_public_board_row(row) for row in value_selected]
    fingerprint_payload = {
        "candidate_probability_fingerprints": sorted(fingerprints),
        "calibration_report_fingerprint_sha256": (
            calibration_report.get("calibration_report_fingerprint_sha256")
            if calibration_report is not None
            else None
        ),
        "model_config": config,
        "probability_board": probability_board,
        "value_board": value_board,
        "all_candidate_rows": all_rows,
    }
    board_fingerprint = _hash(fingerprint_payload)
    disqualified_count = sum(
        not row["qualification"]["qualified_for_probability_board"] for row in rows
    )
    alternate_suppressed_count = sum(
        row["board_selection"]["suppressed_as_alternate_line"] for row in rows
    )

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_player_prop_top_five_probability_and_value_board",
        "schema_version": BOARD_SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _now_iso(),
        "board_id": f"wnba-5k-board-{board_fingerprint[:20]}",
        "board_fingerprint_sha256": board_fingerprint,
        "candidate_count": len(rows),
        "qualified_candidate_count": len(qualified),
        "disqualified_candidate_count": disqualified_count,
        "alternate_line_suppressed_count": alternate_suppressed_count,
        "probability_board_count": len(probability_board),
        "value_board_count": len(value_board),
        "requested_top_n": top_n,
        "probability_board": probability_board,
        "value_board": value_board,
        "all_candidates": all_rows,
        "calibration_report_reference": (
            {
                "calibration_report_id": calibration_report.get("calibration_report_id"),
                "calibration_report_fingerprint_sha256": calibration_report.get(
                    "calibration_report_fingerprint_sha256"
                ),
                "observation_count": calibration_report.get("observation_count"),
            }
            if calibration_report is not None
            else None
        ),
        "model_config": config,
        "ranking_semantics": {
            "top_five_is_a_maximum_not_a_quota": True,
            "fewer_than_five_is_valid_when_fewer_candidates_qualify": True,
            "primary_board_is_pure_model_probability_ranking": True,
            "sportsbook_price_cannot_move_primary_board_rank": True,
            "value_board_is_separate_from_probability_board": True,
            "risk_adjusted_value_means_worst_low_base_high_conditional_ev_from_step_5h": True,
            "historical_calibration_is_evidence_not_probability_recalibration": True,
            "alternate_lines_do_not_crowd_primary_board_by_default": True,
        },
        "guardrails": {
            "step_5f_probability_fingerprint_verified": True,
            "step_5h_must_reference_same_step_5f_fingerprint_when_supplied": True,
            "step_5i_calibration_fingerprint_verified_when_supplied": calibration_report is not None,
            "no_sportsbook_input_changes_model_probability": True,
            "no_calibration_metric_changes_current_model_probability": True,
            "no_scenario_weights_invented": True,
            "no_forced_five_recommendations": True,
            "no_forced_value_recommendation": True,
            "duplicate_logical_candidates_rejected": True,
            "deterministic_tie_breaking": True,
            "board_fingerprint_created": True,
        },
    }
