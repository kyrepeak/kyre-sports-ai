"""Step 9C: synchronized multi-sportsbook consensus + best available offer.

This layer consumes only hash-valid Step-9B comparisons together with the exact
Step-9A pricing payload each comparison references. That extra lineage object is
required so different statistical lines can be compared without accidentally
mixing projections produced from different Step-8 distributions.

Consensus is calculated only among sportsbooks quoting the SAME statistical line.
Different lines are never blended into one implied probability. Best-available
Over/Under offers may span different lines because every candidate is evaluated by
its own frozen Step-9A probability and Step-9B EV. No cross-prop ranking is done;
that remains Step 9D.

No sportsbook/network call occurs here. Production, scheduler, Supabase and
persistence paths remain fail-closed.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import statistics
from typing import Any, Mapping, Sequence

from sports_api.wnba_step9_sportsbook_market_comparison import (
    MODEL_VERSION as STEP9B_MODEL_VERSION,
    RELEASE_ID as STEP9B_RELEASE_ID,
    SCHEMA_VERSION as STEP9B_SCHEMA_VERSION,
)
from sports_api.wnba_step9_threshold_pricing import (
    MODEL_VERSION as STEP9A_MODEL_VERSION,
    RELEASE_ID as STEP9A_RELEASE_ID,
    SCHEMA_VERSION as STEP9A_SCHEMA_VERSION,
)

SOURCE = "Kyre Sports API WNBA Step 9C synchronized multi-sportsbook consensus"
SCHEMA_VERSION = "wnba_step_9c_multisportsbook_consensus_v1"
MODEL_VERSION = "wnba_step9c_same_line_consensus_best_offer_2026_regular_v1"
RELEASE_ID = "wnba_step9c_multisportsbook_consensus_2026_regular_season_v1"
STEP9C_MULTIBOOK_CONSENSUS_ENABLED_ENV = "WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED"
STEP9B_FROZEN_SHA = "45cd3b43ca2771ae01f6fa3c7345ef0b9a444394"
STEP9A_FROZEN_SHA = "3b9acde91250d0e7a1767f3861765d4366f510ba"
MIN_UNIQUE_SPORTSBOOKS = 2
MAX_OFFERS = 50
DEFAULT_MAX_SNAPSHOT_SPREAD_SECONDS = 120
MAX_SNAPSHOT_SPREAD_SECONDS = 3_600
_LINE_TOLERANCE = 1e-9
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep9MultiBookConsensusDisabledError(RuntimeError):
    """Raised when Step 9C is not explicitly enabled in this process."""


class WNBAStep9MultiBookConsensusNotReadyError(RuntimeError):
    """Raised when quotes cannot safely form a synchronized multi-book snapshot."""


class WNBAStep9MultiBookConsensusUpstreamError(RuntimeError):
    """Raised when supplied Step-9A/9B evidence is malformed, mismatched or tampered."""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step9c_multibook_consensus_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP9C_MULTIBOOK_CONSENSUS_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep9MultiBookConsensusDisabledError(
            "Step 9C refuses production switches: " + ", ".join(bad)
        )
    if not _truthy(source.get(STEP9C_MULTIBOOK_CONSENSUS_ENABLED_ENV)):
        raise WNBAStep9MultiBookConsensusDisabledError(
            f"Step 9C requires {STEP9C_MULTIBOOK_CONSENSUS_ENABLED_ENV}=true."
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


def _finite_probability(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C invalid probability for {label}."
        ) from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C invalid probability for {label}."
        )
    return number


def _finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C invalid numeric value for {label}."
        ) from exc
    if not math.isfinite(number):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C invalid numeric value for {label}."
        )
    return number


def _parse_utc(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C missing {label}."
        )
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C invalid timezone-aware timestamp for {label}."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C requires timezone-aware timestamp for {label}."
        )
    return parsed.astimezone(timezone.utc)


def _snapshot_limit(value: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value <= MAX_SNAPSHOT_SPREAD_SECONDS
    ):
        raise ValueError(
            "WNBA max_snapshot_spread_seconds must be an integer from 0 through 3600."
        )
    return value


def _validate_hash(payload: Mapping[str, Any], field: str, timestamp_field: str) -> str:
    observed = str(payload.get(field) or "").strip().lower()
    if not _valid_sha256(observed):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C requires a valid {field}."
        )
    surface = dict(payload)
    surface.pop(timestamp_field, None)
    surface.pop(field, None)
    expected = _canonical_hash(surface)
    if observed != expected:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C detected a content-hash mismatch for {field}."
        )
    return observed


def _pricing_identity(pricing: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(pricing, Mapping):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires a Step-9A pricing object for every Step-9B comparison."
        )
    if pricing.get("data_type") != "post_projection_prop_threshold_pricing":
        raise WNBAStep9MultiBookConsensusUpstreamError("Step 9C received wrong Step-9A data type.")
    if pricing.get("schema_version") != STEP9A_SCHEMA_VERSION:
        raise WNBAStep9MultiBookConsensusUpstreamError("Step 9C received unsupported Step-9A schema.")
    if pricing.get("model_version") != STEP9A_MODEL_VERSION:
        raise WNBAStep9MultiBookConsensusUpstreamError("Step 9C received unsupported Step-9A model.")
    if pricing.get("release_id") != STEP9A_RELEASE_ID:
        raise WNBAStep9MultiBookConsensusUpstreamError("Step 9C received unsupported Step-9A release.")
    pricing_hash = _validate_hash(pricing, "pricing_content_sha256", "generated_at_utc")
    prop = pricing.get("prop")
    lineage = pricing.get("step8_lineage")
    guards = pricing.get("guardrails")
    if not all(isinstance(item, Mapping) for item in (prop, lineage, guards)):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires complete Step-9A prop, lineage and guardrail evidence."
        )
    if prop.get("line_does_not_change_basketball_projection") is not True:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires Step-9A post-projection line semantics."
        )
    if guards.get("post_projection_only") is not True:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires Step-9A post_projection_only=true."
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
        if guards.get(key) is not False:
            raise WNBAStep9MultiBookConsensusUpstreamError(
                f"Step 9C requires frozen Step-9A guardrail {key}=false."
            )
    game_id = str(pricing.get("game_id") or "").strip()
    team_key = str(pricing.get("team_key") or "").strip()
    opponent_key = str(pricing.get("opponent_team_key") or "").strip()
    try:
        player_id = int(pricing.get("player_id"))
        line = float(prop.get("line"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C received invalid Step-9A identity."
        ) from exc
    stat = str(prop.get("stat") or "").strip()
    step8_hash = str(lineage.get("result_content_sha256") or "").strip().lower()
    if (
        len(game_id) != 10
        or not game_id.isdigit()
        or player_id <= 0
        or not team_key
        or not opponent_key
        or team_key == opponent_key
        or stat not in {"points", "rebounds", "assists", "pra"}
        or not math.isfinite(line)
        or not _valid_sha256(step8_hash)
    ):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C received malformed Step-9A identity or Step-8 lineage."
        )
    return {
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "stat": stat,
        "line": round(line, 6),
        "pricing_hash": pricing_hash,
        "step8_hash": step8_hash,
    }


def _comparison_identity(comparison: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(comparison, Mapping):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires Step-9B comparison objects."
        )
    if comparison.get("data_type") != "post_projection_sportsbook_market_comparison":
        raise WNBAStep9MultiBookConsensusUpstreamError("Step 9C received wrong Step-9B data type.")
    if comparison.get("schema_version") != STEP9B_SCHEMA_VERSION:
        raise WNBAStep9MultiBookConsensusUpstreamError("Step 9C received unsupported Step-9B schema.")
    if comparison.get("model_version") != STEP9B_MODEL_VERSION:
        raise WNBAStep9MultiBookConsensusUpstreamError("Step 9C received unsupported Step-9B model.")
    if comparison.get("release_id") != STEP9B_RELEASE_ID:
        raise WNBAStep9MultiBookConsensusUpstreamError("Step 9C received unsupported Step-9B release.")
    comparison_hash = _validate_hash(
        comparison, "comparison_content_sha256", "generated_at_utc"
    )
    prop = comparison.get("prop")
    sportsbook = comparison.get("sportsbook")
    compared = comparison.get("comparison")
    lineage = comparison.get("step9a_lineage")
    guards = comparison.get("guardrails")
    if not all(isinstance(item, Mapping) for item in (prop, sportsbook, compared, lineage, guards)):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires complete Step-9B prop, sportsbook, comparison, lineage and guardrail evidence."
        )
    if prop.get("line_and_sportsbook_quote_enter_after_projection") is not True:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires Step-9B post-projection market semantics."
        )
    if sportsbook.get("network_fetch_performed") is not False:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C accepts caller-supplied sportsbook snapshots only."
        )
    if sportsbook.get("quote_source") != "caller_supplied_exact_two_way_same_line_quote":
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C received unsupported Step-9B quote provenance."
        )
    required_false = (
        "basketball_projection_changed",
        "step8_distribution_changed",
        "step9a_probabilities_changed",
        "sportsbook_called",
        "cross_sportsbook_consensus_calculated",
        "cross_prop_ranking_calculated",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    )
    for key in required_false:
        if guards.get(key) is not False:
            raise WNBAStep9MultiBookConsensusUpstreamError(
                f"Step 9C requires Step-9B guardrail {key}=false."
            )
    for key in ("sportsbook_quote_consumed", "vig_removed", "edge_calculated", "expected_value_calculated"):
        if guards.get(key) is not True:
            raise WNBAStep9MultiBookConsensusUpstreamError(
                f"Step 9C requires Step-9B capability guard {key}=true."
            )
    game_id = str(comparison.get("game_id") or "").strip()
    team_key = str(comparison.get("team_key") or "").strip()
    opponent_key = str(comparison.get("opponent_team_key") or "").strip()
    book = str(sportsbook.get("name") or "").strip()
    try:
        player_id = int(comparison.get("player_id"))
        line = float(prop.get("line"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C received invalid Step-9B identity."
        ) from exc
    stat = str(prop.get("stat") or "").strip()
    if (
        len(game_id) != 10
        or not game_id.isdigit()
        or player_id <= 0
        or not team_key
        or not opponent_key
        or team_key == opponent_key
        or not book
        or stat not in {"points", "rebounds", "assists", "pra"}
        or not math.isfinite(line)
    ):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C received malformed Step-9B identity."
        )
    if str(lineage.get("frozen_git_sha") or "") != STEP9A_FROZEN_SHA:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C detected Step-9B drift from the frozen Step-9A git SHA."
        )
    step9a_hash = str(lineage.get("pricing_content_sha256") or "").strip().lower()
    if not _valid_sha256(step9a_hash):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires Step-9B to carry a valid Step-9A pricing hash."
        )
    freshness = sportsbook.get("market_freshness")
    quote = sportsbook.get("quote")
    over = compared.get("over")
    under = compared.get("under")
    if not all(isinstance(item, Mapping) for item in (freshness, quote, over, under)):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires complete Step-9B market and side comparison evidence."
        )
    captured = _parse_utc(freshness.get("captured_at_utc"), "Step-9B market captured_at_utc")
    over_market = quote.get("over")
    under_market = quote.get("under")
    if not isinstance(over_market, Mapping) or not isinstance(under_market, Mapping):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C requires two-sided Step-9B quote evidence."
        )
    no_vig_over = _finite_probability(over_market.get("no_vig_probability"), "no-vig over")
    no_vig_under = _finite_probability(under_market.get("no_vig_probability"), "no-vig under")
    if abs(no_vig_over + no_vig_under - 1.0) > 2e-8:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C Step-9B no-vig probabilities do not sum to one."
        )
    return {
        "game_id": game_id,
        "player_id": player_id,
        "team_key": team_key,
        "opponent_team_key": opponent_key,
        "stat": stat,
        "line": round(line, 6),
        "sportsbook": book,
        "sportsbook_key": book.casefold(),
        "captured_at": captured,
        "fresh": freshness.get("fresh") is True and freshness.get("stale") is False,
        "comparison_hash": comparison_hash,
        "step9a_hash": step9a_hash,
        "no_vig_over": no_vig_over,
        "no_vig_under": no_vig_under,
        "over": deepcopy(over),
        "under": deepcopy(under),
        "quote": deepcopy(quote),
        "freshness": deepcopy(freshness),
    }


def _validate_offer_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C offer entries must be objects with comparison and pricing."
        )
    comparison = bundle.get("comparison")
    pricing = bundle.get("pricing")
    c = _comparison_identity(comparison)
    p = _pricing_identity(pricing)
    for key in ("game_id", "player_id", "team_key", "opponent_team_key", "stat"):
        if c[key] != p[key]:
            raise WNBAStep9MultiBookConsensusUpstreamError(
                f"Step 9C Step-9A/9B lineage mismatch for {key}."
            )
    if abs(float(c["line"]) - float(p["line"])) > _LINE_TOLERANCE:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C Step-9A/9B prop lines do not match."
        )
    if c["step9a_hash"] != p["pricing_hash"]:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C Step-9B comparison does not reference the supplied Step-9A pricing hash."
        )
    return {**c, "step8_hash": p["step8_hash"], "pricing_hash": p["pricing_hash"]}


def _side_summary(offer: Mapping[str, Any], side: str) -> dict[str, Any]:
    side_record = offer[side]
    market_record = side_record.get("market")
    model_record = side_record.get("model")
    edge_record = side_record.get("edge")
    ev_record = side_record.get("expected_value")
    if not all(isinstance(item, Mapping) for item in (market_record, model_record, edge_record, ev_record)):
        raise WNBAStep9MultiBookConsensusUpstreamError(
            f"Step 9C incomplete Step-9B {side} evidence."
        )
    return {
        "sportsbook": offer["sportsbook"],
        "line": offer["line"],
        "american_odds": market_record.get("american_odds"),
        "decimal_odds": _finite_number(market_record.get("decimal_odds"), f"{side} decimal odds"),
        "model_raw_win_probability": _finite_probability(
            model_record.get("raw_win_probability"), f"{side} model raw win"
        ),
        "model_raw_push_probability": _finite_probability(
            model_record.get("raw_push_probability"), f"{side} model push"
        ),
        "model_resolved_fair_win_probability": _finite_probability(
            model_record.get("resolved_fair_win_probability"), f"{side} model fair win"
        ),
        "market_no_vig_probability": _finite_probability(
            market_record.get("no_vig_probability"), f"{side} market no-vig"
        ),
        "no_vig_edge_probability": _finite_number(
            edge_record.get("vs_no_vig_market_probability"), f"{side} no-vig edge"
        ),
        "no_vig_edge_percentage_points": _finite_number(
            edge_record.get("vs_no_vig_market_percentage_points"), f"{side} no-vig edge pp"
        ),
        "ev_per_unit": _finite_number(
            ev_record.get("net_profit_per_unit_staked"), f"{side} EV"
        ),
        "ev_roi_percentage": _finite_number(ev_record.get("roi_percentage"), f"{side} ROI"),
        "captured_at_utc": offer["captured_at"].isoformat(),
        "comparison_content_sha256": offer["comparison_hash"],
        "pricing_content_sha256": offer["pricing_hash"],
    }


def _best_offer(offers: Sequence[Mapping[str, Any]], side: str) -> dict[str, Any]:
    summaries = [_side_summary(offer, side) for offer in offers]
    if side == "over":
        ordered = sorted(
            summaries,
            key=lambda x: (
                -x["ev_per_unit"],
                x["line"],
                -x["decimal_odds"],
                x["sportsbook"].casefold(),
            ),
        )
    else:
        ordered = sorted(
            summaries,
            key=lambda x: (
                -x["ev_per_unit"],
                -x["line"],
                -x["decimal_odds"],
                x["sportsbook"].casefold(),
            ),
        )
    best = deepcopy(ordered[0])
    best["selection_method"] = (
        "highest_model_ev_then_side_favorable_line_then_best_decimal_price_then_sportsbook_name"
    )
    best["cross_prop_ranking_applied"] = False
    return best


def _best_price_on_line(offers: Sequence[Mapping[str, Any]], side: str, line: float) -> dict[str, Any]:
    candidates = [
        _side_summary(offer, side)
        for offer in offers
        if abs(float(offer["line"]) - float(line)) <= _LINE_TOLERANCE
    ]
    ordered = sorted(
        candidates,
        key=lambda x: (-x["decimal_odds"], x["sportsbook"].casefold()),
    )
    result = deepcopy(ordered[0])
    result["selection_method"] = "best_decimal_price_at_exact_reference_line"
    return result


def _consensus_group(line: float, offers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    over_probs = [float(offer["no_vig_over"]) for offer in offers]
    under_probs = [float(offer["no_vig_under"]) for offer in offers]
    model_over = [_finite_probability(offer["over"]["model"]["resolved_fair_win_probability"], "model over") for offer in offers]
    model_under = [_finite_probability(offer["under"]["model"]["resolved_fair_win_probability"], "model under") for offer in offers]
    if max(model_over) - min(model_over) > 2e-8 or max(model_under) - min(model_under) > 2e-8:
        raise WNBAStep9MultiBookConsensusUpstreamError(
            "Step 9C same-line offers disagree on frozen model probabilities."
        )
    book_count = len(offers)
    consensus_available = book_count >= MIN_UNIQUE_SPORTSBOOKS
    median_over = statistics.median(over_probs)
    median_under = statistics.median(under_probs)
    mean_over = statistics.fmean(over_probs)
    mean_under = statistics.fmean(under_probs)
    return {
        "line": line,
        "book_count": book_count,
        "sportsbooks": sorted(offer["sportsbook"] for offer in offers),
        "consensus_available": consensus_available,
        "consensus_method": "median_of_same_line_book_no_vig_probabilities" if consensus_available else None,
        "no_vig_over": {
            "median_probability": round(median_over, 10),
            "median_percentage": round(median_over * 100.0, 6),
            "mean_probability": round(mean_over, 10),
            "minimum_probability": round(min(over_probs), 10),
            "maximum_probability": round(max(over_probs), 10),
            "range_percentage_points": round((max(over_probs) - min(over_probs)) * 100.0, 6),
        },
        "no_vig_under": {
            "median_probability": round(median_under, 10),
            "median_percentage": round(median_under * 100.0, 6),
            "mean_probability": round(mean_under, 10),
            "minimum_probability": round(min(under_probs), 10),
            "maximum_probability": round(max(under_probs), 10),
            "range_percentage_points": round((max(under_probs) - min(under_probs)) * 100.0, 6),
        },
        "model": {
            "resolved_fair_over_probability": round(model_over[0], 10),
            "resolved_fair_under_probability": round(model_under[0], 10),
        },
        "consensus_edge": {
            "over_probability": round(model_over[0] - median_over, 10) if consensus_available else None,
            "over_percentage_points": round((model_over[0] - median_over) * 100.0, 6) if consensus_available else None,
            "under_probability": round(model_under[0] - median_under, 10) if consensus_available else None,
            "under_percentage_points": round((model_under[0] - median_under) * 100.0, 6) if consensus_available else None,
        },
        "guardrail": "probabilities from different statistical lines are never blended",
    }


def build_step9c_multibook_consensus(
    offers: Sequence[Mapping[str, Any]],
    *,
    max_snapshot_spread_seconds: int = DEFAULT_MAX_SNAPSHOT_SPREAD_SECONDS,
    require_fresh_quotes: bool = True,
    require_synchronized_snapshot: bool = True,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build same-line market consensus and best offers across synchronized books."""
    _assert_safe_environment(env)
    if isinstance(offers, (str, bytes)) or not isinstance(offers, Sequence):
        raise ValueError("WNBA Step 9C offers must be a sequence of comparison/pricing bundles.")
    if not MIN_UNIQUE_SPORTSBOOKS <= len(offers) <= MAX_OFFERS:
        raise ValueError(
            f"WNBA Step 9C requires from {MIN_UNIQUE_SPORTSBOOKS} through {MAX_OFFERS} offer bundles."
        )
    if not isinstance(require_fresh_quotes, bool) or not isinstance(require_synchronized_snapshot, bool):
        raise ValueError("WNBA require_fresh_quotes and require_synchronized_snapshot must be boolean.")
    spread_limit = _snapshot_limit(max_snapshot_spread_seconds)
    validated = [_validate_offer_bundle(bundle) for bundle in offers]

    first = validated[0]
    identity_keys = ("game_id", "player_id", "team_key", "opponent_team_key", "stat", "step8_hash")
    for offer in validated[1:]:
        for key in identity_keys:
            if offer[key] != first[key]:
                raise WNBAStep9MultiBookConsensusUpstreamError(
                    f"Step 9C cannot mix offers with different {key}."
                )

    unique_books = {offer["sportsbook_key"] for offer in validated}
    if len(unique_books) < MIN_UNIQUE_SPORTSBOOKS:
        raise WNBAStep9MultiBookConsensusNotReadyError(
            "Step 9C requires at least two unique sportsbooks."
        )
    seen_book_line: set[tuple[str, float]] = set()
    for offer in validated:
        key = (offer["sportsbook_key"], float(offer["line"]))
        if key in seen_book_line:
            raise WNBAStep9MultiBookConsensusUpstreamError(
                "Step 9C refuses duplicate sportsbook + exact-line offers."
            )
        seen_book_line.add(key)
        if require_fresh_quotes and not offer["fresh"]:
            raise WNBAStep9MultiBookConsensusNotReadyError(
                f"Step 9C requires fresh quotes; {offer['sportsbook']} at line {offer['line']} is stale."
            )

    captured = [offer["captured_at"] for offer in validated]
    earliest = min(captured)
    latest = max(captured)
    snapshot_spread = (latest - earliest).total_seconds()
    if require_synchronized_snapshot and snapshot_spread > spread_limit:
        raise WNBAStep9MultiBookConsensusNotReadyError(
            f"Step 9C quote snapshot spread {snapshot_spread:.3f}s exceeds the {spread_limit}s limit."
        )

    groups: dict[float, list[Mapping[str, Any]]] = {}
    for offer in validated:
        groups.setdefault(float(offer["line"]), []).append(offer)
    line_consensus = [
        _consensus_group(line, groups[line])
        for line in sorted(groups)
    ]
    reference = sorted(
        line_consensus,
        key=lambda item: (-int(item["book_count"]), float(item["line"])),
    )[0]
    reference_line = float(reference["line"])

    result = {
        "data_type": "post_projection_multisportsbook_consensus",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_id": first["game_id"],
        "player_id": first["player_id"],
        "team_key": first["team_key"],
        "opponent_team_key": first["opponent_team_key"],
        "prop": {
            "stat": first["stat"],
            "unique_lines": sorted(groups),
            "reference_line": reference_line,
            "reference_line_method": "most_sportsbooks_then_lower_line_tiebreak",
            "different_lines_are_never_probability_averaged": True,
        },
        "snapshot": {
            "offer_count": len(validated),
            "unique_sportsbook_count": len(unique_books),
            "unique_sportsbooks": sorted({offer["sportsbook"] for offer in validated}),
            "earliest_captured_at_utc": earliest.isoformat(),
            "latest_captured_at_utc": latest.isoformat(),
            "snapshot_spread_seconds": round(snapshot_spread, 3),
            "max_snapshot_spread_seconds": spread_limit,
            "require_fresh_quotes": require_fresh_quotes,
            "require_synchronized_snapshot": require_synchronized_snapshot,
            "all_quotes_fresh": all(offer["fresh"] for offer in validated),
        },
        "same_line_consensus": line_consensus,
        "best_available": {
            "over": _best_offer(validated, "over"),
            "under": _best_offer(validated, "under"),
            "reference_line_best_price": {
                "line": reference_line,
                "over": _best_price_on_line(validated, "over", reference_line),
                "under": _best_price_on_line(validated, "under", reference_line),
            },
            "selection_scope": "within_one_player_prop_only; cross-prop qualification/ranking is Step 9D",
        },
        "lineage": {
            "step8_result_content_sha256": first["step8_hash"],
            "step9a_release_id": STEP9A_RELEASE_ID,
            "step9a_model_version": STEP9A_MODEL_VERSION,
            "step9a_frozen_git_sha": STEP9A_FROZEN_SHA,
            "step9b_release_id": STEP9B_RELEASE_ID,
            "step9b_model_version": STEP9B_MODEL_VERSION,
            "step9b_frozen_git_sha": STEP9B_FROZEN_SHA,
            "comparison_content_sha256s": sorted(offer["comparison_hash"] for offer in validated),
            "pricing_content_sha256s": sorted({offer["pricing_hash"] for offer in validated}),
        },
        "guardrails": {
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9a_probabilities_changed": False,
            "step9b_comparisons_changed": False,
            "sportsbook_called": False,
            "cross_sportsbook_consensus_calculated": True,
            "different_lines_blended_into_consensus": False,
            "best_offer_selected_within_prop": True,
            "cross_prop_ranking_calculated": False,
            "qualification_applied": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    hash_surface = dict(result)
    hash_surface.pop("generated_at_utc", None)
    result["consensus_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return result
