"""MLB Step 11D — shadow consensus and deterministic failover policy.

This layer consumes only a certified Step 11C multi-provider shadow board. It
evaluates source freshness, computes two-provider no-vig consensus only when
markets are structurally comparable, and emits a deterministic shadow route
(FanDuel primary, DraftKings fallback). It never changes production runtime,
selects a best price, writes persistence, or feeds consensus/failover output
into frozen model or sportsbook inputs.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step11a_provider_contract_v1 import SUPPORTED_CORE_MARKETS
from sports_api.mlb_step11c_multi_provider_shadow_board_v1 import (
    BOARD_STATUS as STEP11C_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP11C_MARKER,
    SUPPORTED_PROVIDERS,
    validate_multi_provider_shadow_board,
)

DATA_TYPE = "mlb_provider_consensus_failover_shadow_policy_v1"
SCHEMA_VERSION = 1
STEP11D_BASE_MAIN_SHA = "f088fe171e8202ae6f000d90ce88bdb7b7d5e9a5"
POLICY_STATUS = "STEP11D_PROVIDER_CONSENSUS_FAILOVER_SHADOW_POLICY_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP11D_PROVIDER_CONSENSUS_FAILOVER_SHADOW_POLICY_GREEN"
DEFAULT_PRIMARY_PROVIDER = "fanduel"
DEFAULT_FALLBACK_PROVIDER = "draftkings"
DEFAULT_MAX_AGE_SECONDS = 180
MAX_MAX_AGE_SECONDS = 3600
CONSENSUS_METHOD = "equal_weight_mean_two_provider_no_vig"


class MLBProviderConsensusFailoverShadowPolicyError(ValueError):
    pass


def policy_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step11d_base_main_sha": STEP11D_BASE_MAIN_SHA,
        "policy_status": POLICY_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step11c_board_status_required": STEP11C_STATUS,
        "step11c_final_certification_marker_required": STEP11C_MARKER,
        "supported_providers": list(SUPPORTED_PROVIDERS),
        "supported_core_markets": list(SUPPORTED_CORE_MARKETS),
        "primary_provider": DEFAULT_PRIMARY_PROVIDER,
        "fallback_provider": DEFAULT_FALLBACK_PROVIDER,
        "default_max_age_seconds": DEFAULT_MAX_AGE_SECONDS,
        "consensus_method": CONSENSUS_METHOD,
        "freshness_required_for_shadow_route": True,
        "source_complete_required_for_shadow_route": True,
        "same_official_game_id_required": True,
        "same_market_phase_required": True,
        "same_line_required_for_spread_total_consensus": True,
        "moneyline_same_line_requirement": False,
        "two_provider_consensus_required": True,
        "shadow_consensus_evaluation_enabled": True,
        "shadow_failover_routing_enabled": True,
        "best_price_selection_enabled": False,
        "provider_weighting_enabled": False,
        "production_provider_consensus_enabled": False,
        "production_provider_failover_enabled": False,
        "network_io_added_by_step11d": False,
        "production_api_wiring_added_by_step11d": False,
        "production_runtime_wiring_added_by_step11d": False,
        "persistence_schema_changed_by_step11d": False,
        "production_database_writes_enabled": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "team_name_join_allowed": False,
        "player_name_join_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        **PROTECTED_INVARIANTS,
    }


def _utc_z(value: Any, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MLBProviderConsensusFailoverShadowPolicyError(
            f"{field} must be UTC RFC3339 ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBProviderConsensusFailoverShadowPolicyError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBProviderConsensusFailoverShadowPolicyError(f"{field} must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _max_age(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MLBProviderConsensusFailoverShadowPolicyError("max_age_seconds must be an integer")
    if not 1 <= value <= MAX_MAX_AGE_SECONDS:
        raise MLBProviderConsensusFailoverShadowPolicyError(
            f"max_age_seconds must be between 1 and {MAX_MAX_AGE_SECONDS}"
        )
    return value


def _provider_pair(primary: Any, fallback: Any) -> tuple[str, str]:
    if primary not in SUPPORTED_PROVIDERS or fallback not in SUPPORTED_PROVIDERS:
        raise MLBProviderConsensusFailoverShadowPolicyError("unsupported provider route")
    if primary == fallback:
        raise MLBProviderConsensusFailoverShadowPolicyError(
            "primary_provider and fallback_provider must differ"
        )
    return str(primary), str(fallback)


def _american_to_probability(odds: Any) -> float:
    if isinstance(odds, bool) or not isinstance(odds, int) or abs(odds) < 100:
        raise MLBProviderConsensusFailoverShadowPolicyError("invalid American odds")
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return (-odds) / ((-odds) + 100.0)


def _no_vig_pair(first_odds: int, second_odds: int) -> tuple[float, float]:
    first = _american_to_probability(first_odds)
    second = _american_to_probability(second_odds)
    total = first + second
    if not math.isfinite(total) or total <= 0:
        raise MLBProviderConsensusFailoverShadowPolicyError("invalid implied probability total")
    return first / total, second / total


def _provider_health(
    provider: Mapping[str, Any],
    *,
    evaluated_at: datetime,
    max_age_seconds: int,
) -> dict[str, Any]:
    _, observed = _utc_z(provider.get("observed_at_utc"), "provider.observed_at_utc")
    if observed > evaluated_at:
        raise MLBProviderConsensusFailoverShadowPolicyError(
            "provider observed_at_utc cannot be after evaluated_at_utc"
        )
    age = (evaluated_at - observed).total_seconds()
    fresh = age <= max_age_seconds
    complete = provider.get("source_complete") is True
    return {
        "provider_key": provider["provider_key"],
        "age_seconds": round(age, 6),
        "fresh": fresh,
        "source_complete": complete,
        "route_eligible": fresh and complete,
    }


def _consensus(
    market_name: str,
    available: list[Mapping[str, Any]],
) -> dict[str, Any]:
    if len(available) < 2:
        return {
            "available": False,
            "status": "INSUFFICIENT_PROVIDERS" if available else "NO_AVAILABLE_PROVIDER",
            "method": None,
            "provider_count": len(available),
            "provider_keys": [row["provider_key"] for row in available],
            "consensus": None,
        }

    rows = {row["provider_key"]: row["market"] for row in available}
    ordered = [key for key in SUPPORTED_PROVIDERS if key in rows]
    if len(ordered) != 2:
        raise MLBProviderConsensusFailoverShadowPolicyError(
            "consensus requires exactly two supported providers"
        )

    if market_name == "moneyline":
        probs = [_no_vig_pair(rows[key]["away_odds"], rows[key]["home_odds"]) for key in ordered]
        consensus = {
            "away_no_vig_probability": sum(p[0] for p in probs) / 2.0,
            "home_no_vig_probability": sum(p[1] for p in probs) / 2.0,
        }
    elif market_name == "run_line":
        signature = (
            rows[ordered[0]]["away_line"],
            rows[ordered[0]]["home_line"],
        )
        other = (
            rows[ordered[1]]["away_line"],
            rows[ordered[1]]["home_line"],
        )
        if signature != other:
            return {
                "available": False,
                "status": "LINE_MISMATCH",
                "method": None,
                "provider_count": 2,
                "provider_keys": ordered,
                "consensus": None,
                "provider_lines": {
                    key: {
                        "away_line": rows[key]["away_line"],
                        "home_line": rows[key]["home_line"],
                    }
                    for key in ordered
                },
            }
        probs = [_no_vig_pair(rows[key]["away_odds"], rows[key]["home_odds"]) for key in ordered]
        consensus = {
            "away_line": signature[0],
            "home_line": signature[1],
            "away_no_vig_probability": sum(p[0] for p in probs) / 2.0,
            "home_no_vig_probability": sum(p[1] for p in probs) / 2.0,
        }
    elif market_name == "total":
        line = rows[ordered[0]]["line"]
        if line != rows[ordered[1]]["line"]:
            return {
                "available": False,
                "status": "LINE_MISMATCH",
                "method": None,
                "provider_count": 2,
                "provider_keys": ordered,
                "consensus": None,
                "provider_lines": {key: rows[key]["line"] for key in ordered},
            }
        probs = [_no_vig_pair(rows[key]["over_odds"], rows[key]["under_odds"]) for key in ordered]
        consensus = {
            "line": line,
            "over_no_vig_probability": sum(p[0] for p in probs) / 2.0,
            "under_no_vig_probability": sum(p[1] for p in probs) / 2.0,
        }
    else:
        raise MLBProviderConsensusFailoverShadowPolicyError(
            f"unsupported market_name: {market_name}"
        )

    return {
        "available": True,
        "status": "TWO_PROVIDER_CONSENSUS_READY",
        "method": CONSENSUS_METHOD,
        "provider_count": 2,
        "provider_keys": ordered,
        "consensus": consensus,
    }


def build_provider_consensus_failover_shadow_policy(
    source_board: Mapping[str, Any],
    *,
    evaluated_at_utc: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    primary_provider: str = DEFAULT_PRIMARY_PROVIDER,
    fallback_provider: str = DEFAULT_FALLBACK_PROVIDER,
) -> dict[str, Any]:
    validation = validate_multi_provider_shadow_board(source_board)
    if validation.get("board_valid") is not True:
        raise MLBProviderConsensusFailoverShadowPolicyError(
            f"invalid Step 11C shadow board: {validation.get('failures')}"
        )

    evaluated, evaluated_dt = _utc_z(evaluated_at_utc, "evaluated_at_utc")
    max_age = _max_age(max_age_seconds)
    primary, fallback = _provider_pair(primary_provider, fallback_provider)
    board = deepcopy(dict(source_board))
    if board.get("board_status") != STEP11C_STATUS:
        raise MLBProviderConsensusFailoverShadowPolicyError("Step 11C board status mismatch")
    _, assembled = _utc_z(board.get("assembled_at_utc"), "source_board.assembled_at_utc")
    if assembled > evaluated_dt:
        raise MLBProviderConsensusFailoverShadowPolicyError(
            "source board assembled_at_utc cannot be after evaluated_at_utc"
        )

    output_groups: list[dict[str, Any]] = []
    failover_candidates = 0
    consensus_ready = 0
    stale_provider_slots = 0

    for group in board["game_phase_groups"]:
        providers = {row["provider_key"]: row for row in group["providers"]}
        health = {
            key: _provider_health(row, evaluated_at=evaluated_dt, max_age_seconds=max_age)
            for key, row in providers.items()
        }
        stale_provider_slots += sum(not row["fresh"] for row in health.values())

        markets = []
        for market_name in SUPPORTED_CORE_MARKETS:
            candidates: list[dict[str, Any]] = []
            for key in SUPPORTED_PROVIDERS:
                provider = providers.get(key)
                if provider is None or not health[key]["route_eligible"]:
                    continue
                market = provider["markets"].get(market_name)
                if market is None:
                    continue
                candidates.append(
                    {
                        "provider_key": key,
                        "provider_name": provider["provider_name"],
                        "record_key": provider["record_key"],
                        "observed_at_utc": provider["observed_at_utc"],
                        "market": deepcopy(market),
                    }
                )

            keys = [row["provider_key"] for row in candidates]
            if primary in keys:
                route = primary
                reason = "PRIMARY_AVAILABLE"
                failover = False
            elif fallback in keys:
                route = fallback
                reason = "PRIMARY_UNAVAILABLE_FALLBACK_AVAILABLE"
                failover = True
                failover_candidates += 1
            else:
                route = None
                reason = "NO_ELIGIBLE_PROVIDER"
                failover = False

            consensus = _consensus(market_name, candidates)
            consensus_ready += int(consensus["available"] is True)
            markets.append(
                {
                    "market_name": market_name,
                    "available_provider_keys": keys,
                    "available_provider_count": len(keys),
                    "shadow_route_provider": route,
                    "shadow_route_reason": reason,
                    "shadow_failover_candidate": failover,
                    "consensus": consensus,
                    "best_price_selection_performed": False,
                    "production_route_changed": False,
                }
            )

        output_groups.append(
            {
                "official_game_id": group["official_game_id"],
                "market_phase": group["market_phase"],
                "provider_health": [
                    health[key] for key in SUPPORTED_PROVIDERS if key in health
                ],
                "markets": markets,
            }
        )

    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "policy_status": POLICY_STATUS,
        "evaluated_at_utc": evaluated,
        "max_age_seconds": max_age,
        "primary_provider": primary,
        "fallback_provider": fallback,
        "source_board_sha256": board["board_sha256"],
        "source_board": board,
        "group_count": len(output_groups),
        "consensus_ready_market_count": consensus_ready,
        "shadow_failover_candidate_count": failover_candidates,
        "stale_provider_slot_count": stale_provider_slots,
        "groups": output_groups,
        "shadow_consensus_evaluation_used": True,
        "shadow_failover_policy_evaluated": True,
        "best_price_selection_used": False,
        "provider_weighting_used": False,
        "production_provider_consensus_used": False,
        "production_provider_failover_used": False,
        "price_fabrication_used": False,
        "fallback_price_fabrication_used": False,
        "network_io_performed": False,
        "production_runtime_wiring": False,
        "production_database_writes": False,
        "persisted_snapshot_as_model_input": False,
        "persisted_snapshot_as_sportsbook_input": False,
    }
    result["policy_sha256"] = _hash(result)
    return result


def validate_provider_consensus_failover_shadow_policy(
    policy: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(policy, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "policy_valid": False,
            "failures": ["STEP11D_POLICY_NOT_MAPPING"],
        }
    failures: list[str] = []
    try:
        rebuilt = build_provider_consensus_failover_shadow_policy(
            policy.get("source_board"),
            evaluated_at_utc=policy.get("evaluated_at_utc"),
            max_age_seconds=policy.get("max_age_seconds"),
            primary_provider=policy.get("primary_provider"),
            fallback_provider=policy.get("fallback_provider"),
        )
    except Exception as exc:
        failures.append(f"STEP11D_REBUILD_FAILED:{type(exc).__name__}:{exc}")
    else:
        if dict(policy) != rebuilt:
            failures.append("STEP11D_POLICY_EXACT_CONTRACT_MISMATCH")
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "policy_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE", "SCHEMA_VERSION", "STEP11D_BASE_MAIN_SHA", "POLICY_STATUS",
    "FINAL_CERTIFICATION_MARKER", "DEFAULT_PRIMARY_PROVIDER",
    "DEFAULT_FALLBACK_PROVIDER", "DEFAULT_MAX_AGE_SECONDS", "MAX_MAX_AGE_SECONDS",
    "CONSENSUS_METHOD", "MLBProviderConsensusFailoverShadowPolicyError",
    "policy_manifest", "build_provider_consensus_failover_shadow_policy",
    "validate_provider_consensus_failover_shadow_policy",
]
