from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    target = ROOT / path
    spec = importlib.util.spec_from_file_location(name, target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_permanent_contract_is_green():
    module = _load("permanent_gate_v1", "devsystem/permanent_gate_v1.py")
    result = module.validate()
    assert result["status"] == "GREEN"
    assert result["active_domains"] == ["cfb", "mlb", "nfl", "wnba"]
    assert "nfl" not in result["blocked_until_activated"]
    assert result["critical_test_count"] == 19
    assert result["api_observability_permanent"] is True
    assert result["predictive_failure_triage_permanent"] is True
    assert result["automatic_failure_evidence_wiring_permanent"] is True
    assert result["failed_job_log_evidence_permanent"] is True
    assert result["failure_remediation_policy_permanent"] is True
    assert result["stable_failure_fingerprint_permanent"] is True
    assert result["failure_packet_self_health_permanent"] is True
    assert result["failure_recurrence_history_permanent"] is True
    assert result["failure_recurrence_chronology_permanent"] is True
    assert result["failure_recurrence_age_permanent"] is True
    assert result["failure_history_coverage_permanent"] is True
    assert result["forward_motion_v2_permanent"] is True
    assert result["forward_motion_v2_pr_enforcement"] is True
    assert result["persistent_execution_brain_v1_permanent"] is True
    assert result["automatic_loop_kill_v1_permanent"] is True
    assert result["mandatory_2a_action_gate_v1_permanent"] is True
    assert result["mandatory_2a_receipt_v1_permanent"] is True
    assert result["mandatory_2a_replay_lock_v1_permanent"] is True
    assert result["mandatory_2a_global_enforcement_v1_permanent"] is True
    assert result["mandatory_2a_adversarial_certification_v1_permanent"] is True
    assert result["distributed_execution_lease_v1_permanent"] is True
    assert result["semantic_action_normalizer_v1_permanent"] is True
    assert result["frozen_artifact_registry_v1_permanent"] is True
    assert result["cross_chat_truth_handshake_v1_permanent"] is True
    assert result["terminal_proof_receipt_v1_permanent"] is True
    assert result["evidence_truth_ledger_v1_permanent"] is True
    assert result["failure_ownership_engine_v1_permanent"] is True
    assert result["deployment_truth_control_plane_v1_permanent"] is True
    assert result["adaptive_proof_engine_v1_permanent"] is True
    assert result["project_blast_radius_map_v1_permanent"] is True
    assert result["monster_self_benchmark_v1_permanent"] is True
    assert result["regression_debt_zero_gate_v1_permanent"] is True
    assert result["scope_aware_execution_lease_v1_permanent"] is True
    assert result["detached_execution_continuation_v1_permanent"] is True
    assert result["event_driven_resume_v1_permanent"] is True
    assert result["execution_heartbeat_deadman_recovery_v1_permanent"] is True
    assert result["zero_context_resume_packet_v1_permanent"] is True
    assert result["main_push_proof_concurrency_isolated"] is True


def test_persistent_execution_brain_is_permanently_enforced():
    brain = _load("persistent_execution_brain_v1", "devsystem/persistent_execution_brain_v1.py")
    result = brain.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["persistence_surface"] == "github_issue_ledger"
    assert result["fingerprint_guard"] is True
    assert result["async_lock"] is True
    assert result["repo_drift_guard"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/persistent_execution_brain_v1.py self-test" in workflow
    assert "tests/test_devsystem_persistent_execution_brain_v1.py" in workflow


def test_automatic_loop_kill_is_permanently_enforced():
    loop_kill = _load("automatic_loop_kill_v1", "devsystem/automatic_loop_kill_v1.py")
    result = loop_kill.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["same_state_poll_kill"] is True
    assert result["async_mutation_lock"] is True
    assert result["terminal_transition_unlock"] is True
    assert result["autonomous_skip_continue"] is True
    assert result["user_intervention_required_for_loop"] is False
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/automatic_loop_kill_v1.py" in workflow
    assert "tests/test_devsystem_automatic_loop_kill_v1.py" in workflow


def test_mandatory_2a_action_gate_is_permanently_enforced():
    gate = _load(
        "mandatory_2a_action_gate_v1",
        "devsystem/mandatory_2a_action_gate_v1.py",
    )
    result = gate.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["mandatory_gate"] is True
    assert result["missing_authorization_fails_closed"] is True
    assert result["matching_forward_receipt_authorizes"] is True
    assert result["receipt_action_mismatch_blocked"] is True
    assert result["live_async_mutation_blocked"] is True
    assert result["duplicate_poll_autonomously_skipped"] is True
    assert result["unknown_action_fails_closed"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/mandatory_2a_action_gate_v1.py" in workflow
    assert "tests/test_devsystem_mandatory_2a_action_gate_v1.py" in workflow


def test_mandatory_2a_single_use_receipt_is_permanently_enforced():
    receipt = _load(
        "mandatory_2a_receipt_v1",
        "devsystem/mandatory_2a_receipt_v1.py",
    )
    result = receipt.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["every_allowed_action_gets_receipt"] is True
    assert result["single_use_enforced"] is True
    assert result["exact_action_binding"] is True
    assert result["brain_state_binding"] is True
    assert result["tamper_evident"] is True
    assert result["denied_action_gets_no_receipt"] is True
    assert result["missing_receipt_fails_closed"] is True
    assert result["step1_gate_preserved"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/mandatory_2a_receipt_v1.py" in workflow
    assert "tests/test_devsystem_mandatory_2a_receipt_v1.py" in workflow


def test_mandatory_2a_replay_loop_lock_is_permanently_enforced():
    replay = _load(
        "mandatory_2a_replay_lock_v1",
        "devsystem/mandatory_2a_replay_lock_v1.py",
    )
    result = replay.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["execution_slot_claim_before_action"] is True
    assert result["exact_receipt_replay_skipped"] is True
    assert result["new_receipt_same_action_skipped"] is True
    assert result["async_cycle_replay_skipped"] is True
    assert result["autonomous_skip_no_user"] is True
    assert result["genuinely_new_action_allowed"] is True
    assert result["step2_single_use_preserved"] is True
    assert result["step1_gate_preserved"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/mandatory_2a_replay_lock_v1.py" in workflow
    assert "tests/test_devsystem_mandatory_2a_replay_lock_v1.py" in workflow


def test_mandatory_2a_global_enforcement_tripwire_is_permanently_enforced():
    global_gate = _load(
        "mandatory_2a_global_enforcement_v1",
        "devsystem/mandatory_2a_global_enforcement_v1.py",
    )
    result = global_gate.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["canonical_entrypoint_authorizes"] is True
    assert result["global_proof_valid"] is True
    assert result["missing_prerequisite_tripwire_blocks"] is True
    assert result["replay_stays_loop_skipped"] is True
    assert result["raw_step_outputs_cannot_bypass"] is True
    assert result["global_proof_tamper_blocked"] is True
    assert result["live_async_mutation_tripwire_blocks"] is True
    assert result["safe_continue_no_user"] is True
    assert result["step1_preserved"] is True
    assert result["step2_preserved"] is True
    assert result["step3_preserved"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/mandatory_2a_global_enforcement_v1.py" in workflow
    assert "tests/test_devsystem_mandatory_2a_global_enforcement_v1.py" in workflow


def test_mandatory_2a_adversarial_certification_is_permanently_enforced():
    adversarial = _load(
        "mandatory_2a_adversarial_certification_v1",
        "devsystem/mandatory_2a_adversarial_certification_v1.py",
    )
    result = adversarial.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["attack_count"] >= 12
    assert result["all_attacks_fail_closed"] is True
    assert result["legal_global_proof_valid"] is True
    assert result["step4_preserved"] is True
    assert result["steps1_3_preserved"] is True
    assert result["safe_continue_no_user"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/mandatory_2a_adversarial_certification_v1.py" in workflow
    assert "tests/test_devsystem_mandatory_2a_adversarial_certification_v1.py" in workflow


def test_distributed_execution_lease_is_permanently_enforced():
    lease = _load(
        "distributed_execution_lease_v1",
        "devsystem/distributed_execution_lease_v1.py",
    )
    result = lease.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["persistence_surface"] == "git_ref_fast_forward_cas"
    assert result["fast_forward_cas_required"] is True
    assert result["single_live_owner"] is True
    assert result["stale_revision_blocked"] is True
    assert result["expired_lease_takeover"] is True
    assert result["owner_a_executes"] is True
    assert result["owner_b_cannot_execute"] is True
    assert result["repository_drift_blocked"] is True
    assert result["two_a_chain_preserved"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/distributed_execution_lease_v1.py" in workflow
    assert "tests/test_devsystem_distributed_execution_lease_v1.py" in workflow


def test_semantic_action_normalizer_is_permanently_enforced():
    semantic = _load(
        "semantic_action_normalizer_v1",
        "devsystem/semantic_action_normalizer_v1.py",
    )
    result = semantic.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["alias_targets_equal"] is True
    assert result["alias_action_types_equal"] is True
    assert result["semantic_fingerprints_equal"] is True
    assert result["different_action_stays_distinct"] is True
    assert result["second_alias_replay_skipped"] is True
    assert result["raw_step1_authority_rejected"] is True
    assert result["tampered_normalization_proof_rejected"] is True
    assert result["distributed_lease_preserved"] is True
    assert result["two_a_chain_preserved"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/semantic_action_normalizer_v1.py" in workflow
    assert "tests/test_devsystem_semantic_action_normalizer_v1.py" in workflow


def test_frozen_artifact_registry_is_permanently_enforced():
    frozen = _load(
        "frozen_artifact_registry_v1",
        "devsystem/frozen_artifact_registry_v1.py",
    )
    result = frozen.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["intact_frozen_artifacts_pass"] is True
    assert result["mismatch_without_thaw_blocked"] is True
    assert result["deletion_without_thaw_blocked"] is True
    assert result["exact_head_exact_blob_thaw_allowed"] is True
    assert result["wrong_head_thaw_blocked"] is True
    assert result["registry_tamper_blocked"] is True
    assert result["pr_cannot_self_thaw"] is True
    assert result["separate_authoritative_registry_ref"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/frozen_artifact_registry_v1.py" in workflow
    assert "python devsystem/frozen_artifact_registry_v1.py verify-head" in workflow
    assert "monster-frozen-artifact-registry" in workflow
    assert "tests/test_devsystem_frozen_artifact_registry_v1.py" in workflow


def test_cross_chat_truth_handshake_is_permanently_enforced():
    handshake = _load(
        "cross_chat_truth_handshake_v1",
        "devsystem/cross_chat_truth_handshake_v1.py",
    )
    result = handshake.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["valid_handshake_authorized"] is True
    assert result["missing_packet_blocked"] is True
    assert result["stale_main_blocked"] is True
    assert result["stale_lease_blocked"] is True
    assert result["stale_registry_blocked"] is True
    assert result["tampered_packet_blocked"] is True
    assert result["raw_semantic_authority_rejected"] is True
    assert result["tampered_handshake_proof_rejected"] is True
    assert result["semantic_chain_preserved"] is True
    assert result["lease_chain_preserved"] is True
    assert result["two_a_chain_preserved"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/cross_chat_truth_handshake_v1.py" in workflow
    assert "python devsystem/cross_chat_truth_handshake_v1.py verify-packet" in workflow
    assert "monster-cross-chat-truth" in workflow
    assert "tests/test_devsystem_cross_chat_truth_handshake_v1.py" in workflow


def test_terminal_proof_receipt_is_permanently_enforced():
    receipt = _load(
        "terminal_proof_receipt_v1",
        "devsystem/terminal_proof_receipt_v1.py",
    )
    result = receipt.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["single_terminal_object"] is True
    assert result["exact_sha_bound"] is True
    assert result["authoritative_run_bound"] is True
    assert result["test_count_bound"] is True
    assert result["required_lanes_bound"] is True
    assert result["scope_diff_bound"] is True
    assert result["freeze_tokens_bound"] is True
    assert result["receipt_hash_tamper_rejected"] is True
    assert result["stale_sha_rejected"] is True
    assert result["stale_run_rejected"] is True
    assert result["failed_lane_rejected"] is True
    assert result["scope_drift_rejected"] is True
    assert result["freeze_token_drift_rejected"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/terminal_proof_receipt_v1.py" in workflow
    assert "terminal-proof-receipt:" in workflow
    assert "MONSTER_V4_STEP5_TERMINAL_RECEIPT_GREEN" in workflow
    assert "from devsystem.terminal_proof_receipt_v1 import build_receipt, validate_receipt" in workflow
    assert "tests/test_devsystem_terminal_proof_receipt_v1.py" in workflow


def test_evidence_truth_ledger_is_permanently_enforced():
    truth = _load("evidence_truth_ledger_v1", "devsystem/evidence_truth_ledger_v1.py")
    result = truth.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["exact_identity_guard"] is True
    assert result["stale_head_guard"] is True
    assert result["stale_main_guard"] is True
    assert result["stale_deployment_guard"] is True
    assert result["stale_freeze_guard"] is True
    assert result["tamper_guard"] is True
    assert result["stale_head_detection"] is True
    assert result["stale_main_detection"] is True
    assert result["stale_deployment_detection"] is True
    assert result["stale_freeze_rejected"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/evidence_truth_ledger_v1.py" in workflow
    assert "tests/test_devsystem_evidence_truth_ledger_v1.py" in workflow


def test_failure_ownership_engine_is_permanently_enforced():
    engine = _load("failure_ownership_engine_v1", "devsystem/failure_ownership_engine_v1.py")
    result = engine.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["classify_before_patch"] is True
    assert result["owner_scope_enforcement"] is True
    assert result["verifier_product_mutation_blocked"] is True
    assert result["stale_patch_blocked"] is True
    assert result["external_patch_blocked"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/failure_ownership_engine_v1.py" in workflow
    assert "tests/test_devsystem_failure_ownership_engine_v1.py" in workflow


def test_deployment_truth_control_plane_is_permanently_enforced():
    deployment_truth = _load(
        "deployment_truth_control_plane_v1",
        "devsystem/deployment_truth_control_plane_v1.py",
    )
    result = deployment_truth.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["exact_main_sha_parity"] is True
    assert result["stale_deployment_classification"] is True
    assert result["build_deploy_identity_required"] is True
    assert result["health_ready_ui_chain_required"] is True
    assert result["product_patch_blocked_on_deployment_failure"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/deployment_truth_control_plane_v1.py" in workflow
    assert "tests/test_devsystem_deployment_truth_control_plane_v1.py" in workflow


def test_adaptive_proof_engine_is_permanently_enforced():
    engine = _load("adaptive_proof_engine_v1", "devsystem/adaptive_proof_engine_v1.py")
    result = engine.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["css_targeted_browser"] is True
    assert result["router_fresh_session"] is True
    assert result["provider_provenance"] is True
    assert result["release_full_certification"] is True
    assert result["mixed_union_no_duplicates"] is True
    assert result["stale_head_blocked"] is True
    assert result["unknown_fail_safe"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/adaptive_proof_engine_v1.py" in workflow
    assert "tests/test_devsystem_adaptive_proof_engine_v1.py" in workflow


def test_project_blast_radius_map_is_permanently_enforced():
    blast = _load(
        "project_blast_radius_map_v1",
        "devsystem/project_blast_radius_map_v1.py",
    )
    result = blast.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["direct_transitive_map"] is True
    assert result["protected_reach_guard"] is True
    assert result["blast_radius_risk"] is True
    assert result["adaptive_proof_handoff"] is True
    assert result["unknown_fail_safe"] is True
    assert result["stale_head_blocked"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/project_blast_radius_map_v1.py" in workflow
    assert "tests/test_devsystem_project_blast_radius_map_v1.py" in workflow


def test_monster_self_benchmark_is_permanently_enforced():
    benchmark = _load(
        "monster_self_benchmark_v1",
        "devsystem/monster_self_benchmark_v1.py",
    )
    result = benchmark.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["root_cause_time_tracked"] is True
    assert result["time_to_green_tracked"] is True
    assert result["runs_required_tracked"] is True
    assert result["actions_per_step_tracked"] is True
    assert result["reruns_avoided_tracked"] is True
    assert result["stale_proofs_rejected_tracked"] is True
    assert result["loops_prevented_tracked"] is True
    assert result["production_mismatches_tracked"] is True
    assert result["first_patch_success_rate_tracked"] is True
    assert result["repair_time_tracked"] is True
    assert result["ci_time_tracked"] is True
    assert result["reruns_tracked"] is True
    assert result["stale_runs_tracked"] is True
    assert result["false_failures_tracked"] is True
    assert result["loops_tracked"] is True
    assert result["first_pass_green_rate_tracked"] is True
    assert result["trend_deltas_available"] is True
    assert result["no_overall_vanity_score"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/monster_self_benchmark_v1.py" in workflow
    assert "tests/test_devsystem_monster_self_benchmark_v1.py" in workflow



def test_regression_debt_zero_gate_is_permanently_enforced():
    gate = _load(
        "regression_debt_zero_gate_v1",
        "devsystem/regression_debt_zero_gate_v1.py",
    )
    result = gate.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["real_failure_creates_debt"] is True
    assert result["open_debt_blocks_freeze"] is True
    assert result["permanent_test_clears_debt"] is True
    assert result["permanent_contract_clears_debt"] is True
    assert result["stale_failure_exempt"] is True
    assert result["external_failure_exempt"] is True
    assert result["invalid_test_guard_rejected"] is True
    assert result["nonpermanent_guard_rejected"] is True
    assert result["tamper_rejected"] is True
    assert result["mixed_open_debt_blocks"] is True
    assert result["zero_debt_green"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/regression_debt_zero_gate_v1.py" in workflow
    assert "MONSTER_V4_REGRESSION_DEBT_ZERO_GATE_GREEN" in workflow
    assert "tests/test_devsystem_regression_debt_zero_gate_v1.py" in workflow



def test_scope_aware_execution_lease_is_permanently_enforced():
    lease = _load(
        "scope_aware_execution_lease_v1",
        "devsystem/scope_aware_execution_lease_v1.py",
    )
    result = lease.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["disjoint_parallel_allowed"] is True
    assert result["same_path_overlap_blocked"] is True
    assert result["dependency_overlap_blocked"] is True
    assert result["shared_resource_overlap_blocked"] is True
    assert result["exclusive_scope_blocks_parallel"] is True
    assert result["frozen_path_blocked"] is True
    assert result["stale_cas_blocked"] is True
    assert result["action_within_scope_authorized"] is True
    assert result["action_outside_scope_blocked"] is True
    assert result["unrelated_main_movement_tolerated"] is True
    assert result["scoped_identity_drift_blocked"] is True
    assert result["release_is_holder_local"] is True
    assert result["blast_radius_tokens_reused"] is True
    assert result["step_2a_chain_preserved"] is True
    assert result["dedicated_authoritative_ref"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/scope_aware_execution_lease_v1.py" in workflow
    assert "MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_GREEN" in workflow
    assert "tests/test_devsystem_scope_aware_execution_lease_v1.py" in workflow


def test_detached_execution_continuation_is_permanently_enforced():
    continuation = _load(
        "detached_execution_continuation_v1",
        "devsystem/detached_execution_continuation_v1.py",
    )
    result = continuation.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["repository_backed_state_contract"] is True
    assert result["tamper_evident_packet"] is True
    assert result["cas_persistence"] is True
    assert result["live_async_waits_without_duplicate"] is True
    assert result["worker_handoff_is_cas_bound"] is True
    assert result["handoff_does_not_grant_mutation"] is True
    assert result["resume_without_chat_history"] is True
    assert result["unrelated_main_movement_tolerated"] is True
    assert result["scope_drift_fails_closed"] is True
    assert result["frozen_scope_drift_fails_closed"] is True
    assert result["head_drift_fails_closed"] is True
    assert result["failed_async_forces_classification"] is True
    assert result["multiple_workstreams_supported"] is True
    assert result["step_2a_still_required"] is True
    assert result["scope_lease_still_required"] is True
    assert result["packet_never_grants_mutation"] is True
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/detached_execution_continuation_v1.py" in workflow
    assert "MONSTER_V5_DETACHED_EXECUTION_CONTINUATION_GREEN" in workflow
    assert "tests/test_devsystem_detached_execution_continuation_v1.py" in workflow



def test_event_driven_resume_is_permanently_enforced():
    event_resume = _load(
        "event_driven_resume_v1",
        "devsystem/event_driven_resume_v1.py",
    )
    result = event_resume.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["repository_backed_event_state"] is True
    assert result["continuation_packet_bound"] is True
    assert result["material_event_wakes_once"] is True
    assert result["duplicate_event_blocked"] is True
    assert result["resume_without_polling"] is True
    assert result["continuation_drift_fails_closed"] is True
    assert result["ready_receipt_one_shot"] is True
    assert result["stale_cas_blocked"] is True
    assert result["irrelevant_event_does_not_wake"] is True
    assert result["trigger_matrix_complete"] is True
    assert result["tamper_evident_state"] is True
    assert result["step_2a_still_required"] is True
    assert result["scope_lease_still_required"] is True
    assert result["event_never_grants_mutation"] is True
    assert result["polling_required"] is False
    assert result["product_runtime_mutation"] is False

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/event_driven_resume_v1.py" in workflow
    assert "MONSTER_V5_EVENT_DRIVEN_RESUME_GREEN" in workflow
    assert "tests/test_devsystem_event_driven_resume_v1.py" in workflow

def test_main_push_proof_concurrency_is_sha_isolated():
    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    marker = "group: devsystem-targeted-ci-${{ github.event_name == 'push' && github.ref == 'refs/heads/main' && github.sha || github.ref }}"
    assert marker in workflow
    assert "cancel-in-progress: true" in workflow
    assert "group: devsystem-targeted-ci-${{ github.ref }}" not in workflow

def test_forward_motion_contract_is_permanently_enforced_by_required_lane():
    contract = _load("forward_motion_contract_v1", "devsystem/forward_motion_contract_v1.py")
    result = contract.validate()
    assert result["status"] == "GREEN"
    assert result["mode"] == "strict_auto_continue"
    assert result["duplicate_proof_guard"] is True
    assert result["deterministic_zero_retry"] is True
    assert result["transient_single_retry"] is True
    assert result["one_active_blocker"] is True
    assert result["side_quest_deferral"] is True
    assert result["terminal_task_authoritative"] is True
    assert result["a9_replay_permanent"] is True

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "permanent-contract:" in workflow
    assert "tests/test_devsystem_permanent_gate_v1.py" in workflow


def test_forward_motion_v2_contract_is_permanently_enforced():
    contract = _load("forward_motion_contract_v2", "devsystem/forward_motion_contract_v2.py")
    result = contract.validate()
    assert result["status"] == "GREEN"
    assert result["mode"] == "strict_auto_continue_v2"
    assert result["semantic_root_cause_guard"] is True
    assert result["stagnation_guard"] is True
    assert result["monotonic_checkpoint_guard"] is True
    assert result["single_use_receipts"] is True
    assert result["receipt_chain_tamper_guard"] is True
    assert result["terminal_task_authoritative"] is True
    assert result["user_override_exact_single_use"] is True
    assert result["bootstrap_self_expiring"] is True
    assert result["v1_replay_still_green"] is True
    assert result["v2_replay_green"] is True

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "python devsystem/forward_motion_contract_v2.py" in workflow
    assert "python devsystem/action_ledger_v2.py verify-pr" in workflow


def test_final_gate_accepts_success_and_skipped_only():
    module = _load("final_gate_v1", "devsystem/final_gate_v1.py")
    result = module.evaluate({
        "classify": {"result": "success"},
        "browser-qa": {"result": "skipped"},
        "mlb-critical": {"result": "success"},
    })
    assert result["status"] == "GREEN"

    with pytest.raises(module.FinalGateFailure) as exc:
        module.evaluate({
            "classify": {"result": "success"},
            "cfb-critical": {"result": "failure"},
        })
    message = str(exc.value)
    assert "DEVSYSTEM_FAILURE_TRIAGE" in message
    assert "primary=cfb-critical" in message
    assert "layer=cfb" in message
    assert "official-ID contracts" in message


def test_predictive_triage_signature_is_permanently_exercised():
    triage = _load("failure_triage_predictive", "devsystem/failure_triage_v1.py")
    report = triage.triage({
        "browser-qa": {
            "result": "failure",
            "evidence": "Playwright TimeoutError while waiting for locator combobox",
        }
    })
    primary = report["primary"]
    assert primary["layer"] == "ui-browser"
    assert primary["evidence_signal"] == "browser-selector-race"
    assert primary["confidence"] == "high"
    assert primary["remediation_class"] == "transient-capable"
    assert primary["retry_policy"] == "retry-once-after-inspection"
    assert "readiness" in primary["inspect_first"]


def test_deterministic_failure_is_permanently_protected_from_blind_retry():
    triage = _load("failure_triage_no_blind_retry", "devsystem/failure_triage_v1.py")
    report = triage.triage({
        "cfb-critical": {
            "result": "failure",
            "evidence": "AssertionError: expected official ESPN event ID",
        }
    })
    primary = report["primary"]
    assert primary["layer"] == "cfb"
    assert primary["remediation_class"] == "deterministic-regression"
    assert primary["retry_policy"] == "do-not-retry"


def test_failure_packet_automatically_wires_captured_step_evidence():
    packet_module = _load("failure_packet_evidence_wiring", "devsystem/failure_packet_v1.py")
    packet = packet_module.build_packet(
        {"browser-qa": {"result": "failure"}},
        failed_steps={
            "browser-qa": [
                "Drive real UI: Playwright TimeoutError waiting for locator combobox"
            ]
        },
    )
    primary = packet["triage"]["primary"]
    assert primary["job"] == "browser-qa"
    assert primary["evidence_signal"] == "browser-selector-race"
    assert primary["confidence"] == "high"
    assert primary["retry_policy"] == "retry-once-after-inspection"
    assert primary["failure_fingerprint"].startswith("KYRE-CI-")
    assert primary["recurrence_status"] == "history-unavailable"
    assert primary["recurrence_timing_confidence"] == "unavailable"
    assert primary["recurrence_age_confidence"] == "unavailable"


def test_same_packet_failure_keeps_same_fingerprint_across_run_metadata():
    packet_module = _load("failure_packet_fingerprint", "devsystem/failure_packet_v1.py")
    needs = {
        "browser-qa": {
            "result": "failure",
            "evidence": "Playwright TimeoutError while waiting for locator combobox",
        }
    }
    first = packet_module.build_packet(needs, run_id="100", sha="aaa")
    second = packet_module.build_packet(needs, run_id="200", sha="bbb")
    assert first["triage"]["primary"]["failure_fingerprint"] == second["triage"]["primary"]["failure_fingerprint"]


def test_failed_job_log_excerpt_reaches_predictive_triage():
    extractor = _load("failure_log_excerpt_permanent", "devsystem/failure_log_excerpt_v1.py")
    packet_module = _load("failure_packet_log_path", "devsystem/failure_packet_v1.py")
    raw_log = "\n".join([
        "browser setup complete",
        "Playwright TimeoutError: waiting for locator combobox",
        "cleanup complete",
    ])
    excerpt = extractor.extract_log_excerpt(raw_log)
    packet = packet_module.build_packet({
        "browser-qa": {"result": "failure", "log_excerpt": excerpt}
    })
    primary = packet["triage"]["primary"]
    assert primary["job"] == "browser-qa"
    assert primary["evidence_signal"] == "browser-selector-race"
    assert primary["confidence"] == "high"
    assert primary["retry_policy"] == "retry-once-after-inspection"
    assert primary["failure_fingerprint"].startswith("KYRE-CI-")


def test_production_contract_separates_hosting_config_from_release_parity():
    contract = _load("production_contract_v1", "devsystem/production_contract_v1.py")
    service = {
        "name": contract.SERVICE_NAME,
        "id": contract.SERVICE_ID,
        "repo": contract.REPOSITORY,
        "branch": contract.RENDER_RELEASE_BRANCH,
        "autoDeploy": contract.EXPECTED_AUTO_DEPLOY,
        "suspended": "not_suspended",
        "serviceDetails": {
            "healthCheckPath": contract.EXPECTED_HEALTH_PATH,
            "url": contract.PUBLIC_URL,
        },
    }
    hosting = contract.evaluate_render_service(service)
    assert hosting["status"] == "GREEN"

    parity = contract.evaluate_release_parity(
        {"status": "diverged", "ahead_by": 1199, "behind_by": 63}
    )
    assert parity["status"] == "RED"
    assert parity["main_only_commits"] == 1199
    assert parity["release_only_commits"] == 63


def test_observability_core_is_dependency_light_and_secret_safe(monkeypatch):
    obs = _load("observability_v1", "sports_api/observability_v1.py")

    fingerprint = obs.error_fingerprint(ValueError("one"), path="/health")
    assert fingerprint == obs.error_fingerprint(ValueError("two"), path="/health")
    assert fingerprint.startswith("KYRE-")

    redacted = obs.sanitize_error_message("token=abc password=xyz")
    assert "abc" not in redacted
    assert "xyz" not in redacted

    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    monkeypatch.setenv("API_KEY", "do-not-leak")
    runtime = obs.runtime_metadata()
    assert runtime["deploy_branch"] == "main"
    assert runtime["deploy_commit"] == "abc123"
    assert "do-not-leak" not in repr(runtime)


def test_production_contract_and_observability_share_branch_truth():
    contract = _load("production_contract_branch_truth", "devsystem/production_contract_v1.py")
    obs = _load("observability_branch_truth", "sports_api/observability_v1.py")

    assert obs.CANONICAL_SOURCE_BRANCH == contract.CANONICAL_SOURCE_BRANCH
    assert obs.DEFAULT_RENDER_RUNTIME_BRANCH == contract.RENDER_RELEASE_BRANCH


def test_production_verification_v5_is_the_only_automatic_main_verifier():
    legacy = (ROOT / ".github/workflows/devsystem-production-verification.yml").read_text(encoding="utf-8")
    v5 = (ROOT / ".github/workflows/devsystem-production-verification-v5.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in legacy
    assert "\n  push:" not in legacy
    assert "branches: [main]" not in legacy

    assert "workflow_dispatch:" in v5
    assert "\n  push:" in v5
    assert "branches: [main]" in v5
