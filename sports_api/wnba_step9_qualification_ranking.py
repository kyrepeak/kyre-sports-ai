"""Step 9D: qualified WNBA prop ranking + Top-N selection.

This layer consumes only frozen, hash-valid Step-9C multi-sportsbook consensus
objects. It never changes the basketball projection, Monte Carlo distribution,
threshold probabilities, sportsbook comparisons, or same-line consensus.

Each prop is evaluated on both sides. A side may qualify only when it has a
same-line multi-book consensus plus sufficient model probability, EV, consensus
edge, and market agreement. The strongest qualified side becomes that prop's
candidate. The board then exposes two transparent rankings:

* pure probability: model probability first, then EV/edge tie-breakers;
* value: EV first, then edge/model-probability tie-breakers.

The primary Top-N card list uses the pure-probability ranking after qualification.
It never forces five recommendations. By default it allows at most one selection
per player per game to reduce obvious same-player correlation concentration.

No sportsbook/network call occurs here. Production, scheduler, Supabase and
persistence remain fail-closed.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping, Sequence

from sports_api.wnba_step9_multisportsbook_consensus import (
    MODEL_VERSION as STEP9C_MODEL_VERSION,
    RELEASE_ID as STEP9C_RELEASE_ID,
    SCHEMA_VERSION as STEP9C_SCHEMA_VERSION,
)

SOURCE = "Kyre Sports API WNBA Step 9D qualification and ranking"
SCHEMA_VERSION = "wnba_step_9d_qualification_ranking_v1"
MODEL_VERSION = "wnba_step9d_qualified_probability_value_ranking_2026_regular_v1"
RELEASE_ID = "wnba_step9d_qualification_ranking_2026_regular_season_v1"
STEP9D_QUALIFICATION_RANKING_ENABLED_ENV = "WNBA_STEP9D_QUALIFICATION_RANKING_ENABLED"
STEP9C_FROZEN_SHA = "7372d5a22665e84cd0179c2346939d953e52c31a"

DEFAULT_TOP_N = 5
MAX_TOP_N = 20
MAX_PROP_CONSENSUS_INPUTS = 250
DEFAULT_MINIMUM_MODEL_PROBABILITY = 0.55
DEFAULT_MINIMUM_EV = 0.05
DEFAULT_MINIMUM_CONSENSUS_EDGE = 0.03
DEFAULT_MINIMUM_BOOKS_AT_LINE = 2
DEFAULT_MAXIMUM_CONSENSUS_RANGE_PERCENTAGE_POINTS = 8.0
DEFAULT_MAX_BOARD_SNAPSHOT_SPREAD_SECONDS = 300
MAX_BOARD_SNAPSHOT_SPREAD_SECONDS = 3_600
_LINE_TOLERANCE = 1e-9

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep9QualificationRankingDisabledError(RuntimeError):
    """Raised when Step 9D is not explicitly enabled."""


class WNBAStep9QualificationRankingNotReadyError(RuntimeError):
    """Raised when a cross-prop board cannot be compared safely."""


class WNBAStep9QualificationRankingUpstreamError(RuntimeError):
    """Raised when a Step-9C payload is malformed, mismatched, or tampered."""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step9d_qualification_ranking_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP9D_QUALIFICATION_RANKING_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep9QualificationRankingDisabledError(
            "Step 9D refuses production switches: " + ", ".join(bad)
        )
    if not _truthy(source.get(STEP9D_QUALIFICATION_RANKING_ENABLED_ENV)):
        raise WNBAStep9QualificationRankingDisabledError(
            f"Step 9D requires {STEP9D_QUALIFICATION_RANKING_ENABLED_ENV}=true."
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


def _parse_utc(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise WNBAStep9QualificationRankingUpstreamError(f"Step 9D missing {label}.")
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise WNBAStep9QualificationRankingUpstreamError(
            f"Step 9D invalid timezone-aware timestamp for {label}."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAStep9QualificationRankingUpstreamError(
            f"Step 9D requires timezone-aware timestamp for {label}."
        )
    return parsed.astimezone(timezone.utc)


def _finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep9QualificationRankingUpstreamError(
            f"Step 9D invalid numeric value for {label}."
        ) from exc
    if not math.isfinite(number):
        raise WNBAStep9QualificationRankingUpstreamError(
            f"Step 9D invalid numeric value for {label}."
        )
    return number


def _probability(value: Any, label: str) -> float:
    number = _finite_number(value, label)
    if not 0.0 <= number <= 1.0:
        raise WNBAStep9QualificationRankingUpstreamError(
            f"Step 9D invalid probability for {label}."
        )
    return number


def _threshold_probability(value: float, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be a number from 0 through 1.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"WNBA {label} must be a number from 0 through 1.") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"WNBA {label} must be a number from 0 through 1.")
    return round(number, 8)


def _threshold_percentage_points(value: float, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be a number from 0 through 100.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"WNBA {label} must be a number from 0 through 100.") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 100.0:
        raise ValueError(f"WNBA {label} must be a number from 0 through 100.")
    return round(number, 6)


def _positive_int(value: int, label: str, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise ValueError(f"WNBA {label} must be an integer from 1 through {maximum}.")
    return value


def _snapshot_limit(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value <= MAX_BOARD_SNAPSHOT_SPREAD_SECONDS
    ):
        raise ValueError(
            "WNBA max_board_snapshot_spread_seconds must be an integer from 0 through 3600."
        )
    return value


def _validate_consensus_hash(consensus: Mapping[str, Any]) -> str:
    observed = str(consensus.get("consensus_content_sha256") or "").strip().lower()
    if not _valid_sha256(observed):
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D requires a valid Step-9C consensus_content_sha256."
        )
    surface = dict(consensus)
    surface.pop("generated_at_utc", None)
    surface.pop("consensus_content_sha256", None)
    expected = _canonical_hash(surface)
    if observed != expected:
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D detected a Step-9C content-hash mismatch."
        )
    return observed


def _validate_step9c_consensus(consensus: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(consensus, Mapping):
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D requires Step-9C consensus objects."
        )
    if consensus.get("data_type") != "post_projection_multisportsbook_consensus":
        raise WNBAStep9QualificationRankingUpstreamError("Step 9D received wrong Step-9C data type.")
    if consensus.get("schema_version") != STEP9C_SCHEMA_VERSION:
        raise WNBAStep9QualificationRankingUpstreamError("Step 9D received unsupported Step-9C schema.")
    if consensus.get("model_version") != STEP9C_MODEL_VERSION:
        raise WNBAStep9QualificationRankingUpstreamError("Step 9D received unsupported Step-9C model.")
    if consensus.get("release_id") != STEP9C_RELEASE_ID:
        raise WNBAStep9QualificationRankingUpstreamError("Step 9D received unsupported Step-9C release.")

    consensus_hash = _validate_consensus_hash(consensus)
    prop = consensus.get("prop")
    snapshot = consensus.get("snapshot")
    best = consensus.get("best_available")
    lineage = consensus.get("lineage")
    guards = consensus.get("guardrails")
    groups = consensus.get("same_line_consensus")
    if not all(isinstance(item, Mapping) for item in (prop, snapshot, best, lineage, guards)):
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D requires complete Step-9C prop, snapshot, best-available, lineage and guardrail evidence."
        )
    if not isinstance(groups, list) or not groups:
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D requires Step-9C same-line consensus groups."
        )
    if prop.get("different_lines_are_never_probability_averaged") is not True:
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D requires Step-9C line-separation guardrails."
        )
    if str(lineage.get("step9b_frozen_git_sha") or "") != "45cd3b43ca2771ae01f6fa3c7345ef0b9a444394":
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D detected Step-9C drift from the frozen Step-9B SHA."
        )
    if str(lineage.get("step9a_frozen_git_sha") or "") != "3b9acde91250d0e7a1767f3861765d4366f510ba":
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D detected Step-9C drift from the frozen Step-9A SHA."
        )

    expected_false = (
        "basketball_projection_changed",
        "step8_distribution_changed",
        "step9a_probabilities_changed",
        "step9b_comparisons_changed",
        "sportsbook_called",
        "different_lines_blended_into_consensus",
        "cross_prop_ranking_calculated",
        "qualification_applied",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    )
    for key in expected_false:
        if guards.get(key) is not False:
            raise WNBAStep9QualificationRankingUpstreamError(
                f"Step 9D requires frozen Step-9C guardrail {key}=false."
            )
    for key in ("cross_sportsbook_consensus_calculated", "best_offer_selected_within_prop"):
        if guards.get(key) is not True:
            raise WNBAStep9QualificationRankingUpstreamError(
                f"Step 9D requires Step-9C capability guard {key}=true."
            )

    game_id = str(consensus.get("game_id") or "").strip()
    team_key = str(consensus.get("team_key") or "").strip()
    opponent_key = str(consensus.get("opponent_team_key") or "").strip()
    stat = str(prop.get("stat") or "").strip()
    try:
        player_id = int(consensus.get("player_id"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D received invalid Step-9C player identity."
        ) from exc
    if (
        len(game_id) != 10
        or not game_id.isdigit()
        or player_id <= 0
        or not team_key
        or not opponent_key
        or team_key == opponent_key
        or stat not in {"points", "rebounds", "assists", "pra"}
    ):
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D received malformed Step-9C prop identity."
        )

    step8_hash = str(lineage.get("step8_result_content_sha256") or "").strip().lower()
    if not _valid_sha256(step8_hash):
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D requires Step-9C to carry a valid Step-8 result hash."
        )

    earliest = _parse_utc(snapshot.get("earliest_captured_at_utc"), "Step-9C earliest quote timestamp")
    latest = _parse_utc(snapshot.get("latest_captured_at_utc"), "Step-9C latest quote timestamp")
    if latest < earliest:
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D Step-9C snapshot timestamps are reversed."
        )
    try:
        offer_count = int(snapshot.get("offer_count"))
        unique_book_count = int(snapshot.get("unique_sportsbook_count"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D received invalid Step-9C sportsbook counts."
        ) from exc
    if offer_count < 2 or unique_book_count < 2:
        raise WNBAStep9QualificationRankingUpstreamError(
            "Step 9D requires Step-9C multi-book evidence."
        )

    normalized_groups: list[dict[str, Any]] = []
    seen_lines: set[float] = set()
    for group in groups:
        if not isinstance(group, Mapping):
            raise WNBAStep9QualificationRankingUpstreamError(
                "Step 9D found malformed Step-9C consensus group."
            )
        line = round(_finite_number(group.get("line"), "Step-9C line"), 6)
        if line in seen_lines:
            raise WNBAStep9QualificationRankingUpstreamError(
                "Step 9D refuses duplicate Step-9C same-line consensus groups."
            )
        seen_lines.add(line)
        try:
            book_count = int(group.get("book_count"))
        except (TypeError, ValueError) as exc:
            raise WNBAStep9QualificationRankingUpstreamError(
                "Step 9D received invalid Step-9C same-line book count."
            ) from exc
        over_market = group.get("no_vig_over")
        under_market = group.get("no_vig_under")
        model = group.get("model")
        edge = group.get("consensus_edge")
        if not all(isinstance(item, Mapping) for item in (over_market, under_market, model, edge)):
            raise WNBAStep9QualificationRankingUpstreamError(
                "Step 9D requires complete Step-9C same-line probability evidence."
            )
        normalized_groups.append(
            {
                "line": line,
                "book_count": book_count,
                "consensus_available": group.get("consensus_available") is True,
                "over_market_probability": _probability(
                    over_market.get("median_probability"), "same-line median Over probability"
                ),
                "under_market_probability": _probability(
                    under_market.get("median_probability"), "same-line median Under probability"
                ),
                "over_range_pp": _finite_number(
                    over_market.get("range_percentage_points"), "same-line Over probability range"
                ),
                "under_range_pp": _finite_number(
                    under_market.get("range_percentage_points"), "same-line Under probability range"
                ),
                "model_over_probability": _probability(
                    model.get("resolved_fair_over_probability"), "same-line model Over probability"
                ),
                "model_under_probability": _probability(
                    model.get("resolved_fair_under_probability"), "same-line model Under probability"
                ),
                "over_consensus_edge": (
                    None
                    if edge.get("over_probability") is None
                    else _finite_number(edge.get("over_probability"), "same-line Over consensus edge")
                ),
                "under_consensus_edge": (
                    None
                    if edge.get("under_probability") is None
                    else _finite_number(edge.get("under_probability"), "same-line Under consensus edge")
                ),
            }
        )

    return {
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "stat": stat,
        "prop_key": f"{game_id}:{player_id}:{stat}",
        "player_game_key": f"{game_id}:{player_id}",
        "consensus_hash": consensus_hash,
        "step8_hash": step8_hash,
        "earliest": earliest,
        "latest": latest,
        "all_quotes_fresh": snapshot.get("all_quotes_fresh") is True,
        "snapshot_synchronized": (
            snapshot.get("require_synchronized_snapshot") is True
            and _finite_number(snapshot.get("snapshot_spread_seconds"), "Step-9C snapshot spread")
            <= _finite_number(snapshot.get("max_snapshot_spread_seconds"), "Step-9C snapshot limit") + 1e-9
        ),
        "unique_book_count": unique_book_count,
        "groups": normalized_groups,
        "best_available": deepcopy(best),
    }


def _group_for_line(validated: Mapping[str, Any], line: float) -> Mapping[str, Any] | None:
    for group in validated["groups"]:
        if abs(float(group["line"]) - float(line)) <= _LINE_TOLERANCE:
            return group
    return None


def _offer_metrics(offer: Mapping[str, Any], side: str) -> dict[str, Any]:
    if not isinstance(offer, Mapping):
        raise WNBAStep9QualificationRankingUpstreamError(
            f"Step 9D missing Step-9C best-available {side} offer."
        )
    try:
        line = round(float(offer.get("line")), 6)
    except (TypeError, ValueError) as exc:
        raise WNBAStep9QualificationRankingUpstreamError(
            f"Step 9D invalid Step-9C {side} offer line."
        ) from exc
    sportsbook = str(offer.get("sportsbook") or "").strip()
    if not sportsbook or not math.isfinite(line):
        raise WNBAStep9QualificationRankingUpstreamError(
            f"Step 9D invalid Step-9C {side} offer identity."
        )
    return {
        "sportsbook": sportsbook,
        "line": line,
        "american_odds": offer.get("american_odds"),
        "decimal_odds": _finite_number(offer.get("decimal_odds"), f"{side} decimal odds"),
        "model_probability": _probability(
            offer.get("model_resolved_fair_win_probability"), f"{side} model fair probability"
        ),
        "model_raw_win_probability": _probability(
            offer.get("model_raw_win_probability"), f"{side} raw win probability"
        ),
        "model_push_probability": _probability(
            offer.get("model_raw_push_probability"), f"{side} push probability"
        ),
        "ev": _finite_number(offer.get("ev_per_unit"), f"{side} EV"),
        "ev_roi_percentage": _finite_number(offer.get("ev_roi_percentage"), f"{side} EV percentage"),
        "captured_at_utc": str(offer.get("captured_at_utc") or ""),
        "comparison_content_sha256": str(offer.get("comparison_content_sha256") or ""),
        "pricing_content_sha256": str(offer.get("pricing_content_sha256") or ""),
    }


def _candidate_offer(validated: Mapping[str, Any], side: str, minimum_books: int) -> tuple[dict[str, Any], Mapping[str, Any] | None, str]:
    best = validated["best_available"]
    overall = _offer_metrics(best.get(side), side)
    overall_group = _group_for_line(validated, overall["line"])
    if (
        overall_group is not None
        and overall_group.get("consensus_available") is True
        and int(overall_group.get("book_count", 0)) >= minimum_books
    ):
        return overall, overall_group, "overall_best_available_with_same_line_consensus"

    reference = best.get("reference_line_best_price")
    if isinstance(reference, Mapping):
        fallback = _offer_metrics(reference.get(side), side)
        fallback_group = _group_for_line(validated, fallback["line"])
        if (
            fallback_group is not None
            and fallback_group.get("consensus_available") is True
            and int(fallback_group.get("book_count", 0)) >= minimum_books
        ):
            return fallback, fallback_group, "reference_line_best_price_fallback_for_consensus_support"
    return overall, overall_group, "no_consensus_backed_offer_available"


def _build_side_candidate(
    validated: Mapping[str, Any],
    side: str,
    *,
    minimum_model_probability: float,
    minimum_ev: float,
    minimum_consensus_edge: float,
    minimum_books_at_line: int,
    maximum_consensus_range_percentage_points: float,
    require_fresh_snapshots: bool,
    require_synchronized_snapshots: bool,
) -> dict[str, Any]:
    offer, group, selection_method = _candidate_offer(validated, side, minimum_books_at_line)
    reasons: list[str] = []

    if require_fresh_snapshots and not validated["all_quotes_fresh"]:
        reasons.append("snapshot_contains_stale_quote")
    if require_synchronized_snapshots and not validated["snapshot_synchronized"]:
        reasons.append("step9c_snapshot_not_synchronized")

    if group is None or group.get("consensus_available") is not True:
        consensus_edge = None
        market_probability = None
        range_pp = None
        books_at_line = 0 if group is None else int(group.get("book_count", 0))
        reasons.append("same_line_multibook_consensus_unavailable")
    else:
        books_at_line = int(group["book_count"])
        if side == "over":
            consensus_edge = group["over_consensus_edge"]
            market_probability = group["over_market_probability"]
            range_pp = group["over_range_pp"]
            group_model = group["model_over_probability"]
        else:
            consensus_edge = group["under_consensus_edge"]
            market_probability = group["under_market_probability"]
            range_pp = group["under_range_pp"]
            group_model = group["model_under_probability"]
        if consensus_edge is None:
            reasons.append("same_line_consensus_edge_unavailable")
        if abs(float(group_model) - float(offer["model_probability"])) > 2e-8:
            raise WNBAStep9QualificationRankingUpstreamError(
                "Step 9D selected offer disagrees with Step-9C same-line frozen model probability."
            )
        if books_at_line < minimum_books_at_line:
            reasons.append("books_at_line_below_threshold")
        if range_pp is not None and float(range_pp) > maximum_consensus_range_percentage_points + 1e-9:
            reasons.append("same_line_market_disagreement_above_threshold")

    if offer["model_probability"] + 1e-12 < minimum_model_probability:
        reasons.append("model_probability_below_threshold")
    if offer["ev"] + 1e-12 < minimum_ev:
        reasons.append("expected_value_below_threshold")
    if consensus_edge is not None and float(consensus_edge) + 1e-12 < minimum_consensus_edge:
        reasons.append("consensus_edge_below_threshold")

    qualified = not reasons
    candidate_id = (
        f"{validated['prop_key']}:{side}:{offer['line']:.6f}:"
        f"{offer['sportsbook'].casefold()}"
    )
    return {
        "candidate_id": candidate_id,
        "prop_key": validated["prop_key"],
        "player_game_key": validated["player_game_key"],
        "game_id": validated["game_id"],
        "player_id": validated["player_id"],
        "team_key": validated["team_key"],
        "opponent_team_key": validated["opponent_team_key"],
        "stat": validated["stat"],
        "side": side,
        "line": offer["line"],
        "sportsbook": offer["sportsbook"],
        "american_odds": offer["american_odds"],
        "decimal_odds": offer["decimal_odds"],
        "model_probability": round(offer["model_probability"], 10),
        "model_percentage": round(offer["model_probability"] * 100.0, 6),
        "model_raw_win_probability": round(offer["model_raw_win_probability"], 10),
        "model_push_probability": round(offer["model_push_probability"], 10),
        "ev_per_unit": round(offer["ev"], 10),
        "ev_roi_percentage": round(offer["ev_roi_percentage"], 6),
        "same_line_market_no_vig_probability": (
            None if market_probability is None else round(float(market_probability), 10)
        ),
        "same_line_consensus_edge_probability": (
            None if consensus_edge is None else round(float(consensus_edge), 10)
        ),
        "same_line_consensus_edge_percentage_points": (
            None if consensus_edge is None else round(float(consensus_edge) * 100.0, 6)
        ),
        "same_line_book_count": books_at_line,
        "same_line_market_probability_range_percentage_points": (
            None if range_pp is None else round(float(range_pp), 6)
        ),
        "offer_selection_method": selection_method,
        "qualified": qualified,
        "qualification_failures": reasons,
        "qualification_margin": {
            "model_probability_above_minimum": round(
                offer["model_probability"] - minimum_model_probability, 10
            ),
            "ev_above_minimum": round(offer["ev"] - minimum_ev, 10),
            "consensus_edge_above_minimum": (
                None
                if consensus_edge is None
                else round(float(consensus_edge) - minimum_consensus_edge, 10)
            ),
        },
        "lineage": {
            "step9c_consensus_content_sha256": validated["consensus_hash"],
            "step8_result_content_sha256": validated["step8_hash"],
            "step9b_comparison_content_sha256": offer["comparison_content_sha256"],
            "step9a_pricing_content_sha256": offer["pricing_content_sha256"],
        },
    }


def _choose_prop_candidate(over: Mapping[str, Any], under: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    qualified = [deepcopy(candidate) for candidate in (over, under) if candidate.get("qualified") is True]
    if not qualified:
        return None, "no_side_qualified"
    ordered = sorted(
        qualified,
        key=lambda c: (
            -float(c["model_probability"]),
            -float(c["ev_per_unit"]),
            -float(c["same_line_consensus_edge_probability"]),
            -int(c["same_line_book_count"]),
            float(c["same_line_market_probability_range_percentage_points"]),
            str(c["side"]),
        ),
    )
    return ordered[0], (
        "qualified_side_with_highest_model_probability_then_ev_then_consensus_edge_"
        "then_book_count_then_lower_market_disagreement"
    )


def _probability_order(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        -float(candidate["model_probability"]),
        -float(candidate["ev_per_unit"]),
        -float(candidate["same_line_consensus_edge_probability"]),
        -int(candidate["same_line_book_count"]),
        float(candidate["same_line_market_probability_range_percentage_points"]),
        str(candidate["candidate_id"]),
    )


def _value_order(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        -float(candidate["ev_per_unit"]),
        -float(candidate["same_line_consensus_edge_probability"]),
        -float(candidate["model_probability"]),
        -int(candidate["same_line_book_count"]),
        float(candidate["same_line_market_probability_range_percentage_points"]),
        str(candidate["candidate_id"]),
    )


def _rank(candidates: Sequence[Mapping[str, Any]], *, method: str) -> list[dict[str, Any]]:
    key = _probability_order if method == "probability" else _value_order
    ordered = sorted((deepcopy(c) for c in candidates), key=key)
    return [{**candidate, "rank": index + 1} for index, candidate in enumerate(ordered)]


def _top_n_cards(
    probability_ranking: Sequence[Mapping[str, Any]],
    *,
    top_n: int,
    one_selection_per_player: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    used_players: set[str] = set()
    for candidate in probability_ranking:
        if one_selection_per_player and candidate["player_game_key"] in used_players:
            skipped.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "reason": "one_selection_per_player_per_game_policy",
                }
            )
            continue
        selected.append(deepcopy(candidate))
        used_players.add(str(candidate["player_game_key"]))
        if len(selected) >= top_n:
            break
    for index, candidate in enumerate(selected, start=1):
        candidate["top_card_rank"] = index
    return selected, skipped


def build_step9d_qualification_ranking(
    consensuses: Sequence[Mapping[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
    minimum_model_probability: float = DEFAULT_MINIMUM_MODEL_PROBABILITY,
    minimum_ev: float = DEFAULT_MINIMUM_EV,
    minimum_consensus_edge: float = DEFAULT_MINIMUM_CONSENSUS_EDGE,
    minimum_books_at_line: int = DEFAULT_MINIMUM_BOOKS_AT_LINE,
    maximum_consensus_range_percentage_points: float = DEFAULT_MAXIMUM_CONSENSUS_RANGE_PERCENTAGE_POINTS,
    max_board_snapshot_spread_seconds: int = DEFAULT_MAX_BOARD_SNAPSHOT_SPREAD_SECONDS,
    require_fresh_snapshots: bool = True,
    require_synchronized_snapshots: bool = True,
    one_selection_per_player: bool = True,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Qualify and rank Step-9C player props without forcing a full Top-N board."""
    _assert_safe_environment(env)
    if isinstance(consensuses, (str, bytes)) or not isinstance(consensuses, Sequence):
        raise ValueError("WNBA Step 9D consensuses must be a sequence of Step-9C objects.")
    if not 1 <= len(consensuses) <= MAX_PROP_CONSENSUS_INPUTS:
        raise ValueError(
            f"WNBA Step 9D requires from 1 through {MAX_PROP_CONSENSUS_INPUTS} Step-9C consensuses."
        )
    top = _positive_int(top_n, "top_n", MAX_TOP_N)
    min_probability = _threshold_probability(minimum_model_probability, "minimum_model_probability")
    min_ev = _threshold_probability(minimum_ev, "minimum_ev")
    min_edge = _threshold_probability(minimum_consensus_edge, "minimum_consensus_edge")
    min_books = _positive_int(minimum_books_at_line, "minimum_books_at_line", 25)
    max_range_pp = _threshold_percentage_points(
        maximum_consensus_range_percentage_points,
        "maximum_consensus_range_percentage_points",
    )
    board_spread_limit = _snapshot_limit(max_board_snapshot_spread_seconds)
    if not all(
        isinstance(value, bool)
        for value in (require_fresh_snapshots, require_synchronized_snapshots, one_selection_per_player)
    ):
        raise ValueError(
            "WNBA require_fresh_snapshots, require_synchronized_snapshots and one_selection_per_player must be boolean."
        )

    validated = [_validate_step9c_consensus(item) for item in consensuses]
    seen_props: set[str] = set()
    seen_hashes: set[str] = set()
    for item in validated:
        if item["prop_key"] in seen_props:
            raise WNBAStep9QualificationRankingUpstreamError(
                "Step 9D refuses duplicate game/player/stat prop consensuses."
            )
        if item["consensus_hash"] in seen_hashes:
            raise WNBAStep9QualificationRankingUpstreamError(
                "Step 9D refuses duplicate Step-9C consensus hashes."
            )
        seen_props.add(item["prop_key"])
        seen_hashes.add(item["consensus_hash"])
        if require_fresh_snapshots and not item["all_quotes_fresh"]:
            raise WNBAStep9QualificationRankingNotReadyError(
                f"Step 9D requires fresh Step-9C snapshots; {item['prop_key']} is not fully fresh."
            )
        if require_synchronized_snapshots and not item["snapshot_synchronized"]:
            raise WNBAStep9QualificationRankingNotReadyError(
                f"Step 9D requires internally synchronized Step-9C snapshots; {item['prop_key']} is not synchronized."
            )

    board_earliest = min(item["earliest"] for item in validated)
    board_latest = max(item["latest"] for item in validated)
    board_snapshot_spread = (board_latest - board_earliest).total_seconds()
    if require_synchronized_snapshots and board_snapshot_spread > board_spread_limit:
        raise WNBAStep9QualificationRankingNotReadyError(
            f"Step 9D board snapshot spread {board_snapshot_spread:.3f}s exceeds the "
            f"{board_spread_limit}s limit."
        )

    prop_decisions: list[dict[str, Any]] = []
    qualified_prop_candidates: list[dict[str, Any]] = []
    for item in validated:
        over = _build_side_candidate(
            item,
            "over",
            minimum_model_probability=min_probability,
            minimum_ev=min_ev,
            minimum_consensus_edge=min_edge,
            minimum_books_at_line=min_books,
            maximum_consensus_range_percentage_points=max_range_pp,
            require_fresh_snapshots=require_fresh_snapshots,
            require_synchronized_snapshots=require_synchronized_snapshots,
        )
        under = _build_side_candidate(
            item,
            "under",
            minimum_model_probability=min_probability,
            minimum_ev=min_ev,
            minimum_consensus_edge=min_edge,
            minimum_books_at_line=min_books,
            maximum_consensus_range_percentage_points=max_range_pp,
            require_fresh_snapshots=require_fresh_snapshots,
            require_synchronized_snapshots=require_synchronized_snapshots,
        )
        chosen, method = _choose_prop_candidate(over, under)
        prop_decisions.append(
            {
                "prop_key": item["prop_key"],
                "game_id": item["game_id"],
                "player_id": item["player_id"],
                "stat": item["stat"],
                "over": over,
                "under": under,
                "selected_candidate_id": None if chosen is None else chosen["candidate_id"],
                "selection_method": method,
                "qualified": chosen is not None,
                "step9c_consensus_content_sha256": item["consensus_hash"],
            }
        )
        if chosen is not None:
            qualified_prop_candidates.append(chosen)

    probability_ranking = _rank(qualified_prop_candidates, method="probability")
    value_ranking = _rank(qualified_prop_candidates, method="value")
    top_cards, diversification_skips = _top_n_cards(
        probability_ranking,
        top_n=top,
        one_selection_per_player=one_selection_per_player,
    )

    result = {
        "data_type": "post_projection_qualified_prop_ranking",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "qualification_policy": {
            "minimum_model_probability": min_probability,
            "minimum_model_percentage": round(min_probability * 100.0, 6),
            "minimum_ev_per_unit": min_ev,
            "minimum_ev_roi_percentage": round(min_ev * 100.0, 6),
            "minimum_same_line_consensus_edge_probability": min_edge,
            "minimum_same_line_consensus_edge_percentage_points": round(min_edge * 100.0, 6),
            "minimum_books_at_exact_line": min_books,
            "maximum_same_line_market_probability_range_percentage_points": max_range_pp,
            "require_fresh_snapshots": require_fresh_snapshots,
            "require_synchronized_snapshots": require_synchronized_snapshots,
            "max_board_snapshot_spread_seconds": board_spread_limit,
            "one_selection_per_player_per_game_on_primary_top_cards": one_selection_per_player,
            "top_n_requested": top,
            "do_not_force_top_n": True,
        },
        "board_snapshot": {
            "input_prop_count": len(validated),
            "earliest_market_capture_utc": board_earliest.isoformat(),
            "latest_market_capture_utc": board_latest.isoformat(),
            "snapshot_spread_seconds": round(board_snapshot_spread, 3),
            "within_limit": board_snapshot_spread <= board_spread_limit + 1e-9,
        },
        "qualification_summary": {
            "input_prop_count": len(validated),
            "qualified_prop_count": len(qualified_prop_candidates),
            "not_qualified_prop_count": len(validated) - len(qualified_prop_candidates),
            "top_card_count": len(top_cards),
            "requested_top_card_count": top,
            "full_requested_board_available": len(top_cards) >= top,
        },
        "prop_decisions": prop_decisions,
        "rankings": {
            "pure_probability": probability_ranking,
            "value": value_ranking,
            "pure_probability_method": (
                "qualified_only: model_probability_desc, EV_desc, consensus_edge_desc, "
                "book_count_desc, market_disagreement_asc, candidate_id"
            ),
            "value_method": (
                "qualified_only: EV_desc, consensus_edge_desc, model_probability_desc, "
                "book_count_desc, market_disagreement_asc, candidate_id"
            ),
        },
        "top_cards": {
            "primary": top_cards,
            "selection_method": "pure_probability_ranking_after_qualification_and_optional_one-player-per-game diversification",
            "not_forced": True,
            "diversification_skips": diversification_skips,
        },
        "lineage": {
            "step9c_release_id": STEP9C_RELEASE_ID,
            "step9c_model_version": STEP9C_MODEL_VERSION,
            "step9c_schema_version": STEP9C_SCHEMA_VERSION,
            "step9c_frozen_git_sha": STEP9C_FROZEN_SHA,
            "step9c_consensus_content_sha256s": sorted(item["consensus_hash"] for item in validated),
            "step8_result_content_sha256s": sorted({item["step8_hash"] for item in validated}),
        },
        "guardrails": {
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9a_probabilities_changed": False,
            "step9b_comparisons_changed": False,
            "step9c_consensus_changed": False,
            "sportsbook_called": False,
            "cross_sportsbook_consensus_recomputed": False,
            "qualification_applied": True,
            "cross_prop_ranking_calculated": True,
            "top_n_forced": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    hash_surface = dict(result)
    hash_surface.pop("generated_at_utc", None)
    result["ranking_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return result
