"""MONSTER V8 Step 6 — Chaos / Adversarial Certification Harness V1.

Deterministic crash-test layer for the frozen MONSTER control plane.

The harness does not create chaos in GitHub or production. It replays the
already-frozen pure state-machine adversarial simulations and requires the
expected fail-closed/recovery behavior across workstream arbitration, Step 2A,
transactional rollback, queue handoff, ownership monotonicity, frozen artifacts,
deployment truth, dead-man recovery, replay locking, detached continuation, and
adaptive stuck thresholds.

No network calls. No product/runtime mutation. No mutation authority.
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

from devsystem import adaptive_stuck_thresholds_v1 as adaptive
from devsystem import atomic_wait_queue_lease_handoff_v1 as queue
from devsystem import cross_workstream_intent_arbiter_v1 as intents
from devsystem import deployment_truth_control_plane_v1 as deployment
from devsystem import detached_execution_continuation_v1 as detached
from devsystem import execution_heartbeat_deadman_recovery_v1 as heartbeat
from devsystem import frozen_artifact_registry_v1 as frozen
from devsystem import mandatory_2a_adversarial_certification_v1 as two_a
from devsystem import mandatory_2a_replay_lock_v1 as replay
from devsystem import monotonic_state_ownership_guard_v1 as ownership
from devsystem import transactional_rollback_engine_v1 as rollback

VERSION = "MONSTER_V8_CHAOS_ADVERSARIAL_CERTIFICATION_HARNESS_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

EXPECTED_DEPENDENCY_VERSIONS = {
    "cross_workstream_intent_arbiter": "MONSTER_V8_CROSS_WORKSTREAM_INTENT_ARBITER_V1",
    "two_a_adversarial": "MONSTER_2A_ADVERSARIAL_CERTIFICATION_V1",
    "transactional_rollback": "MONSTER_V8_TRANSACTIONAL_ROLLBACK_ENGINE_V1",
    "atomic_wait_queue": "MONSTER_V7_ATOMIC_WAIT_QUEUE_LEASE_HANDOFF_V1",
    "monotonic_ownership": "MONSTER_V7_MONOTONIC_STATE_OWNERSHIP_GUARD_V1",
    "frozen_artifact_registry": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
    "deployment_truth": "MONSTER_DEPLOYMENT_TRUTH_CONTROL_PLANE_V1",
    "heartbeat_deadman": "MONSTER_V5_EXECUTION_HEARTBEAT_DEADMAN_RECOVERY_V1",
    "replay_lock": "MONSTER_2A_REPLAY_LOOP_LOCK_V1",
    "detached_continuation": "MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_V1",
    "adaptive_stuck_thresholds": "MONSTER_V8_ADAPTIVE_STUCK_THRESHOLDS_V1",
}

DEPENDENCY_MODULES = {
    "cross_workstream_intent_arbiter": intents,
    "two_a_adversarial": two_a,
    "transactional_rollback": rollback,
    "atomic_wait_queue": queue,
    "monotonic_ownership": ownership,
    "frozen_artifact_registry": frozen,
    "deployment_truth": deployment,
    "heartbeat_deadman": heartbeat,
    "replay_lock": replay,
    "detached_continuation": detached,
    "adaptive_stuck_thresholds": adaptive,
}

SCENARIO_MANIFEST = {
    "duplicate_chats": {
        "fault": "two chats submit the same semantic mission",
        "expected": "join the existing canonical intent; no duplicate branch/lease",
    },
    "stale_sha": {
        "fault": "worker acts from stale main/head identity",
        "expected": "Step 2A firewall blocks and requires repository revalidation",
    },
    "dropped_connection_after_mutation": {
        "fault": "mutation/restore outcome response is lost or delayed",
        "expected": "no duplicate restore; recover from authoritative state and recertify",
    },
    "partial_queue_acknowledgement": {
        "fault": "lease handoff commits but queue acknowledgement is delayed",
        "expected": "reconcile idempotently from live lease ticket identity",
    },
    "old_writer_wakeup": {
        "fault": "older upstream writer wakes after newer downstream ownership",
        "expected": "stale ownership epoch is blocked before mutation",
    },
    "frozen_file_edit": {
        "fault": "frozen artifact changes without exact-head thaw",
        "expected": "frozen registry fails closed",
    },
    "deployment_drift": {
        "fault": "production SHA differs from GitHub main",
        "expected": "classify as deployment-owned stale deployment; block product patch",
    },
    "dead_runner": {
        "fault": "worker heartbeat expires after authoritative run is terminal",
        "expected": "single recovery handoff allowed, but Step 2A and new scope lease remain required",
    },
    "duplicate_merge_attempt": {
        "fault": "same semantic merge action is attempted again",
        "expected": "replay lock converts it to LOOP_SKIPPED_CONTINUE",
    },
    "slow_live_run": {
        "fault": "run exceeds learned threshold while authoritative run remains active",
        "expected": "do not call it stuck and do not start a duplicate run",
    },
    "detached_worker_resume": {
        "fault": "chat/worker disappears while authoritative async work is still live",
        "expected": "durable continuation resumes as WAIT, never duplicate",
    },
}


class ChaosCertificationFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _require_green(name: str, result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping) or result.get("status") != "GREEN":
        raise ChaosCertificationFailure(f"{name} dependency self-test is not GREEN")
    return deepcopy(dict(result))


def _dependency_results() -> dict[str, dict[str, Any]]:
    actual = {
        name: str(module.VERSION)
        for name, module in DEPENDENCY_MODULES.items()
    }
    if actual != EXPECTED_DEPENDENCY_VERSIONS:
        raise ChaosCertificationFailure(
            "dependency version drift: "
            + _canonical({"expected": EXPECTED_DEPENDENCY_VERSIONS, "actual": actual})
        )

    return {
        "cross_workstream_intent_arbiter": _require_green(
            "cross_workstream_intent_arbiter", intents.contract_self_test()
        ),
        "two_a_adversarial": _require_green(
            "two_a_adversarial", two_a.contract_self_test()
        ),
        "transactional_rollback": _require_green(
            "transactional_rollback", rollback.contract_self_test()
        ),
        "atomic_wait_queue": _require_green(
            "atomic_wait_queue", queue.contract_self_test()
        ),
        "monotonic_ownership": _require_green(
            "monotonic_ownership", ownership.contract_self_test()
        ),
        "frozen_artifact_registry": _require_green(
            "frozen_artifact_registry", frozen.contract_self_test()
        ),
        "deployment_truth": _require_green(
            "deployment_truth", deployment.contract_self_test()
        ),
        "heartbeat_deadman": _require_green(
            "heartbeat_deadman", heartbeat.contract_self_test()
        ),
        "replay_lock": _require_green(
            "replay_lock", replay.contract_self_test()
        ),
        "detached_continuation": _require_green(
            "detached_continuation", detached.contract_self_test()
        ),
        "adaptive_stuck_thresholds": _require_green(
            "adaptive_stuck_thresholds", adaptive.contract_self_test()
        ),
    }


def run_chaos_matrix() -> dict[str, Any]:
    dep = _dependency_results()

    scenarios = {
        "duplicate_chats": {
            "passed": (
                dep["cross_workstream_intent_arbiter"]["semantic_duplicate_joins"] is True
            ),
            "evidence": "semantic_duplicate_joins",
            "recovery": "JOIN_EXISTING_INTENT",
        },
        "stale_sha": {
            "passed": (
                dep["two_a_adversarial"]["attacks"]["stale_main_blocked"] is True
                and dep["two_a_adversarial"]["attacks"]["stale_head_blocked"] is True
            ),
            "evidence": "stale_main_blocked + stale_head_blocked",
            "recovery": "REVALIDATE_REPOSITORY_IDENTITY",
        },
        "dropped_connection_after_mutation": {
            "passed": (
                dep["transactional_rollback"]["duplicate_restore_suppressed"] is True
                and dep["transactional_rollback"]["restoration_requires_recertification"] is True
                and dep["transactional_rollback"]["rollback_closes_only_after_green_recertification"] is True
            ),
            "evidence": "duplicate restore suppression + mandatory rollback recertification",
            "recovery": "REREAD_AUTHORITATIVE_SURFACE_THEN_RECERTIFY",
        },
        "partial_queue_acknowledgement": {
            "passed": (
                dep["atomic_wait_queue"]["delayed_queue_ack_reconciles_from_lease"] is True
                and dep["atomic_wait_queue"]["ticket_identity_carried_into_lease"] is True
            ),
            "evidence": "delayed_queue_ack_reconciles_from_lease",
            "recovery": "WAIT_QUEUE_HANDOFF_RECONCILED",
        },
        "old_writer_wakeup": {
            "passed": (
                dep["monotonic_ownership"]["older_upstream_writer_blocked"] is True
                and dep["monotonic_ownership"]["blocked_write_routes_to_backtrace"] is True
            ),
            "evidence": "older_upstream_writer_blocked",
            "recovery": "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE",
        },
        "frozen_file_edit": {
            "passed": (
                dep["frozen_artifact_registry"]["mismatch_without_thaw_blocked"] is True
                and dep["frozen_artifact_registry"]["wrong_head_thaw_blocked"] is True
            ),
            "evidence": "mismatch_without_thaw_blocked + wrong_head_thaw_blocked",
            "recovery": "REQUIRE_EXACT_AUTHORITATIVE_THAW_OR_ABORT",
        },
        "deployment_drift": {
            "passed": (
                dep["deployment_truth"]["stale_deployment_classification"] is True
                and dep["deployment_truth"]["product_patch_blocked_on_deployment_failure"] is True
            ),
            "evidence": "stale_deployment_classification",
            "recovery": "DEPLOYMENT_OWNER_RECONCILIATION",
        },
        "dead_runner": {
            "passed": (
                dep["heartbeat_deadman"]["dead_worker_terminal_run_recoverable"] is True
                and dep["heartbeat_deadman"]["takeover_never_grants_mutation"] is True
                and dep["heartbeat_deadman"]["step_2a_remains_mandatory"] is True
                and dep["heartbeat_deadman"]["scope_lease_remains_mandatory"] is True
                and dep["heartbeat_deadman"]["recovery_receipt_one_shot"] is True
            ),
            "evidence": "dead-worker recovery receipt remains one-shot/non-authoritative",
            "recovery": "ISSUE_ONE_SHOT_RECOVERY_RECEIPT_THEN_REENTER_STEP2A",
        },
        "duplicate_merge_attempt": {
            "passed": (
                dep["replay_lock"]["exact_receipt_replay_skipped"] is True
                and dep["replay_lock"]["new_receipt_same_action_skipped"] is True
                and dep["replay_lock"]["autonomous_skip_no_user"] is True
            ),
            "evidence": "same semantic merge cannot execute twice",
            "recovery": "LOOP_SKIPPED_CONTINUE",
        },
        "slow_live_run": {
            "passed": (
                dep["adaptive_stuck_thresholds"]["live_authoritative_run_protected"] is True
                and dep["adaptive_stuck_thresholds"]["abnormal_stall_detected"] is True
            ),
            "evidence": "adaptive threshold distinguishes slow-live from abnormal stall",
            "recovery": "WAIT_FOR_TERMINAL_EVENT_WHILE_RUN_IS_LIVE",
        },
        "detached_worker_resume": {
            "passed": (
                dep["detached_continuation"]["live_async_waits_without_duplicate"] is True
                and dep["detached_continuation"]["worker_handoff_is_cas_bound"] is True
            ),
            "evidence": "detached continuation is CAS-bound and live async stays WAIT",
            "recovery": "DETACHED_WAIT_AUTHORITATIVE_ASYNC",
        },
    }

    for scenario_id, details in scenarios.items():
        if scenario_id not in SCENARIO_MANIFEST:
            raise ChaosCertificationFailure(f"unregistered chaos scenario: {scenario_id}")
        if details["passed"] is not True:
            raise ChaosCertificationFailure(f"chaos scenario failed: {scenario_id}")

    safety = {
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "all_dependency_safety_green": all(
            result.get("product_runtime_mutation") is False
            for result in dep.values()
            if "product_runtime_mutation" in result
        ),
    }
    if (
        safety["network_calls"]
        or safety["auto_mutate"]
        or safety["may_modify_product_runtime"]
        or safety["mutation_authority_granted"]
        or not safety["all_dependency_safety_green"]
    ):
        raise ChaosCertificationFailure("chaos harness safety invariant failed")

    proof_core = {
        "version": VERSION,
        "dependency_versions": EXPECTED_DEPENDENCY_VERSIONS,
        "scenario_manifest": SCENARIO_MANIFEST,
        "scenarios": scenarios,
        "safety": safety,
    }
    return {
        "status": "GREEN",
        **proof_core,
        "scenario_count": len(scenarios),
        "passed_scenario_count": sum(
            1 for details in scenarios.values() if details["passed"] is True
        ),
        "all_scenarios_pass": all(
            details["passed"] is True for details in scenarios.values()
        ),
        "step_2a_preserved": True,
        "frozen_prior_steps_preserved": True,
        "chaos_certificate_digest": "sha256:" + _digest(proof_core),
    }


def validate_certificate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ChaosCertificationFailure("certificate must be an object")
    cert = deepcopy(dict(payload))
    if cert.get("version") != VERSION or cert.get("status") != "GREEN":
        raise ChaosCertificationFailure("certificate version/status mismatch")
    if cert.get("scenario_count") != len(SCENARIO_MANIFEST):
        raise ChaosCertificationFailure("certificate scenario count mismatch")
    if cert.get("passed_scenario_count") != cert.get("scenario_count"):
        raise ChaosCertificationFailure("certificate does not pass every scenario")
    if cert.get("all_scenarios_pass") is not True:
        raise ChaosCertificationFailure("certificate all_scenarios_pass false")
    if cert.get("step_2a_preserved") is not True:
        raise ChaosCertificationFailure("Step 2A preservation missing")
    if cert.get("frozen_prior_steps_preserved") is not True:
        raise ChaosCertificationFailure("frozen prior-step preservation missing")

    core = {
        "version": cert["version"],
        "dependency_versions": cert["dependency_versions"],
        "scenario_manifest": cert["scenario_manifest"],
        "scenarios": cert["scenarios"],
        "safety": cert["safety"],
    }
    expected = "sha256:" + _digest(core)
    if cert.get("chaos_certificate_digest") != expected:
        raise ChaosCertificationFailure("chaos certificate digest mismatch")
    return cert


def contract_self_test() -> dict[str, Any]:
    cert = run_chaos_matrix()
    validate_certificate(cert)

    tampered = deepcopy(cert)
    tampered["scenarios"]["duplicate_merge_attempt"]["passed"] = False
    tamper_blocked = False
    try:
        validate_certificate(tampered)
    except ChaosCertificationFailure:
        tamper_blocked = True
    if not tamper_blocked:
        raise ChaosCertificationFailure("tampered chaos certificate was accepted")

    return {
        "status": "GREEN",
        "version": VERSION,
        "scenario_count": cert["scenario_count"],
        "all_scenarios_pass": cert["all_scenarios_pass"],
        "duplicate_chats_recovered": cert["scenarios"]["duplicate_chats"]["passed"],
        "stale_sha_blocked": cert["scenarios"]["stale_sha"]["passed"],
        "dropped_connection_recovered": cert["scenarios"]["dropped_connection_after_mutation"]["passed"],
        "partial_queue_ack_reconciled": cert["scenarios"]["partial_queue_acknowledgement"]["passed"],
        "old_writer_blocked": cert["scenarios"]["old_writer_wakeup"]["passed"],
        "frozen_file_edit_blocked": cert["scenarios"]["frozen_file_edit"]["passed"],
        "deployment_drift_classified": cert["scenarios"]["deployment_drift"]["passed"],
        "dead_runner_recoverable": cert["scenarios"]["dead_runner"]["passed"],
        "duplicate_merge_blocked": cert["scenarios"]["duplicate_merge_attempt"]["passed"],
        "slow_live_run_protected": cert["scenarios"]["slow_live_run"]["passed"],
        "detached_resume_no_duplicate": cert["scenarios"]["detached_worker_resume"]["passed"],
        "tamper_evident_certificate": tamper_blocked,
        "step_2a_preserved": cert["step_2a_preserved"],
        "frozen_prior_steps_preserved": cert["frozen_prior_steps_preserved"],
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "chaos_certificate_digest": cert["chaos_certificate_digest"],
    }


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V8_STEP6_CHAOS_ADVERSARIAL_CERTIFICATION_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ChaosCertificationFailure as exc:
        print("MONSTER_V8_STEP6_CHAOS_ADVERSARIAL_CERTIFICATION_BLOCKED: " + str(exc))
        raise SystemExit(1)
