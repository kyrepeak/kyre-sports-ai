from __future__ import annotations

import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.chaos_adversarial_certification_harness_v1 import (
    ChaosCertificationFailure,
    SCENARIO_MANIFEST,
    VERSION,
    contract_self_test,
    run_chaos_matrix,
    validate_certificate,
)


ROOT = Path(__file__).resolve().parents[1]


def test_step6_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["version"] == VERSION
    assert result["scenario_count"] == 11
    assert result["all_scenarios_pass"] is True
    assert result["duplicate_chats_recovered"] is True
    assert result["stale_sha_blocked"] is True
    assert result["dropped_connection_recovered"] is True
    assert result["partial_queue_ack_reconciled"] is True
    assert result["old_writer_blocked"] is True
    assert result["frozen_file_edit_blocked"] is True
    assert result["deployment_drift_classified"] is True
    assert result["dead_runner_recoverable"] is True
    assert result["duplicate_merge_blocked"] is True
    assert result["slow_live_run_protected"] is True
    assert result["detached_resume_no_duplicate"] is True
    assert result["tamper_evident_certificate"] is True
    assert result["step_2a_preserved"] is True
    assert result["frozen_prior_steps_preserved"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False
    assert result["mutation_authority_granted"] is False


def test_required_user_failure_modes_are_explicitly_present():
    required = {
        "duplicate_chats",
        "stale_sha",
        "dropped_connection_after_mutation",
        "partial_queue_acknowledgement",
        "old_writer_wakeup",
        "frozen_file_edit",
        "deployment_drift",
        "dead_runner",
        "duplicate_merge_attempt",
    }
    assert required.issubset(set(SCENARIO_MANIFEST))


def test_matrix_certificate_is_complete_and_tamper_evident():
    cert = run_chaos_matrix()
    validated = validate_certificate(cert)
    assert validated["status"] == "GREEN"
    assert validated["scenario_count"] == len(SCENARIO_MANIFEST)
    assert validated["passed_scenario_count"] == len(SCENARIO_MANIFEST)
    assert validated["chaos_certificate_digest"].startswith("sha256:")

    tampered = deepcopy(cert)
    tampered["scenarios"]["deployment_drift"]["recovery"] = "PATCH_PRODUCT"
    with pytest.raises(ChaosCertificationFailure, match="digest mismatch"):
        validate_certificate(tampered)


def test_no_scenario_grants_mutation_authority():
    cert = run_chaos_matrix()
    assert cert["safety"]["mutation_authority_granted"] is False
    assert cert["safety"]["network_calls"] is False
    assert cert["safety"]["auto_mutate"] is False
    assert cert["safety"]["may_modify_product_runtime"] is False
    assert cert["safety"]["all_dependency_safety_green"] is True


def test_every_scenario_has_fault_expected_evidence_and_recovery():
    cert = run_chaos_matrix()
    for scenario_id, manifest in SCENARIO_MANIFEST.items():
        assert manifest["fault"]
        assert manifest["expected"]
        row = cert["scenarios"][scenario_id]
        assert row["passed"] is True
        assert row["evidence"]
        assert row["recovery"]


def test_direct_script_execution_is_green():
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "devsystem" / "chaos_adversarial_certification_harness_v1.py"),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V8_STEP6_CHAOS_ADVERSARIAL_CERTIFICATION_GREEN" in completed.stdout
