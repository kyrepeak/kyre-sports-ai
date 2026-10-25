from __future__ import annotations

from pathlib import Path

from devsystem.api2_frozen_artifact_registry_v1 import (
    REGISTRY_PATH,
    REGISTRY_REF,
    VERSION,
    contract_self_test,
)


ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "devsystem/api2_frozen_registry_lifecycle_v1.py"
WORKFLOW = ROOT / ".github/workflows/api2-proof-architecture-v1-step6-frozen-registry-lifecycle.yml"


def test_api2_registry_has_independent_authority_constants():
    assert VERSION == "API2_FROZEN_ARTIFACT_REGISTRY_V1"
    assert REGISTRY_REF == "refs/heads/api2-frozen-registry"
    assert REGISTRY_PATH == "devsystem/api2_frozen_registry_state_v1.json"


def test_api2_lifecycle_imports_only_api2_registry_authority():
    text = LIFECYCLE.read_text(encoding="utf-8")
    assert "from devsystem.api2_frozen_artifact_registry_v1 import" in text
    assert "from devsystem.frozen_artifact_registry_v1 import" not in text
    assert "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1" not in text
    assert "monster-frozen-artifact-registry" not in text


def test_api2_step6_workflow_fetches_only_api2_registry_authority():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git fetch origin api2-frozen-registry --depth=1" in text
    assert "FETCH_HEAD:devsystem/api2_frozen_registry_state_v1.json" in text
    assert "api2_frozen_artifact_registry_v1.py verify-head" in text
    assert "monster-frozen-artifact-registry" not in text
    assert "FETCH_HEAD:devsystem/frozen_artifact_registry_state_v1.json" not in text
    assert "frozen_artifact_registry_v1.py verify-head" not in text.replace(
        "api2_frozen_artifact_registry_v1.py verify-head", ""
    )


def test_api2_registry_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["intact_frozen_artifacts_pass"] is True
    assert result["mismatch_without_thaw_blocked"] is True
    assert result["exact_head_exact_blob_thaw_allowed"] is True
    assert result["wrong_head_thaw_blocked"] is True
    assert result["registry_tamper_blocked"] is True
    assert result["separate_authoritative_registry_ref"] is True
