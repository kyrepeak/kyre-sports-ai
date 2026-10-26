from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "devsystem" / "monster_step2g_frozen_checkpoint_v1.py"


def _load():
    assert MODULE.is_file(), "MONSTER Step 2G frozen checkpoint module is required"
    spec = importlib.util.spec_from_file_location("monster_step2g_frozen_checkpoint_v1", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _payload():
    return {
        "checkpoint_id": "MONSTER_STEP2G_FINAL_PRODUCTION_CONVERGENCE_V1_FROZEN",
        "certified_monster_sha": "1" * 40,
        "certified_monster_tree_sha": "2" * 40,
        "production_runtime_sha": "3" * 40,
        "production_runtime_tree_sha": "4" * 40,
        "stable_alias": "https://pickvault.streamlit.app",
        "deployment_id": "monster-streamlit-" + "3" * 12,
        "step2g_evidence_digest": "a" * 64,
        "proof_artifact_digest": "b" * 64,
        "rollback_anchor_sha": "0" * 40,
        "runtime_identity": {
            "owner": "MONSTER",
            "certified_monster_sha": "1" * 40,
            "runtime_sha": "3" * 40,
        },
    }


def test_checkpoint_is_monster_only_deterministic_and_readback_validatable():
    mod = _load()
    first = mod.build_checkpoint(**_payload())
    second = mod.build_checkpoint(**_payload())
    assert first == second
    assert first["authority"] == "MONSTER_ONLY"
    assert first["status"] == "FROZEN"
    assert first["checkpoint_id"].startswith("MONSTER_")
    assert len(first["checkpoint_digest"]) == 64
    result = mod.validate_checkpoint(first)
    assert result["status"] == "GREEN"
    assert result["readback_verified"] is True
    assert result["checkpoint_digest"] == first["checkpoint_digest"]


def test_checkpoint_rejects_foreign_system_evidence():
    mod = _load()
    payload = _payload()
    payload["runtime_identity"] = {"owner": "api2", "sha": "9" * 40}
    try:
        mod.build_checkpoint(**payload)
    except Exception as exc:
        assert "foreign" in str(exc).lower() or "api" in str(exc).lower()
    else:
        raise AssertionError("foreign-system evidence must fail closed")


def test_checkpoint_rejects_identity_and_digest_drift():
    mod = _load()
    checkpoint = mod.build_checkpoint(**_payload())
    tampered = dict(checkpoint)
    tampered["production_runtime_sha"] = "9" * 40
    try:
        mod.validate_checkpoint(tampered)
    except Exception:
        pass
    else:
        raise AssertionError("tampered checkpoint must fail closed")
