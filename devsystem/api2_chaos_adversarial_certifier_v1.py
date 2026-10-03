"""API2 Control-Plane Efficiency V1 Step 6 — Chaos / Adversarial Certification.

Read-only certification layer over the frozen MONSTER V8 chaos harness and
API2 Step-5 state-aware proof contract.

It does not inject faults into GitHub or production. It deterministically
replays the proven control-plane crash matrix and certifies that API2 maps
adversarial conditions into stable WAIT / BLOCKED / FAILED / RECONCILING
states without duplicate execution, blind retries, or mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem import chaos_adversarial_certification_harness_v1 as monster_chaos
from devsystem import state_aware_proof_contract_v1 as state_aware

VERSION = "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP6_CHAOS_ADVERSARIAL_CERTIFICATION_V1"
EXPECTED_CHAOS_VERSION = "MONSTER_V8_CHAOS_ADVERSARIAL_CERTIFICATION_HARNESS_V1"
EXPECTED_STATE_AWARE_VERSION = (
    "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP5_STATE_AWARE_PROOF_CONTRACTS_V1"
)
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
BLIND_RETRY_ALLOWED = False


class Api2ChaosCertificationFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parents_green() -> None:
    if monster_chaos.VERSION != EXPECTED_CHAOS_VERSION:
        raise Api2ChaosCertificationFailure("frozen MONSTER chaos parent version drift")
    if state_aware.VERSION != EXPECTED_STATE_AWARE_VERSION:
        raise Api2ChaosCertificationFailure("frozen API2 Step-5 parent version drift")


def _api2_integration_matrix() -> dict[str, dict[str, Any]]:
    slow_a = state_aware.evaluate_state(
        "WAIT",
        {
            "wait_decision": "WAIT",
            "wait_state_token": "WAIT-SLOW-LIVE-001",
            "resume_trigger": "authoritative_run_terminal_or_state_token_changed",
            "event_driven_resume": True,
            "elapsed_seconds": 999,
            "poll_count": 1,
            "temporary_selector_present": False,
        },
    )
    slow_b = state_aware.evaluate_state(
        "WAIT",
        {
            "wait_decision": "WAIT",
            "wait_state_token": "WAIT-SLOW-LIVE-001",
            "resume_trigger": "authoritative_run_terminal_or_state_token_changed",
            "event_driven_resume": True,
            "elapsed_seconds": 9999,
            "poll_count": 999,
            "temporary_selector_present": True,
        },
    )

    frozen_edit = state_aware.evaluate_state(
        "BLOCKED",
        {
            "blocker": "FROZEN_ARTIFACT_EDIT_WITHOUT_EXACT_THAW",
            "next_legal_action": "ABORT_OR_ACQUIRE_EXACT_AUTHORITATIVE_THAW",
            "mutation_allowed": False,
            "observed_blob": "drift",
        },
    )

    deployment_drift = state_aware.evaluate_state(
        "FAILED",
        {
            "terminal_failure": True,
            "failure_domain": "DEPLOYMENT",
            "root_cause_fingerprint": "ROOT-DEPLOYMENT-SHA-DRIFT",
            "next_legal_action": "RECONCILE_DEPLOYMENT_OWNER",
            "product_patch_requested": True,
        },
    )

    reconciling = state_aware.evaluate_state(
        "RECONCILING",
        {
            "reconciliation_decision": "AUTO_RECONCILIATION_PLANNED",
            "apply_allowed": True,
            "previous_state_hash": "1" * 64,
            "next_state_hash": "2" * 64,
            "retry_after_state_change_only": True,
            "duplicate_retry_requested": True,
        },
    )

    return {
        "slow_live_run_is_wait_not_fail": {
            "passed": (
                slow_a["valid_state"] is True
                and slow_a["green_eligible"] is False
                and slow_a["rerun_allowed"] is False
                and slow_a["blind_polling_allowed"] is False
            ),
            "recovery": "WAIT_FOR_AUTHORITATIVE_TERMINAL_OR_STATE_EVENT",
            "evidence": slow_a["contract_fingerprint"],
        },
        "transient_noise_is_idempotent": {
            "passed": slow_a["contract_fingerprint"] == slow_b["contract_fingerprint"],
            "recovery": "KEEP_SINGLE_AUTHORITATIVE_WAIT_IDENTITY",
            "evidence": slow_b["contract_fingerprint"],
        },
        "frozen_edit_blocks_mutation": {
            "passed": (
                frozen_edit["valid_state"] is True
                and frozen_edit["mutation_authority_granted"] is False
                and frozen_edit["green_eligible"] is False
            ),
            "recovery": "REQUIRE_EXACT_THAW_OR_ABORT",
            "evidence": frozen_edit["contract_fingerprint"],
        },
        "deployment_drift_stays_nonproduct_owned": {
            "passed": (
                deployment_drift["valid_state"] is True
                and deployment_drift["green_eligible"] is False
                and deployment_drift["stable_evidence"]["failure_domain"] == "DEPLOYMENT"
                and deployment_drift["mutation_authority_granted"] is False
            ),
            "recovery": "RECONCILE_DEPLOYMENT_OWNER",
            "evidence": deployment_drift["contract_fingerprint"],
        },
        "reconciliation_allows_one_state_progress_retry": {
            "passed": (
                reconciling["valid_state"] is True
                and reconciling["rerun_allowed"] is True
                and reconciling["mutation_authority_granted"] is False
            ),
            "recovery": "ONE_RETRY_AFTER_STATE_HASH_PROGRESS",
            "evidence": reconciling["contract_fingerprint"],
        },
    }


def run_certification() -> dict[str, Any]:
    _parents_green()

    chaos = monster_chaos.contract_self_test()
    if chaos.get("status") != "GREEN":
        raise Api2ChaosCertificationFailure("MONSTER chaos harness is not GREEN")
    if chaos.get("scenario_count") != 11 or chaos.get("all_scenarios_pass") is not True:
        raise Api2ChaosCertificationFailure("MONSTER chaos matrix incomplete")

    step5 = state_aware.self_test()
    if step5.get("status") != "GREEN":
        raise Api2ChaosCertificationFailure("API2 Step-5 state-aware proof is not GREEN")

    integration = _api2_integration_matrix()
    failed = sorted(name for name, result in integration.items() if result["passed"] is not True)
    if failed:
        raise Api2ChaosCertificationFailure("API2 integration scenarios failed: " + ", ".join(failed))

    safety = {
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "blind_retry_allowed": BLIND_RETRY_ALLOWED,
        "step_2a_preserved": chaos.get("step_2a_preserved") is True,
        "duplicate_merge_blocked": chaos.get("duplicate_merge_blocked") is True,
        "detached_resume_no_duplicate": chaos.get("detached_resume_no_duplicate") is True,
        "slow_live_run_protected": chaos.get("slow_live_run_protected") is True,
    }
    if any(
        (
            safety["network_calls"],
            safety["auto_mutate"],
            safety["may_modify_product_runtime"],
            safety["mutation_authority_granted"],
            safety["blind_retry_allowed"],
        )
    ):
        raise Api2ChaosCertificationFailure("read-only safety boundary drift")
    if not all(
        safety[key]
        for key in (
            "step_2a_preserved",
            "duplicate_merge_blocked",
            "detached_resume_no_duplicate",
            "slow_live_run_protected",
        )
    ):
        raise Api2ChaosCertificationFailure("adversarial safety dependency failed")

    core = {
        "version": VERSION,
        "parent_versions": {
            "monster_chaos": monster_chaos.VERSION,
            "api2_state_aware": state_aware.VERSION,
        },
        "monster_chaos_digest": chaos["chaos_certificate_digest"],
        "monster_scenario_count": chaos["scenario_count"],
        "api2_integration_scenarios": integration,
        "safety": safety,
    }
    return {
        "status": "GREEN",
        **core,
        "api2_integration_scenario_count": len(integration),
        "combined_scenario_count": int(chaos["scenario_count"]) + len(integration),
        "all_scenarios_pass": True,
        "certification_digest": _digest(core),
    }


def validate_certificate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise Api2ChaosCertificationFailure("certificate must be an object")
    cert = deepcopy(dict(payload))
    if cert.get("version") != VERSION or cert.get("status") != "GREEN":
        raise Api2ChaosCertificationFailure("certificate version/status mismatch")
    if cert.get("monster_scenario_count") != 11:
        raise Api2ChaosCertificationFailure("base chaos scenario count mismatch")
    if cert.get("api2_integration_scenario_count") != 5:
        raise Api2ChaosCertificationFailure("API2 integration scenario count mismatch")
    if cert.get("combined_scenario_count") != 16:
        raise Api2ChaosCertificationFailure("combined scenario count mismatch")
    if cert.get("all_scenarios_pass") is not True:
        raise Api2ChaosCertificationFailure("not every adversarial scenario passed")

    core = {
        "version": cert["version"],
        "parent_versions": cert["parent_versions"],
        "monster_chaos_digest": cert["monster_chaos_digest"],
        "monster_scenario_count": cert["monster_scenario_count"],
        "api2_integration_scenarios": cert["api2_integration_scenarios"],
        "safety": cert["safety"],
    }
    if cert.get("certification_digest") != _digest(core):
        raise Api2ChaosCertificationFailure("certificate digest mismatch")
    return cert


def self_test() -> dict[str, Any]:
    cert = run_certification()
    validate_certificate(cert)

    tampered = deepcopy(cert)
    tampered["api2_integration_scenarios"]["slow_live_run_is_wait_not_fail"]["passed"] = False
    tamper_blocked = False
    try:
        validate_certificate(tampered)
    except Api2ChaosCertificationFailure:
        tamper_blocked = True
    if not tamper_blocked:
        raise Api2ChaosCertificationFailure("tampered certificate was accepted")

    return {
        "status": "GREEN",
        "version": VERSION,
        "base_chaos_scenarios": cert["monster_scenario_count"],
        "api2_integration_scenarios": cert["api2_integration_scenario_count"],
        "combined_scenarios": cert["combined_scenario_count"],
        "all_scenarios_pass": cert["all_scenarios_pass"],
        "slow_live_wait_protected": cert["api2_integration_scenarios"]["slow_live_run_is_wait_not_fail"]["passed"],
        "transient_noise_idempotent": cert["api2_integration_scenarios"]["transient_noise_is_idempotent"]["passed"],
        "frozen_edit_blocks_mutation": cert["api2_integration_scenarios"]["frozen_edit_blocks_mutation"]["passed"],
        "deployment_drift_nonproduct_owned": cert["api2_integration_scenarios"]["deployment_drift_stays_nonproduct_owned"]["passed"],
        "one_retry_after_registry_progress": cert["api2_integration_scenarios"]["reconciliation_allows_one_state_progress_retry"]["passed"],
        "tamper_evident_certificate": tamper_blocked,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "blind_retry_allowed": BLIND_RETRY_ALLOWED,
        "certification_digest": cert["certification_digest"],
    }


def main() -> int:
    result = self_test()
    print("API2_CONTROL_PLANE_EFFICIENCY_V1_STEP6_CHAOS_ADVERSARIAL_CERTIFICATION_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Api2ChaosCertificationFailure as exc:
        print(
            "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP6_BLOCKED: " + str(exc),
            file=sys.stderr,
        )
        raise SystemExit(1)
