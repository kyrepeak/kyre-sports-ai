from copy import deepcopy

import pytest

from runless_proof_plane.step6_registry import (
    FREEZE_TOKEN,
    STEP6_ARTIFACTS,
    build_step6_registry_update,
)


MERGED_SHA = "4b7c1bd0ac0708f9b711430b3fec0bb137f46609"


def _registry():
    return {
        "revision": 136,
        "source_main_sha": "19584f7ef016de66a0fd4a8ce907c45efac0ca8f",
        "state_hash": "old",
        "entries": {
            "OLD": {
                "status": "FROZEN",
                "checkpoint_id": "OLD",
                "source_main_sha": "19584f7ef016de66a0fd4a8ce907c45efac0ca8f",
                "artifacts": {"old.py": "oldblob"},
            }
        },
        "active_thaws": [
            {
                "thaw_id": "UNRELATED",
                "status": "ACTIVE",
                "target_head_sha": "a" * 40,
                "files": {"elsewhere.py": {"from_blob": "x", "to_blob": "y"}},
            }
        ],
    }


def _artifacts():
    return {path: f"blob-{i}" for i, path in enumerate(sorted(STEP6_ARTIFACTS), 1)}


def test_step6_freeze_scope_is_only_the_five_additive_verification_artifacts():
    assert FREEZE_TOKEN == "WNBA_PRA_REPAIR_V1_STEP6_FROZEN"
    assert set(STEP6_ARTIFACTS) == {
        "wnba_pra_repair_v1_step6_completeness_sweep.py",
        "tests/test_wnba_pra_repair_v1_step6.py",
        "devsystem/wnba_pra_repair_v1_step6_completeness_sweep_cert.py",
        "devsystem/runless_proof_plans/wnba-pra-repair-v1-step6-completeness-sweep.json",
        "devsystem/task_ledgers/wnba-pra-repair-v1-step6-completeness-sweep.json",
    }


def test_step6_freeze_preserves_unrelated_thaws_and_adds_one_revision():
    current = _registry()
    thaws_before = deepcopy(current["active_thaws"])
    updated = build_step6_registry_update(current, _artifacts(), MERGED_SHA)

    assert updated["revision"] == 137
    assert updated["source_main_sha"] == MERGED_SHA
    assert updated["active_thaws"] == thaws_before
    assert updated["entries"][FREEZE_TOKEN] == {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MERGED_SHA,
        "artifacts": _artifacts(),
    }
    assert updated["state_hash"] != "old"


def test_step6_freeze_fails_closed_on_active_thaw_overlap():
    current = _registry()
    current["active_thaws"][0]["files"] = {STEP6_ARTIFACTS[0]: {"from_blob": "x", "to_blob": "y"}}
    with pytest.raises(RuntimeError, match="STEP6_CONFLICTING_THAW"):
        build_step6_registry_update(current, _artifacts(), MERGED_SHA)


def test_step6_freeze_fails_closed_on_conflicting_frozen_baseline():
    current = _registry()
    current["entries"]["OLD"]["artifacts"] = {STEP6_ARTIFACTS[0]: "different-blob"}
    with pytest.raises(RuntimeError, match="STEP6_FROZEN_BASELINE_CONFLICT"):
        build_step6_registry_update(current, _artifacts(), MERGED_SHA)
