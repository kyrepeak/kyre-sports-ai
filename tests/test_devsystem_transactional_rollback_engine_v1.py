from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from devsystem.transactional_rollback_engine_v1 import (
    TransactionalRollbackFailure,
    _simulation_core,
    advance,
    contract_self_test,
    prepare_transaction,
    record_mutation_applied,
    validate_state,
)
from devsystem.terminal_proof_receipt_v1 import build_receipt


BASE = "a" * 40
MUT = "b" * 40
RESTORED = "c" * 40
CURRENT = "d" * 40
P1 = "app.py"
P2 = "config.py"
B1 = "1" * 40
B2 = "2" * 40
M1 = "3" * 40
M2 = "4" * 40
DEP = "5" * 40
OWNER = "chat:monster"


def _hash(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def _proof(head=BASE, run=1, checkpoint="BASE"):
    return build_receipt(
        repository="owner/repo",
        checkpoint_id=checkpoint,
        head_sha=head,
        authoritative_run=run,
        authoritative_workflow="proof",
        test_count=12,
        required_lanes={"focused": "success", "devsystem": "success"},
        scope_diff=[P1, P2],
        freeze_tokens=["GREEN"],
    )


def _simulation(owner=OWNER, head=BASE, paths=(P1, P2), status="GREEN"):
    receipt = {
        "version": "MONSTER_V8_PRE_MUTATION_BLAST_RADIUS_SIMULATOR_V1",
        "status": status,
        "decision": (
            "SAFE_TO_REQUEST_MUTATION_GATE"
            if status == "GREEN"
            else "PRE_MUTATION_BLOCKED"
        ),
        "owner_id": owner,
        "expected_head_sha": head,
        "observed_head_sha": head,
        "proposed_paths": sorted(paths),
        "impact_paths": sorted(paths),
        "required_scope": {
            "write_paths": sorted(paths),
            "dependency_tokens": [],
            "shared_resources": [],
            "resource_identity": {"main:base": head},
            "exclusive": False,
        },
        "declared_scope": {
            "write_paths": sorted(paths),
            "dependency_tokens": [],
            "shared_resources": [],
            "resource_identity": {"main:base": head},
            "exclusive": False,
        },
        "workflow_impacts": [],
        "deployment_impacts": [],
        "frozen_registry_state_hash": "6" * 64,
        "lease_state_hash": "7" * 64,
        "legacy_blast": {
            "version": "MONSTER_PROJECT_BLAST_RADIUS_MAP_V1",
            "state": "ALLOW_EDIT",
            "risk": "LOW",
            "blast_radius": 0,
            "impacted_entrypoints": [],
            "protected_reach": [],
        },
        "blockers": [] if status == "GREEN" else [{"code": "TEST"}],
        "blocker_count": 0 if status == "GREEN" else 1,
        "step_2a_required": True,
        "mutation_authority": False,
    }
    receipt["simulation_receipt_digest"] = "sha256:" + _hash(
        _simulation_core(receipt)
    )
    return receipt


def _prepared(
    *,
    simulation=None,
    proof=None,
    resources=None,
    baseline_paths=None,
    dependencies=None,
):
    return prepare_transaction(
        transaction_id="TX-1",
        owner_id=OWNER,
        baseline_head_sha=BASE,
        baseline_path_blobs=baseline_paths or {P1: B1, P2: B2},
        baseline_dependency_blobs=dependencies or {"dep.py": DEP},
        baseline_resource_snapshots=resources or {"deploy:app": "release-a"},
        baseline_terminal_receipt=proof or _proof(),
        blast_simulation_receipt=simulation or _simulation(),
    )


def _applied(resources=None, mutation_paths=None):
    return record_mutation_applied(
        _prepared(),
        mutation_head_sha=MUT,
        mutation_path_blobs=mutation_paths or {P1: M1, P2: M2},
        mutation_resource_snapshots=resources or {"deploy:app": "release-b"},
    )


def _failure_evidence(**surface_changes):
    surface = {
        "head_sha": CURRENT,
        "path_blobs": {P1: M1, P2: M2},
        "dependency_blobs": {"dep.py": DEP},
        "resource_snapshots": {"deploy:app": "release-b"},
    }
    surface.update(surface_changes)
    return {
        "outcome": {
            "terminal": True,
            "status": "FAILURE",
            "transaction_id": "TX-1",
            "head_sha": MUT,
            "failure_class": "PRODUCT_RUNTIME",
        },
        "current_surface": surface,
    }


def _restore_issued():
    return advance(_applied(), _failure_evidence())


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["whole_repo_reset_forbidden"] is True
    assert result["rollback_closes_only_after_green_recertification"] is True


def test_prepare_requires_green_exact_head_terminal_receipt():
    wrong = _proof(head="9" * 40)
    with pytest.raises(
        TransactionalRollbackFailure,
        match="bound to wrong head",
    ):
        _prepared(proof=wrong)


def test_prepare_requires_green_step1_simulation():
    with pytest.raises(
        TransactionalRollbackFailure,
        match="must be GREEN",
    ):
        _prepared(simulation=_simulation(status="BLOCKED"))


def test_prepare_rejects_simulation_owner_mismatch():
    with pytest.raises(
        TransactionalRollbackFailure,
        match="owner mismatch",
    ):
        _prepared(simulation=_simulation(owner="other-chat"))


def test_prepare_rejects_simulation_head_mismatch():
    with pytest.raises(
        TransactionalRollbackFailure,
        match="baseline head",
    ):
        _prepared(simulation=_simulation(head="9" * 40))


def test_prepare_rejects_simulation_path_mismatch():
    with pytest.raises(
        TransactionalRollbackFailure,
        match="proposed paths mismatch",
    ):
        _prepared(simulation=_simulation(paths=(P1,)))


def test_prepare_rejects_tampered_simulation_digest():
    sim = _simulation()
    sim["legacy_blast"]["risk"] = "HIGH"
    with pytest.raises(
        TransactionalRollbackFailure,
        match="receipt digest mismatch",
    ):
        _prepared(simulation=sim)


def test_prepared_transaction_only_requests_step2a_gate():
    result = advance(_prepared())
    assert result["result"]["decision"] == "BASELINE_SEALED_READY_FOR_STEP2A_MUTATION"
    assert result["result"]["next_legal_action"] == "REQUEST_STEP_2A_MUTATION_GATE"
    assert result["result"]["mutation_authority"] is False


def test_mutation_path_set_must_exactly_match_baseline():
    with pytest.raises(
        TransactionalRollbackFailure,
        match="path set must exactly match",
    ):
        record_mutation_applied(
            _prepared(),
            mutation_head_sha=MUT,
            mutation_path_blobs={P1: M1},
            mutation_resource_snapshots={"deploy:app": "release-b"},
        )


def test_mutation_resource_set_must_exactly_match_baseline():
    with pytest.raises(
        TransactionalRollbackFailure,
        match="resource set must exactly match",
    ):
        record_mutation_applied(
            _prepared(),
            mutation_head_sha=MUT,
            mutation_path_blobs={P1: M1, P2: M2},
            mutation_resource_snapshots={},
        )


def test_noop_mutation_is_rejected():
    with pytest.raises(
        TransactionalRollbackFailure,
        match="changed no owned surface",
    ):
        record_mutation_applied(
            _prepared(),
            mutation_head_sha=MUT,
            mutation_path_blobs={P1: B1, P2: B2},
            mutation_resource_snapshots={"deploy:app": "release-a"},
        )


def test_nonterminal_failure_cannot_authorize_rollback():
    result = advance(
        _applied(),
        {
            "outcome": {
                "terminal": False,
                "status": "FAILURE",
                "transaction_id": "TX-1",
                "head_sha": MUT,
            }
        },
    )
    assert result["result"]["decision"] == "WAIT_FOR_TERMINAL_MUTATION_OUTCOME"
    assert result["state"]["phase"] == "MUTATION_APPLIED"


def test_terminal_success_closes_and_forbids_rollback():
    result = advance(
        _applied(),
        {
            "outcome": {
                "terminal": True,
                "status": "SUCCESS",
                "transaction_id": "TX-1",
                "head_sha": MUT,
            }
        },
    )
    assert result["result"]["decision"] == "TRANSACTION_COMMITTED_SUCCESS"
    assert result["result"]["rollback_allowed"] is False
    assert result["state"]["phase"] == "CLOSED_SUCCESS"


def test_wrong_transaction_outcome_blocks():
    result = advance(
        _applied(),
        {
            "outcome": {
                "terminal": True,
                "status": "FAILURE",
                "transaction_id": "TX-WRONG",
                "head_sha": MUT,
                "failure_class": "PRODUCT_RUNTIME",
            }
        },
    )
    assert result["result"]["decision"] == "TRANSACTION_BLOCKED"
    assert result["state"]["failure"]["code"] == "OUTCOME_TRANSACTION_ID_MISMATCH"


def test_wrong_mutation_head_outcome_blocks():
    result = advance(
        _applied(),
        {
            "outcome": {
                "terminal": True,
                "status": "FAILURE",
                "transaction_id": "TX-1",
                "head_sha": "9" * 40,
                "failure_class": "PRODUCT_RUNTIME",
            }
        },
    )
    assert result["state"]["failure"]["code"] == "OUTCOME_HEAD_MISMATCH"


def test_terminal_failure_without_snapshot_requests_one():
    evidence = _failure_evidence()
    evidence.pop("current_surface")
    result = advance(_applied(), evidence)
    assert result["result"]["decision"] == "REQUIRE_CURRENT_ROLLBACK_SURFACE_SNAPSHOT"
    assert result["result"]["polling_required"] is False


def test_unrelated_newer_head_does_not_block_path_scoped_rollback():
    result = _restore_issued()
    assert result["result"]["decision"] == "ROLLBACK_ACTION_ISSUED"
    assert result["result"]["expected_current_head_sha"] == CURRENT
    assert result["result"]["whole_repo_ref_reset_allowed"] is False
    assert result["result"]["restore_manifest"]["path_blobs"] == {P1: B1, P2: B2}


def test_newer_writer_on_owned_path_blocks_rollback():
    result = advance(
        _applied(),
        _failure_evidence(path_blobs={P1: "9" * 40, P2: M2}),
    )
    assert result["result"]["decision"] == "TRANSACTION_BLOCKED"
    codes = [row["code"] for row in result["result"]["rollback_conflicts"]]
    assert "POST_MUTATION_PATH_OWNERSHIP_DRIFT" in codes


def test_dependency_drift_blocks_rollback():
    result = advance(
        _applied(),
        _failure_evidence(dependency_blobs={"dep.py": "9" * 40}),
    )
    codes = [row["code"] for row in result["result"]["rollback_conflicts"]]
    assert "DEPENDENCY_DRIFT_SINCE_BASELINE" in codes


def test_resource_drift_blocks_rollback():
    result = advance(
        _applied(),
        _failure_evidence(resource_snapshots={"deploy:app": "release-c"}),
    )
    codes = [row["code"] for row in result["result"]["rollback_conflicts"]]
    assert "POST_MUTATION_RESOURCE_OWNERSHIP_DRIFT" in codes


def test_restore_action_is_single_use_while_waiting_for_event():
    first = _restore_issued()
    second = advance(first["state"], {})
    assert second["result"]["decision"] == "WAIT_FOR_RESTORATION_EVENT"
    assert second["result"]["duplicate_restore_suppressed"] is True


def test_restore_manifest_supports_deleting_new_file():
    prepared = _prepared(
        baseline_paths={P1: None, P2: B2},
    )
    applied = record_mutation_applied(
        prepared,
        mutation_head_sha=MUT,
        mutation_path_blobs={P1: M1, P2: M2},
        mutation_resource_snapshots={"deploy:app": "release-b"},
    )
    result = advance(
        applied,
        {
            "outcome": {
                "terminal": True,
                "status": "FAILURE",
                "transaction_id": "TX-1",
                "head_sha": MUT,
                "failure_class": "PRODUCT_RUNTIME",
            },
            "current_surface": {
                "head_sha": CURRENT,
                "path_blobs": {P1: M1, P2: M2},
                "dependency_blobs": {"dep.py": DEP},
                "resource_snapshots": {"deploy:app": "release-b"},
            },
        },
    )
    assert result["result"]["restore_manifest"]["path_blobs"][P1] is None


def test_restoration_must_match_baseline_paths_exactly():
    first = _restore_issued()
    result = advance(
        first["state"],
        {
            "restoration": {
                "status": "RESTORED",
                "restored_head_sha": RESTORED,
                "path_blobs": {P1: "9" * 40, P2: B2},
                "resource_snapshots": {"deploy:app": "release-a"},
            }
        },
    )
    assert result["state"]["failure"]["code"] == "RESTORATION_PATH_IDENTITY_MISMATCH"


def test_restoration_must_match_baseline_resources_exactly():
    first = _restore_issued()
    result = advance(
        first["state"],
        {
            "restoration": {
                "status": "RESTORED",
                "restored_head_sha": RESTORED,
                "path_blobs": {P1: B1, P2: B2},
                "resource_snapshots": {"deploy:app": "release-z"},
            }
        },
    )
    assert result["state"]["failure"]["code"] == "RESTORATION_RESOURCE_IDENTITY_MISMATCH"


def test_exact_restoration_requires_new_recertification():
    first = _restore_issued()
    result = advance(
        first["state"],
        {
            "restoration": {
                "status": "RESTORED",
                "restored_head_sha": RESTORED,
                "path_blobs": {P1: B1, P2: B2},
                "resource_snapshots": {"deploy:app": "release-a"},
            }
        },
    )
    assert result["result"]["action"] == "RUN_ROLLBACK_RECERTIFICATION"
    assert result["state"]["phase"] == "RECERTIFY"


def test_recertification_is_single_use_while_waiting():
    first = _restore_issued()
    recert = advance(
        first["state"],
        {
            "restoration": {
                "status": "RESTORED",
                "restored_head_sha": RESTORED,
                "path_blobs": {P1: B1, P2: B2},
                "resource_snapshots": {"deploy:app": "release-a"},
            }
        },
    )
    waiting = advance(recert["state"], {})
    assert waiting["result"]["decision"] == "WAIT_FOR_ROLLBACK_RECERTIFICATION_EVENT"
    assert waiting["result"]["duplicate_recertification_suppressed"] is True


def test_recertification_receipt_must_bind_exact_restored_head():
    first = _restore_issued()
    recert = advance(
        first["state"],
        {
            "restoration": {
                "status": "RESTORED",
                "restored_head_sha": RESTORED,
                "path_blobs": {P1: B1, P2: B2},
                "resource_snapshots": {"deploy:app": "release-a"},
            }
        },
    )
    result = advance(
        recert["state"],
        {"recertification_receipt": _proof(head="9" * 40, run=2, checkpoint="ROLLBACK")},
    )
    assert result["state"]["failure"]["code"] == "ROLLBACK_RECERTIFICATION_HEAD_MISMATCH"


def test_green_recertification_closes_rollback():
    first = _restore_issued()
    recert = advance(
        first["state"],
        {
            "restoration": {
                "status": "RESTORED",
                "restored_head_sha": RESTORED,
                "path_blobs": {P1: B1, P2: B2},
                "resource_snapshots": {"deploy:app": "release-a"},
            }
        },
    )
    result = advance(
        recert["state"],
        {"recertification_receipt": _proof(head=RESTORED, run=2, checkpoint="ROLLBACK")},
    )
    assert result["result"]["decision"] == "TRANSACTION_ROLLBACK_CERTIFIED"
    assert result["state"]["phase"] == "CLOSED_ROLLED_BACK"


def test_terminal_recertification_failure_blocks_without_retry():
    first = _restore_issued()
    recert = advance(
        first["state"],
        {
            "restoration": {
                "status": "RESTORED",
                "restored_head_sha": RESTORED,
                "path_blobs": {P1: B1, P2: B2},
                "resource_snapshots": {"deploy:app": "release-a"},
            }
        },
    )
    result = advance(
        recert["state"],
        {
            "recertification_failure": {
                "terminal": True,
                "run_id": 99,
            }
        },
    )
    assert result["state"]["failure"]["code"] == "ROLLBACK_RECERTIFICATION_FAILED"
    assert result["result"]["next_legal_action"] == "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE"


def test_tampered_transaction_state_fails_closed():
    state = _prepared()
    tampered = deepcopy(state)
    tampered["phase"] = "CLOSED_SUCCESS"
    with pytest.raises(
        TransactionalRollbackFailure,
        match="state hash mismatch",
    ):
        validate_state(tampered)


def test_engine_is_pure_and_never_grants_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
