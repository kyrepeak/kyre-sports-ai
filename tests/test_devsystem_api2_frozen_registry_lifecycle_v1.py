from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.api2_frozen_registry_lifecycle_v1 import (
    RegistryLifecycleFailure,
    _sample_registry,
    audit_registry,
    contract_self_test,
    plan_baseline_forward_port,
    registry_progress,
)
from devsystem.frozen_artifact_registry_v1 import validate_registry


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/devsystem-targeted-ci.yml"


def test_clean_registry_audit_is_green():
    result = audit_registry(_sample_registry())
    assert result["status"] == "GREEN"
    assert result["decision"] == "REGISTRY_LIFECYCLE_CLEAN"
    assert result["active_thaw_count"] == 2
    assert result["active_thaw_file_pair_count"] == 2


def test_forward_port_is_atomic_across_all_frozen_owners():
    source = _sample_registry()
    before = deepcopy(source)
    result = plan_baseline_forward_port(
        source,
        updates={
            "shared.yml": {
                "from_blob": "a" * 40,
                "to_blob": "b" * 40,
            }
        },
        source_main_sha="4" * 40,
    )
    assert source == before
    assert result["next_revision"] == before["revision"] + 1
    assert len(result["updated_entries"]) == 2
    assert result["registry"]["entries"]["STEP_A"]["artifacts"]["shared.yml"] == "b" * 40
    assert result["registry"]["entries"]["STEP_B"]["artifacts"]["shared.yml"] == "b" * 40
    validate_registry(result["registry"])


def test_forward_port_retires_obsolete_thaw_pairs_without_rebasing_authority():
    result = plan_baseline_forward_port(
        _sample_registry(),
        updates={
            "shared.yml": {
                "from_blob": "a" * 40,
                "to_blob": "b" * 40,
            }
        },
        source_main_sha="4" * 40,
    )
    assert [x["thaw_id"] for x in result["retired_thaw_file_pairs"]] == ["THAW-SHARED-OLD"]
    assert result["retired_empty_thaw_grants"] == ["THAW-SHARED-OLD"]
    assert [x["thaw_id"] for x in result["registry"]["active_thaws"]] == ["THAW-KEEP"]
    assert result["registry"]["active_thaws"][0]["files"]["keep.py"]["from_blob"] == "c" * 40


def test_wrong_baseline_update_fails_closed():
    with pytest.raises(RegistryLifecycleFailure, match="differs from frozen baseline"):
        plan_baseline_forward_port(
            _sample_registry(),
            updates={
                "shared.yml": {
                    "from_blob": "c" * 40,
                    "to_blob": "b" * 40,
                }
            },
            source_main_sha="4" * 40,
        )


def test_retry_requires_registry_state_hash_progress():
    old = "1" * 64
    new = "2" * 64
    assert registry_progress(old, new)["refetch_retry_allowed"] is True
    same = registry_progress(new, new)
    assert same["decision"] == "REGISTRY_STATE_UNCHANGED"
    assert same["refetch_retry_allowed"] is False


def test_workflow_audits_lifecycle_before_strict_head_verify_and_bounds_refresh():
    text = WORKFLOW.read_text(encoding="utf-8")
    audit = "api2_frozen_registry_lifecycle_v1.py audit"
    strict = "frozen_artifact_registry_v1.py verify-head"
    assert audit in text
    assert strict in text
    assert text.index(audit) < text.index(strict)
    assert "for attempt in 1 2 3" in text
    assert "API2_STEP6_REGISTRY_NO_PROGRESS_BLOCKED" in text
    assert 'current_hash" = "$last_hash' in text
    assert "API2_STEP6_REGISTRY_RETRY_BUDGET_EXHAUSTED" in text


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["atomic_multi_checkpoint_forward_port"] is True
    assert result["obsolete_thaw_pair_retired"] is True
    assert result["unrelated_thaw_preserved"] is True
    assert result["wrong_from_blob_blocked"] is True
    assert result["state_progress_required_for_retry"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False
