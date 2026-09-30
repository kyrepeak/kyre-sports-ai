from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.frozen_artifact_registry_v1 import (
    FrozenArtifactRegistryFailure,
    REGISTRY_REF,
    VERSION,
    contract_self_test,
    evaluate_head,
    validate_registry,
)


def _registry():
    from devsystem.frozen_artifact_registry_v1 import _hash

    payload = {
        "schema_version": 1,
        "version": VERSION,
        "repository": "owner/repo",
        "registry_ref": REGISTRY_REF,
        "registry_path": "devsystem/frozen_artifact_registry_state_v1.json",
        "revision": 0,
        "source_main_sha": "1" * 40,
        "entries": {
            "STEP": {
                "status": "FROZEN",
                "checkpoint_id": "STEP",
                "source_main_sha": "1" * 40,
                "artifacts": {"a.py": "a" * 40, "b.py": "b" * 40},
            }
        },
        "active_thaws": [],
    }
    payload["state_hash"] = _hash(payload)
    return payload


def test_registry_hash_and_artifact_count_validate():
    result = validate_registry(_registry())
    assert result["status"] == "GREEN"
    assert result["entry_count"] == 1
    assert result["artifact_count"] == 2


def test_unchanged_frozen_artifacts_pass():
    result = evaluate_head(
        _registry(),
        {"a.py": "a" * 40, "b.py": "b" * 40},
        head_sha="2" * 40,
    )
    assert result["decision"] == "FROZEN_ARTIFACTS_INTACT"


@pytest.mark.parametrize("actual", ["c" * 40, None])
def test_changed_or_deleted_artifact_fails_closed_without_thaw(actual):
    with pytest.raises(FrozenArtifactRegistryFailure, match="without exact thaw grant"):
        evaluate_head(
            _registry(),
            {"a.py": actual, "b.py": "b" * 40},
            head_sha="2" * 40,
        )


def test_exact_head_and_exact_from_to_thaw_is_allowed():
    from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash

    registry = _registry()
    registry["active_thaws"] = [{
        "thaw_id": "THAW-1",
        "status": "ACTIVE",
        "target_head_sha": "2" * 40,
        "files": {
            "a.py": {"from_blob": "a" * 40, "to_blob": "c" * 40}
        },
    }]
    registry["state_hash"] = _hash(_payload_without_hash(registry))
    result = evaluate_head(
        registry,
        {"a.py": "c" * 40, "b.py": "b" * 40},
        head_sha="2" * 40,
    )
    assert result["decision"] == "FROZEN_ARTIFACTS_EXACT_THAW_AUTHORIZED"
    assert result["thawed_files"][0]["thaw_id"] == "THAW-1"


def test_thaw_for_different_head_does_not_authorize():
    from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash

    registry = _registry()
    registry["active_thaws"] = [{
        "thaw_id": "THAW-1",
        "status": "ACTIVE",
        "target_head_sha": "3" * 40,
        "files": {
            "a.py": {"from_blob": "a" * 40, "to_blob": "c" * 40}
        },
    }]
    registry["state_hash"] = _hash(_payload_without_hash(registry))
    with pytest.raises(FrozenArtifactRegistryFailure):
        evaluate_head(
            registry,
            {"a.py": "c" * 40, "b.py": "b" * 40},
            head_sha="2" * 40,
        )


def test_exact_head_thaw_cannot_include_unused_frozen_file():
    from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash

    registry = _registry()
    registry["active_thaws"] = [{
        "thaw_id": "THAW-1",
        "status": "ACTIVE",
        "target_head_sha": "2" * 40,
        "files": {
            "a.py": {"from_blob": "a" * 40, "to_blob": "c" * 40},
            "b.py": {"from_blob": "b" * 40, "to_blob": "d" * 40},
        },
    }]
    registry["state_hash"] = _hash(_payload_without_hash(registry))
    with pytest.raises(FrozenArtifactRegistryFailure, match="unused file"):
        evaluate_head(
            registry,
            {"a.py": "c" * 40, "b.py": "b" * 40},
            head_sha="2" * 40,
        )


def test_registry_tamper_fails_hash_validation():
    registry = _registry()
    registry["entries"]["STEP"]["artifacts"]["a.py"] = "c" * 40
    with pytest.raises(FrozenArtifactRegistryFailure, match="state hash"):
        validate_registry(registry)


def test_conflicting_duplicate_path_baselines_fail_closed():
    from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash

    registry = _registry()
    registry["entries"]["STEP2"] = {
        "status": "FROZEN",
        "checkpoint_id": "STEP2",
        "source_main_sha": "1" * 40,
        "artifacts": {"a.py": "c" * 40},
    }
    registry["state_hash"] = _hash(_payload_without_hash(registry))
    with pytest.raises(FrozenArtifactRegistryFailure, match="conflicting frozen baselines"):
        validate_registry(registry)


def test_contract_self_test_is_green():
    result = contract_self_test()
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


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "frozen_artifact_registry_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1_GREEN" in completed.stdout
