from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    assert path.is_file(), f"required MONSTER module missing: {rel}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _receipt_payload(*, include_step2g: bool = True, convergence_green: bool = True):
    gates = {
        name: "GREEN"
        for name in (
            "step2a",
            "anti_loop",
            "step2c",
            "step2b",
            "execution",
            "step2d",
            "step2e",
            "step2f",
            "final_verify",
        )
    }
    if include_step2g:
        gates["step2g"] = "GREEN"
    convergence = {
        "status": "GREEN" if convergence_green else "BLOCKED",
        "evidence_digest": "a" * 64,
        "final_sha": "2" * 40,
        "deployment_id": "monster-prod-200",
        "stable_alias": "https://pickvault.streamlit.app",
        "runtime_sha": "2" * 40,
    }
    return {
        "task_id": "monster-step2g-final-production-convergence-v1",
        "candidate_sha": "1" * 40,
        "gates": gates,
        "regressions": {"status": "GREEN", "count": 1},
        "production": {
            "deployment_applicable": True,
            "deployment_id": "monster-prod-200",
            "stable_alias_target": "https://pickvault.streamlit.app",
        },
        "convergence": convergence,
        "rollback_anchor": {"sha": "0" * 40},
        "freeze_target": "MONSTER_STEP2G_FINAL_PRODUCTION_CONVERGENCE_V1_FROZEN",
        "evidence": {"source": "monster-only", "step2g": "green"},
    }


def test_permanent_stack_requires_step2g_as_mandatory_dependency():
    gate = _load(
        "mandatory_2c2d2e2f_permanent_enforcement_v1",
        "devsystem/mandatory_2c2d2e2f_permanent_enforcement_v1.py",
    )
    result = gate.validate()
    assert result["status"] == "GREEN"
    assert result["step2g_permanent"] is True
    assert result["final_green_requires_step2g"] is True
    assert result["final_frozen_requires_step2g"] is True


def test_authoritative_receipt_blocks_missing_step2g_gate():
    receipt = _load(
        "monster_authoritative_proof_receipt_v1",
        "devsystem/monster_authoritative_proof_receipt_v1.py",
    )
    result = receipt.build_receipt(_receipt_payload(include_step2g=False))
    assert result["status"] == "BLOCKED"
    assert "step2g" in result["reason"].lower()


def test_authoritative_receipt_blocks_non_green_convergence():
    receipt = _load(
        "monster_authoritative_proof_receipt_v1_b",
        "devsystem/monster_authoritative_proof_receipt_v1.py",
    )
    result = receipt.build_receipt(_receipt_payload(convergence_green=False))
    assert result["status"] == "BLOCKED"
    assert "convergence" in result["reason"].lower()


def test_authoritative_receipt_forbids_step2g_production_not_applicable_shortcut():
    receipt = _load(
        "monster_authoritative_proof_receipt_v1_no_na",
        "devsystem/monster_authoritative_proof_receipt_v1.py",
    )
    payload = _receipt_payload()
    payload["production"] = {
        "deployment_applicable": False,
        "proof": "NOT_APPLICABLE_READ_ONLY_CONTROL_PLANE",
    }
    result = receipt.build_receipt(payload)
    assert result["status"] == "BLOCKED"
    assert "production" in result["reason"].lower()


def test_authoritative_receipt_binds_step2g_digest_and_authorizes_freeze_checkpoint():
    receipt = _load(
        "monster_authoritative_proof_receipt_v1_c",
        "devsystem/monster_authoritative_proof_receipt_v1.py",
    )
    result = receipt.build_receipt(_receipt_payload())
    assert result["status"] == "GREEN"
    assert result["gates"]["step2g"] == "GREEN"
    assert result["step2g_evidence_digest"] == "a" * 64
    assert result["frozen_checkpoint_authorized"] is True
    assert result["frozen_authorized"] is False
    assert receipt.validate_receipt(result)["status"] == "GREEN"
