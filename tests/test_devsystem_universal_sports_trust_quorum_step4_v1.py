import copy
import hashlib
import json
from pathlib import Path

import pytest

from devsystem.universal_sports_trust_quorum_v1 import (
    FREEZE_TOKEN,
    STEP,
    WORKSTREAM,
    evaluate_quorum,
    load_trust_policy,
    validate_trust_policy,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "devsystem" / "contracts" / "universal-sports-trust-quorum-v1.json"


def _policy():
    return load_trust_policy(POLICY_PATH)


def _route(*, field="schedule", metric="SCHEDULE", eligible=None, primary=None, status="ROUTE_READY"):
    eligible = list(eligible or ["nba_official", "espn", "cbs_sports"])
    base = {
        "status": status,
        "sport": "nba",
        "field": field,
        "semantic_metric_id": metric,
        "primary_provider_id": primary if primary is not None else (eligible[0] if eligible else ""),
        "fallback_provider_ids": eligible[1:],
        "eligible_provider_ids": eligible,
        "blocked_providers": [],
        "active_provider_ids": [],
        "routing_unit": "DATA_FIELD",
        "page_wide_source_authority": False,
        "network_calls": False,
        "fabrication": False,
        "router_id": "USFR-TEST",
        "registry_id": "USPR-TEST",
    }
    canonical = json.dumps(base, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {**base, "route_id": "ROUTE-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24].upper()}


def _obs(provider, metric, value, *, age=10, quality=1.0):
    return {
        "provider_id": provider,
        "semantic_metric_id": metric,
        "normalized_value": value,
        "age_seconds": age,
        "quality_score": quality,
    }


def test_valid_policy_certifies_step4_contract():
    result = validate_trust_policy(_policy())
    assert result["status"] == "GREEN"
    assert result["workstream"] == WORKSTREAM == "universal-sports-source-finalization-v1"
    assert result["step"] == STEP == "4/8"
    assert result["routing_unit"] == "DATA_FIELD"
    assert result["minimum_quorum_early_stop"] is True
    assert result["active_provider_semantics"] == "ACTUALLY_CONSULTED_ONLY"
    assert result["page_wide_source_authority"] is False
    assert result["network_calls"] is False
    assert result["github_actions_fallback"] == 0
    assert result["field_policy_count"] == 15
    assert result["freeze_token"] == FREEZE_TOKEN


def test_single_official_authority_stops_after_one_fresh_high_quality_value():
    decision = evaluate_quorum(
        _policy(),
        _route(),
        [_obs("nba_official", "SCHEDULE", {"games": [1, 2]}), _obs("espn", "SCHEDULE", {"games": [1, 2]})],
    )
    assert decision["status"] == "ACCEPTED_SINGLE_AUTHORITY"
    assert decision["selected_provider_ids"] == ["nba_official"]
    assert decision["active_provider_ids"] == ["nba_official"]
    assert decision["next_provider_ids"] == []
    assert decision["minimum_quorum_satisfied"] is True
    assert decision["early_stop"] is True


def test_injuries_requires_two_agreeing_sources_and_stops_before_third():
    route = _route(field="injuries", metric="INJURIES", eligible=["nba_official", "official_team_sites", "espn"])
    value = [{"player": "A", "status": "OUT"}]
    decision = evaluate_quorum(
        _policy(), route,
        [_obs("nba_official", "INJURIES", value), _obs("official_team_sites", "INJURIES", value), _obs("espn", "INJURIES", value)],
    )
    assert decision["status"] == "ACCEPTED_QUORUM"
    assert decision["selected_provider_ids"] == ["nba_official", "official_team_sites"]
    assert decision["active_provider_ids"] == ["nba_official", "official_team_sites"]
    assert decision["early_stop"] is True


def test_stale_primary_can_escalate_to_fallback_quorum():
    route = _route(field="injuries", metric="INJURIES", eligible=["nba_official", "official_team_sites", "espn"])
    value = [{"player": "A", "status": "QUESTIONABLE"}]
    decision = evaluate_quorum(
        _policy(), route,
        [
            _obs("nba_official", "INJURIES", value, age=999999),
            _obs("official_team_sites", "INJURIES", value),
            _obs("espn", "INJURIES", value),
        ],
    )
    assert decision["status"] == "ACCEPTED_FALLBACK_QUORUM"
    assert decision["selected_provider_ids"] == ["official_team_sites", "espn"]
    assert decision["active_provider_ids"] == ["nba_official", "official_team_sites", "espn"]
    assert decision["rejected_attempts"] == [{"provider_id": "nba_official", "reason": "STALE_DATA"}]


def test_disagreement_requests_only_remaining_compatible_provider():
    route = _route(field="injuries", metric="INJURIES", eligible=["nba_official", "official_team_sites", "espn"])
    decision = evaluate_quorum(
        _policy(), route,
        [
            _obs("nba_official", "INJURIES", [{"player": "A", "status": "OUT"}]),
            _obs("official_team_sites", "INJURIES", [{"player": "A", "status": "ACTIVE"}]),
        ],
    )
    assert decision["status"] == "DISAGREEMENT_REQUIRES_EXPANSION"
    assert decision["active_provider_ids"] == ["nba_official", "official_team_sites"]
    assert decision["next_provider_ids"] == ["espn"]
    assert decision["expansion_reason"] == "DISAGREEMENT"


def test_exhausted_disagreement_fails_closed_instead_of_blending_values():
    route = _route(field="injuries", metric="INJURIES", eligible=["nba_official", "official_team_sites"])
    decision = evaluate_quorum(
        _policy(), route,
        [
            _obs("nba_official", "INJURIES", [{"player": "A", "status": "OUT"}]),
            _obs("official_team_sites", "INJURIES", [{"player": "A", "status": "ACTIVE"}]),
        ],
    )
    assert decision["status"] == "UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION"
    assert decision["selected_provider_ids"] == []
    assert decision["fabrication"] is False


def test_all_stale_sources_fail_closed_as_stale():
    route = _route(field="schedule", metric="SCHEDULE", eligible=["nba_official"])
    decision = evaluate_quorum(_policy(), route, [_obs("nba_official", "SCHEDULE", {"games": []}, age=999999)])
    assert decision["status"] == "STALE_DATA_FAIL_CLOSED"
    assert decision["selected_provider_ids"] == []


def test_ambiguous_identity_fails_closed_without_consulting_providers():
    decision = evaluate_quorum(_policy(), _route(), [], identity_ambiguous=True)
    assert decision["status"] == "AMBIGUOUS_IDENTITY_FAIL_CLOSED"
    assert decision["active_provider_ids"] == []
    assert decision["selected_provider_ids"] == []


def test_off_route_provider_is_rejected_not_counted_toward_quorum():
    with pytest.raises(ValueError, match="OFF_ROUTE_PROVIDER"):
        evaluate_quorum(_policy(), _route(), [_obs("action_network", "SCHEDULE", {"games": []})])


def test_semantic_metric_mismatch_fails_closed():
    with pytest.raises(ValueError, match="SEMANTIC_METRIC_MISMATCH"):
        evaluate_quorum(_policy(), _route(), [_obs("nba_official", "PUBLIC_BET_PERCENTAGE", 51.0)])


def test_low_quality_primary_expands_to_remaining_route():
    decision = evaluate_quorum(_policy(), _route(), [_obs("nba_official", "SCHEDULE", {"games": []}, quality=0.1)])
    assert decision["status"] == "DISAGREEMENT_REQUIRES_EXPANSION"
    assert decision["expansion_reason"] == "LOW_QUALITY"
    assert decision["next_provider_ids"] == ["espn", "cbs_sports"]


def test_numeric_tolerance_can_form_market_quorum_without_value_blending():
    route = _route(field="public_bet_percentage", metric="PUBLIC_BET_PERCENTAGE", eligible=["action_network", "covers", "vsin"])
    decision = evaluate_quorum(
        _policy(), route,
        [_obs("action_network", "PUBLIC_BET_PERCENTAGE", 52.0), _obs("covers", "PUBLIC_BET_PERCENTAGE", 53.0)],
    )
    assert decision["status"] == "ACCEPTED_QUORUM"
    assert decision["selected_provider_ids"] == ["action_network", "covers"]
    assert decision["accepted_value"] == 52.0


def test_decision_id_is_deterministic_and_value_sensitive():
    route = _route()
    first = evaluate_quorum(_policy(), route, [_obs("nba_official", "SCHEDULE", {"games": [1]})])
    second = evaluate_quorum(_policy(), route, [_obs("nba_official", "SCHEDULE", {"games": [1]})])
    changed = evaluate_quorum(_policy(), route, [_obs("nba_official", "SCHEDULE", {"games": [2]})])
    assert first["decision_id"] == second["decision_id"]
    assert first["decision_id"] != changed["decision_id"]


def test_tampered_step3_route_fingerprint_fails_closed_before_provider_acceptance():
    route = _route()
    route["eligible_provider_ids"] = ["action_network", "espn", "cbs_sports"]
    route["primary_provider_id"] = "action_network"
    route["fallback_provider_ids"] = ["espn", "cbs_sports"]
    with pytest.raises(ValueError, match="ROUTE_FINGERPRINT_MISMATCH"):
        evaluate_quorum(_policy(), route, [_obs("action_network", "SCHEDULE", {"games": []})])


def test_unused_malformed_fallback_does_not_break_valid_primary_early_stop():
    decision = evaluate_quorum(
        _policy(),
        _route(),
        [
            _obs("nba_official", "SCHEDULE", {"games": [1]}),
            _obs("espn", "PUBLIC_BET_PERCENTAGE", 51.0),
        ],
    )
    assert decision["status"] == "ACCEPTED_SINGLE_AUTHORITY"
    assert decision["active_provider_ids"] == ["nba_official"]
    assert decision["selected_provider_ids"] == ["nba_official"]


def test_nan_observation_age_is_rejected():
    with pytest.raises(ValueError, match="OBSERVATION_AGE_INVALID"):
        evaluate_quorum(_policy(), _route(), [_obs("nba_official", "SCHEDULE", {"games": []}, age=float("nan"))])


def test_tampered_policy_fingerprint_fails_closed():
    policy = _policy()
    broken = copy.deepcopy(policy)
    broken["fields"]["injuries"]["minimum_accepted_quality"] = 0.91
    with pytest.raises(ValueError, match="TRUST_POLICY_FINGERPRINT_MISMATCH"):
        validate_trust_policy(broken)
