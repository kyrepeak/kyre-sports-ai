from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.evidence_truth_ledger_v1 import (
    EvidenceTruthFailure,
    _fingerprint,
    build_evidence_record,
    build_truth_ledger,
    classify_evidence,
    validate_truth_ledger,
)


HEAD = "1" * 40
OLD = "2" * 40
DEPLOY = "3" * 40


def _record(**overrides):
    values = {
        "evidence_id": "EV-STEP3-PR",
        "checkpoint_id": "3",
        "contract_id": "monster-v3-step3",
        "scope": "PR_HEAD",
        "repository": "kyrepeak/kyre-sports-ai",
        "commit_sha": HEAD,
        "workflow_run_id": 12345,
        "job_id": 67890,
        "proof_id": "devsystem-final-gate",
        "conclusion": "SUCCESS",
        "frozen": False,
    }
    values.update(overrides)
    return build_evidence_record(**values)


def test_pr_head_evidence_is_current_only_on_exact_head():
    record = _record()
    assert classify_evidence(
        record,
        current_head_sha=HEAD,
        current_main_sha=OLD,
    )["freshness"] == "CURRENT"

    stale = classify_evidence(
        record,
        current_head_sha=OLD,
        current_main_sha=OLD,
    )
    assert stale["freshness"] == "STALE_HEAD"
    assert stale["requires_reproof"] is True


def test_merged_main_evidence_turns_stale_when_main_advances():
    record = _record(scope="MERGED_MAIN", commit_sha=HEAD)
    assert classify_evidence(
        record,
        current_head_sha=HEAD,
        current_main_sha=HEAD,
    )["freshness"] == "CURRENT"

    stale = classify_evidence(
        record,
        current_head_sha=HEAD,
        current_main_sha=OLD,
    )
    assert stale["freshness"] == "STALE_MAIN"


def test_deployment_proof_requires_exact_deployed_sha():
    record = _record(
        scope="DEPLOYMENT",
        commit_sha=HEAD,
        deployment_id="deploy-7",
        deployment_sha=HEAD,
    )
    assert classify_evidence(
        record,
        current_head_sha=HEAD,
        current_main_sha=HEAD,
        current_deployment_sha=HEAD,
    )["freshness"] == "CURRENT"

    stale = classify_evidence(
        record,
        current_head_sha=HEAD,
        current_main_sha=HEAD,
        current_deployment_sha=DEPLOY,
    )
    assert stale["freshness"] == "STALE_DEPLOYMENT"


def test_incomplete_or_unsuccessful_proof_cannot_be_current():
    incomplete = _record(job_id=None)
    assert classify_evidence(
        incomplete,
        current_head_sha=HEAD,
        current_main_sha=HEAD,
    )["freshness"] == "INCOMPLETE"

    failed = _record(conclusion="FAILURE")
    assert classify_evidence(
        failed,
        current_head_sha=HEAD,
        current_main_sha=HEAD,
    )["freshness"] == "INCOMPLETE"


def test_truth_ledger_builds_machine_readable_evidence_graph():
    record = _record(
        scope="DEPLOYMENT",
        deployment_id="deploy-7",
        deployment_sha=HEAD,
        frozen=True,
    )
    ledger = build_truth_ledger(
        task_id="monster-v3",
        checkpoint_id="3",
        records=[record],
        current_head_sha=HEAD,
        current_main_sha=HEAD,
        current_deployment_sha=HEAD,
    )
    validated = validate_truth_ledger(ledger)
    assert validated["status"] == "GREEN"
    assert validated["current_evidence"] == 1
    assert validated["stale_evidence"] == 0

    graph = ledger["graph"]
    kinds = {node["kind"] for node in graph["nodes"]}
    assert {
        "checkpoint",
        "contract",
        "workflow_run",
        "job",
        "commit",
        "deployment",
        "proof",
        "freeze",
    }.issubset(kinds)

    relations = {edge["relation"] for edge in graph["edges"]}
    assert {
        "requires_contract",
        "proved_by_run",
        "contains_job",
        "certifies_commit",
        "deployed_as",
        "observed_by",
        "closes_checkpoint",
    }.issubset(relations)


def test_stale_history_is_preserved_but_cannot_freeze_checkpoint():
    stale_history = _record(
        evidence_id="EV-OLD",
        commit_sha=OLD,
        frozen=False,
    )
    current = _record(
        evidence_id="EV-CURRENT",
        commit_sha=HEAD,
        frozen=True,
    )
    ledger = build_truth_ledger(
        task_id="monster-v3",
        checkpoint_id="3",
        records=[stale_history, current],
        current_head_sha=HEAD,
        current_main_sha=HEAD,
    )
    assert ledger["records"][0]["freshness"] == "STALE_HEAD"
    assert ledger["records"][1]["freshness"] == "CURRENT"
    assert validate_truth_ledger(ledger)["stale_evidence"] == 1

    stale_freeze = _record(commit_sha=OLD, frozen=True)
    with pytest.raises(EvidenceTruthFailure, match="stale evidence cannot freeze"):
        build_truth_ledger(
            task_id="monster-v3",
            checkpoint_id="3",
            records=[stale_freeze],
            current_head_sha=HEAD,
            current_main_sha=HEAD,
        )


def test_truth_ledger_fails_closed_on_dangling_graph_edge():
    ledger = build_truth_ledger(
        task_id="monster-v3",
        checkpoint_id="3",
        records=[_record()],
        current_head_sha=HEAD,
        current_main_sha=HEAD,
    )
    ledger["graph"]["edges"].append(
        {"from": "missing", "to": "also-missing", "relation": "fake"}
    )
    with pytest.raises(EvidenceTruthFailure, match="dangling graph edge"):
        validate_truth_ledger(ledger)


def test_truth_ledger_fingerprint_detects_tampering():
    ledger = build_truth_ledger(
        task_id="monster-v3",
        checkpoint_id="3",
        records=[_record()],
        current_head_sha=HEAD,
        current_main_sha=HEAD,
    )
    tampered = copy.deepcopy(ledger)
    tampered["records"][0]["proof_id"] = "different-proof"
    with pytest.raises(EvidenceTruthFailure, match="fingerprint mismatch"):
        validate_truth_ledger(tampered)


def test_exact_run_job_commit_identity_is_required():
    with pytest.raises(EvidenceTruthFailure, match="workflow_run_id"):
        _record(workflow_run_id=None)
    with pytest.raises(EvidenceTruthFailure, match="commit_sha"):
        _record(commit_sha="abc")
    with pytest.raises(EvidenceTruthFailure, match="repository"):
        _record(repository="not-a-repo")



def test_validator_recomputes_freshness_instead_of_trusting_stored_label():
    stale = _record(evidence_id="EV-FORGED", commit_sha=OLD, frozen=False)
    ledger = build_truth_ledger(
        task_id="monster-v3",
        checkpoint_id="3",
        records=[stale],
        current_head_sha=HEAD,
        current_main_sha=HEAD,
    )
    assert ledger["records"][0]["freshness"] == "STALE_HEAD"

    forged = copy.deepcopy(ledger)
    forged["records"][0]["freshness"] = "CURRENT"
    forged["records"][0]["requires_reproof"] = False
    forged["records"][0]["reason"] = "forged current label"
    forged["records"][0]["frozen"] = True
    unsigned = copy.deepcopy(forged)
    unsigned.pop("truth_id")
    forged["truth_id"] = _fingerprint(unsigned)

    with pytest.raises(EvidenceTruthFailure, match="freshness does not match"):
        validate_truth_ledger(forged)

def test_truth_ledger_runs_directly_as_permanent_self_test():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "evidence_truth_ledger_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_EVIDENCE_TRUTH_LEDGER_V1_GREEN" in completed.stdout
