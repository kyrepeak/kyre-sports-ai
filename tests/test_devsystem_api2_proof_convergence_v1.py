from __future__ import annotations

import json
from pathlib import Path

import pytest

from devsystem.api2_proof_convergence_v1 import (
    AUTO_MUTATE,
    MAY_MODIFY_PRODUCT_RUNTIME,
    MUTATION_AUTHORITY_GRANTED,
    NETWORK_CALLS,
    ProofConvergenceFailure,
    STEP_CONTRACTS,
    contract_self_test,
    validate_authoritative_registry,
)
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash


def _registry() -> dict:
    entries = {}
    for index, contract in enumerate(STEP_CONTRACTS, start=1):
        checkpoint = contract["checkpoint"]
        entries[checkpoint] = {
            "status": "FROZEN",
            "checkpoint_id": checkpoint,
            "source_main_sha": format(index, "x") * 40,
            "artifacts": {f"proof/step{index}.txt": format(index, "x") * 40},
        }
    payload = {
        "schema_version": 1,
        "version": "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1",
        "repository": "kyrepeak/kyre-sports-ai",
        "registry_ref": "refs/heads/monster-frozen-artifact-registry",
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 83,
        "source_main_sha": "a" * 40,
        "entries": entries,
        "active_thaws": [],
    }
    payload["state_hash"] = _hash(_payload_without_hash(payload))
    return payload


def test_local_architecture_converges() -> None:
    result = contract_self_test()
    assert result["decision"] == "LOCAL_ARCHITECTURE_CONVERGED"
    assert result["steps_proven"] == 6


def test_registry_requires_all_six_frozen_steps() -> None:
    result = validate_authoritative_registry(_registry())
    assert result["decision"] == "AUTHORITATIVE_FROZEN_CHAIN_CONVERGED"
    assert result["required_checkpoint_count"] == 6


def test_registry_missing_step_fails_closed() -> None:
    payload = _registry()
    del payload["entries"]["API2_PROOF_ARCHITECTURE_V1_STEP4"]
    payload["state_hash"] = _hash(_payload_without_hash(payload))
    with pytest.raises(ProofConvergenceFailure):
        validate_authoritative_registry(payload)


def test_step7_is_read_only() -> None:
    assert NETWORK_CALLS is False
    assert AUTO_MUTATE is False
    assert MAY_MODIFY_PRODUCT_RUNTIME is False
    assert MUTATION_AUTHORITY_GRANTED is False
