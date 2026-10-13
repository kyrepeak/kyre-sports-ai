from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "UNIVERSAL_SPORTS_TRUST_QUORUM_V1"
WORKSTREAM = "universal-sports-source-finalization-v1"
STEP = "4/8"
PROGRAM_STEPS = 8
ROUTING_UNIT = "DATA_FIELD"
FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP4_TRUST_QUORUM_ENGINE_FROZEN"

_REQUIRED_FIELDS = {
    "schedule": "SCHEDULE",
    "game_identity": "GAME_IDENTITY",
    "team_identity": "TEAM_IDENTITY",
    "player_identity": "PLAYER_IDENTITY",
    "rosters": "ROSTERS",
    "injuries": "INJURIES",
    "official_stats": "OFFICIAL_STATS",
    "advanced_stats": "ADVANCED_STATS",
    "matchup_history": "MATCHUP_HISTORY",
    "sportsbook_lines": "SPORTSBOOK_LINES",
    "line_movement": "LINE_MOVEMENT",
    "public_bet_count": "PUBLIC_BET_COUNT",
    "public_bet_percentage": "PUBLIC_BET_PERCENTAGE",
    "money_percentage": "MONEY_PERCENTAGE",
    "news_context": "NEWS_CONTEXT",
}

_REQUIRED_TOP_LEVEL = {
    "version": VERSION,
    "workstream": WORKSTREAM,
    "step": STEP,
    "program_steps": PROGRAM_STEPS,
    "routing_unit": ROUTING_UNIT,
    "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
    "page_wide_source_authority": False,
    "minimum_quorum_early_stop": True,
    "incompatible_metric_substitution": False,
    "network_calls": False,
    "product_runtime_mutation": False,
    "sports_model_mutation": False,
    "legacy_registry_mutation": False,
    "github_actions_fallback": 0,
    "fabrication": False,
    "freeze_token": FREEZE_TOKEN,
}

_TERMINAL_STATES = {
    "ACCEPTED_SINGLE_AUTHORITY",
    "ACCEPTED_QUORUM",
    "ACCEPTED_FALLBACK_QUORUM",
    "DISAGREEMENT_REQUIRES_EXPANSION",
    "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION",
    "AMBIGUOUS_IDENTITY_FAIL_CLOSED",
    "STALE_DATA_FAIL_CLOSED",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest().upper()


def _trust_policy_id(policy_without_id: Mapping[str, Any]) -> str:
    return f"USTQ-{_sha256(policy_without_id)[:24]}"


def _decision_id(payload: Mapping[str, Any]) -> str:
    return f"QUORUM-{_sha256(payload)[:24]}"


def _value_fingerprint(value: Any) -> str:
    return f"VALUE-{_sha256(value)[:24]}"


def load_trust_policy(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("TRUST_POLICY_NOT_OBJECT")
    return value


def validate_trust_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, Mapping):
        raise ValueError("TRUST_POLICY_NOT_OBJECT")

    raw = deepcopy(dict(policy))
    supplied_policy_id = str(raw.pop("trust_policy_id", "") or "").strip().upper()
    for key, expected in _REQUIRED_TOP_LEVEL.items():
        if raw.get(key) != expected:
            raise ValueError(f"TRUST_POLICY_CONTRACT_DRIFT:{key}")

    fields = raw.get("fields")
    if not isinstance(fields, Mapping) or set(fields) != set(_REQUIRED_FIELDS):
        raise ValueError("TRUST_POLICY_FIELD_COVERAGE_MISMATCH")

    for field, expected_metric in _REQUIRED_FIELDS.items():
        rule = fields.get(field)
        if not isinstance(rule, Mapping):
            raise ValueError(f"TRUST_POLICY_FIELD_INVALID:{field}")
        if str(rule.get("semantic_metric_id") or "").strip().upper() != expected_metric:
            raise ValueError(f"TRUST_POLICY_SEMANTIC_METRIC_MISMATCH:{field}")

        max_age = rule.get("maximum_age_seconds")
        quality = rule.get("minimum_accepted_quality")
        quorum = rule.get("minimum_quorum_size")
        tolerance = rule.get("disagreement_tolerance")
        if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age <= 0:
            raise ValueError(f"TRUST_POLICY_MAX_AGE_INVALID:{field}")
        if not isinstance(quality, (int, float)) or isinstance(quality, bool) or not 0 <= float(quality) <= 1:
            raise ValueError(f"TRUST_POLICY_QUALITY_INVALID:{field}")
        if not isinstance(quorum, int) or isinstance(quorum, bool) or quorum < 1:
            raise ValueError(f"TRUST_POLICY_QUORUM_INVALID:{field}")
        if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) or float(tolerance) < 0:
            raise ValueError(f"TRUST_POLICY_TOLERANCE_INVALID:{field}")
        if rule.get("escalation_order") != "ROUTE_ORDER":
            raise ValueError(f"TRUST_POLICY_ESCALATION_INVALID:{field}")
        if rule.get("fail_closed_terminal_state") != "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION":
            raise ValueError(f"TRUST_POLICY_FAIL_CLOSED_INVALID:{field}")

        single_allowed = rule.get("single_authority_allowed")
        independent_required = rule.get("independent_verification_required")
        if single_allowed not in (True, False) or independent_required not in (True, False):
            raise ValueError(f"TRUST_POLICY_AUTHORITY_FLAGS_INVALID:{field}")
        if single_allowed and (independent_required or quorum != 1):
            raise ValueError(f"TRUST_POLICY_SINGLE_AUTHORITY_CONTRADICTION:{field}")
        if independent_required and quorum < 2:
            raise ValueError(f"TRUST_POLICY_INDEPENDENT_QUORUM_TOO_SMALL:{field}")

    expected_policy_id = _trust_policy_id(raw)
    if supplied_policy_id != expected_policy_id:
        raise ValueError("TRUST_POLICY_FINGERPRINT_MISMATCH")

    return {
        "status": "GREEN",
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "program_steps": PROGRAM_STEPS,
        "routing_unit": ROUTING_UNIT,
        "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
        "page_wide_source_authority": False,
        "minimum_quorum_early_stop": True,
        "incompatible_metric_substitution": False,
        "network_calls": False,
        "product_runtime_mutation": False,
        "sports_model_mutation": False,
        "legacy_registry_mutation": False,
        "github_actions_fallback": 0,
        "fabrication": False,
        "field_policy_count": len(fields),
        "trust_policy_id": supplied_policy_id,
        "freeze_token": FREEZE_TOKEN,
    }


def _validate_route(route: Mapping[str, Any]) -> None:
    if not isinstance(route, Mapping):
        raise ValueError("ROUTE_NOT_OBJECT")
    if route.get("routing_unit") != ROUTING_UNIT:
        raise ValueError("ROUTE_ROUTING_UNIT_MISMATCH")
    if route.get("page_wide_source_authority") is not False:
        raise ValueError("ROUTE_PAGE_WIDE_AUTHORITY_FORBIDDEN")
    if route.get("network_calls") is not False:
        raise ValueError("ROUTE_NETWORK_CALL_CONTRACT_DRIFT")
    if route.get("fabrication") is not False:
        raise ValueError("ROUTE_FABRICATION_FORBIDDEN")

    eligible = route.get("eligible_provider_ids")
    fallbacks = route.get("fallback_provider_ids")
    if not isinstance(eligible, list) or len(eligible) != len(set(eligible)):
        raise ValueError("ROUTE_ELIGIBLE_PROVIDERS_INVALID")
    if not isinstance(fallbacks, list):
        raise ValueError("ROUTE_FALLBACKS_INVALID")
    primary = str(route.get("primary_provider_id") or "")
    expected_primary = eligible[0] if eligible else ""
    if primary != expected_primary or fallbacks != eligible[1:]:
        raise ValueError("ROUTE_ORDER_CONTRACT_DRIFT")
    if route.get("active_provider_ids") != []:
        raise ValueError("ROUTE_MUST_ENTER_QUORUM_WITHOUT_ACTIVE_PROVIDERS")


def _observation_map(
    observations: Sequence[Mapping[str, Any]],
    *,
    eligible: Sequence[str],
    semantic_metric_id: str,
) -> dict[str, dict[str, Any]]:
    if isinstance(observations, (str, bytes)) or not isinstance(observations, Sequence):
        raise ValueError("OBSERVATIONS_NOT_SEQUENCE")
    allowed = set(eligible)
    by_provider: dict[str, dict[str, Any]] = {}
    for row in observations:
        if not isinstance(row, Mapping):
            raise ValueError("OBSERVATION_NOT_OBJECT")
        provider_id = str(row.get("provider_id") or "").strip()
        if provider_id not in allowed:
            raise ValueError(f"OFF_ROUTE_PROVIDER:{provider_id}")
        if provider_id in by_provider:
            raise ValueError(f"DUPLICATE_PROVIDER_OBSERVATION:{provider_id}")
        metric = str(row.get("semantic_metric_id") or "").strip().upper()
        if metric != semantic_metric_id:
            raise ValueError(f"SEMANTIC_METRIC_MISMATCH:{provider_id}")
        age = row.get("age_seconds")
        quality = row.get("quality_score")
        if not isinstance(age, (int, float)) or isinstance(age, bool) or float(age) < 0:
            raise ValueError(f"OBSERVATION_AGE_INVALID:{provider_id}")
        if not isinstance(quality, (int, float)) or isinstance(quality, bool) or not 0 <= float(quality) <= 1:
            raise ValueError(f"OBSERVATION_QUALITY_INVALID:{provider_id}")
        if "normalized_value" not in row:
            raise ValueError(f"OBSERVATION_VALUE_REQUIRED:{provider_id}")
        by_provider[provider_id] = deepcopy(dict(row))
    return by_provider


def _agrees(left: Any, right: Any, tolerance: float) -> bool:
    numeric_left = isinstance(left, (int, float)) and not isinstance(left, bool)
    numeric_right = isinstance(right, (int, float)) and not isinstance(right, bool)
    if numeric_left and numeric_right:
        return abs(float(left) - float(right)) <= tolerance
    return _canonical(left) == _canonical(right)


def _best_agreement_group(valid_rows: Sequence[dict[str, Any]], *, tolerance: float) -> list[dict[str, Any]]:
    best: list[dict[str, Any]] = []
    for anchor in valid_rows:
        group = [row for row in valid_rows if _agrees(anchor["normalized_value"], row["normalized_value"], tolerance)]
        if len(group) > len(best):
            best = group
    return best


def _finalize_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") not in _TERMINAL_STATES:
        raise ValueError("QUORUM_TERMINAL_STATE_INVALID")
    result = deepcopy(payload)
    result["decision_id"] = _decision_id(result)
    return result


def evaluate_quorum(
    policy: Mapping[str, Any],
    route: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    identity_ambiguous: bool = False,
) -> dict[str, Any]:
    policy_result = validate_trust_policy(policy)
    _validate_route(route)

    field = str(route.get("field") or "").strip().lower()
    metric = str(route.get("semantic_metric_id") or "").strip().upper()
    fields = policy.get("fields") or {}
    if field not in fields:
        raise ValueError(f"TRUST_POLICY_FIELD_UNKNOWN:{field}")
    rule = fields[field]
    if str(rule.get("semantic_metric_id") or "").strip().upper() != metric:
        raise ValueError("TRUST_POLICY_ROUTE_SEMANTIC_METRIC_MISMATCH")

    eligible = [str(value) for value in (route.get("eligible_provider_ids") or [])]
    common = {
        "workstream": WORKSTREAM,
        "step": STEP,
        "sport": str(route.get("sport") or "").strip().lower(),
        "field": field,
        "semantic_metric_id": metric,
        "route_id": str(route.get("route_id") or ""),
        "trust_policy_id": policy_result["trust_policy_id"],
        "active_provider_ids": [],
        "selected_provider_ids": [],
        "rejected_attempts": [],
        "next_provider_ids": [],
        "accepted_value": None,
        "value_fingerprint": "",
        "minimum_quorum_satisfied": False,
        "early_stop": False,
        "expansion_reason": "",
        "routing_unit": ROUTING_UNIT,
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
    }

    if identity_ambiguous:
        return _finalize_decision({**common, "status": "AMBIGUOUS_IDENTITY_FAIL_CLOSED"})

    if route.get("status") != "ROUTE_READY" or not eligible:
        return _finalize_decision({**common, "status": "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"})

    by_provider = _observation_map(observations, eligible=eligible, semantic_metric_id=metric)
    active: list[str] = []
    rejected: list[dict[str, str]] = []
    valid: list[dict[str, Any]] = []
    max_age = int(rule["maximum_age_seconds"])
    min_quality = float(rule["minimum_accepted_quality"])
    min_quorum = int(rule["minimum_quorum_size"])
    tolerance = float(rule["disagreement_tolerance"])
    primary = str(route.get("primary_provider_id") or "")

    for provider_id in eligible:
        row = by_provider.get(provider_id)
        if row is None:
            continue
        active.append(provider_id)
        if float(row["age_seconds"]) > max_age:
            rejected.append({"provider_id": provider_id, "reason": "STALE_DATA"})
            continue
        if float(row["quality_score"]) < min_quality:
            rejected.append({"provider_id": provider_id, "reason": "LOW_QUALITY"})
            continue

        valid.append(row)
        if rule.get("single_authority_allowed") is True and provider_id == primary and min_quorum == 1:
            value = deepcopy(row["normalized_value"])
            return _finalize_decision({
                **common,
                "status": "ACCEPTED_SINGLE_AUTHORITY",
                "active_provider_ids": active,
                "selected_provider_ids": [provider_id],
                "rejected_attempts": rejected,
                "accepted_value": value,
                "value_fingerprint": _value_fingerprint(value),
                "minimum_quorum_satisfied": True,
                "early_stop": True,
            })

        group = _best_agreement_group(valid, tolerance=tolerance)
        if len(group) >= min_quorum:
            selected = [str(row["provider_id"]) for row in group[:min_quorum]]
            value = deepcopy(group[0]["normalized_value"])
            fallback_used = primary not in selected or bool(rejected)
            return _finalize_decision({
                **common,
                "status": "ACCEPTED_FALLBACK_QUORUM" if fallback_used else "ACCEPTED_QUORUM",
                "active_provider_ids": active,
                "selected_provider_ids": selected,
                "rejected_attempts": rejected,
                "accepted_value": value,
                "value_fingerprint": _value_fingerprint(value),
                "minimum_quorum_satisfied": True,
                "early_stop": True,
            })

    remaining = [provider_id for provider_id in eligible if provider_id not in by_provider]
    if remaining:
        if len(valid) >= 2:
            expansion_reason = "DISAGREEMENT"
        elif any(item["reason"] == "LOW_QUALITY" for item in rejected):
            expansion_reason = "LOW_QUALITY"
        elif any(item["reason"] == "STALE_DATA" for item in rejected):
            expansion_reason = "STALE_DATA"
        else:
            expansion_reason = "INSUFFICIENT_EVIDENCE"
        return _finalize_decision({
            **common,
            "status": "DISAGREEMENT_REQUIRES_EXPANSION",
            "active_provider_ids": active,
            "rejected_attempts": rejected,
            "next_provider_ids": remaining,
            "expansion_reason": expansion_reason,
        })

    if rejected and not valid and all(item["reason"] == "STALE_DATA" for item in rejected):
        status = "STALE_DATA_FAIL_CLOSED"
    else:
        status = "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"
    return _finalize_decision({
        **common,
        "status": status,
        "active_provider_ids": active,
        "rejected_attempts": rejected,
    })


__all__ = [
    "FREEZE_TOKEN",
    "PROGRAM_STEPS",
    "ROUTING_UNIT",
    "STEP",
    "VERSION",
    "WORKSTREAM",
    "evaluate_quorum",
    "load_trust_policy",
    "validate_trust_policy",
]
