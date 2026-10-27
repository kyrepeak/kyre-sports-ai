from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
HELPER = ROOT / "devsystem" / "monster_runtime_identity_v1.py"
CERT = ROOT / "devsystem" / "monster_runtime_certification_v1.json"
RUNLESS_INIT = ROOT / "runless_v2" / "__init__.py"
PROOF = ROOT / "runless_v2" / "monster_step2g_proof_v1.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "monster-step2g-production-identity-promotion-v1.json"

CERTIFIED_SHA = "b3724b245257c32c7e51f69bd7f340575712e528"
CERTIFIED_TREE = "11108c69983273ecd79de3bc1a94a6ca58aee11a"
CERTIFIED_DIGEST = "d20804fdbb4bd1bc99259c0e2256f12a863d9e6293d32ca687cea18157e8f2f5"


def _load_proof():
    spec = importlib.util.spec_from_file_location("monster_step2g_proof_v1", PROOF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_certification_descriptor_is_monster_only_and_exact():
    payload = json.loads(CERT.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": "MONSTER_STEP2G_RUNTIME_CERTIFICATION_V1",
        "authority": "MONSTER_ONLY",
        "certified_monster_sha": CERTIFIED_SHA,
        "certified_monster_tree_sha": CERTIFIED_TREE,
        "certified_artifact_digest": CERTIFIED_DIGEST,
    }


def test_production_entrypoint_uses_shared_lifecycle_without_replacing_terminal_router():
    text = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page2_route_restore_v1" in text
    assert "from devsystem.monster_runtime_identity_v1 import emit_runtime_identity_marker" in text
    assert "from devsystem.shared_runtime_lifecycle_v1 import run_shared_runtime_lifecycle" in text
    assert "render=render_app" in text
    assert "pre_render_hooks=(emit_runtime_identity_marker,)" in text


def test_runtime_helper_is_monster_owned_and_descriptor_driven():
    text = HELPER.read_text(encoding="utf-8")
    assert 'CERTIFICATION_PATH = "devsystem/monster_runtime_certification_v1.json"' in text
    assert '"owner": "MONSTER"' in text
    assert 'payload.get("authority") != "MONSTER_ONLY"' in text
    assert "certified_monster_sha" in text
    assert "runtime_sha" in text
    assert "emit_runtime_identity_marker" in text


def test_promotion_does_not_modify_sports_or_projection_logic():
    assert HELPER.is_file() and CERT.is_file()
    helper = HELPER.read_text(encoding="utf-8")
    forbidden = ("projection_weight", "sportsbook_projection", "odds_router", "market_probability")
    assert all(token not in helper.lower() for token in forbidden)


def test_monster_proof_receipt_is_deterministic_owned_and_foreign_evidence_fails_closed():
    proof = _load_proof()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    kwargs = {
        "candidate_sha": "1" * 40,
        "expected_main_sha": proof.EXPECTED_MAIN_SHA,
        "changed_paths": ["app.py", "devsystem/monster_runtime_identity_v1.py"],
        "artifact_map": {"app.py": "2" * 40},
        "dependency_map": {"streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page2_route_restore_v1.py": "3" * 40},
        "evidence": [{"name": "focused", "ok": True, "detail": "MONSTER_ONLY"}],
        "plan": plan,
    }
    first = proof.build_receipt(**kwargs)
    second = proof.build_receipt(**kwargs)
    assert first == second
    assert first["authority"] == "MONSTER_ONLY"
    assert proof.validate_receipt(first) == first
    poisoned = dict(kwargs)
    poisoned["evidence"] = [{"name": "foreign", "ok": True, "detail": "api2-foreign-state"}]
    try:
        proof.build_receipt(**poisoned)
    except Exception as exc:
        assert "FOREIGN" in str(exc).upper()
    else:
        raise AssertionError("foreign-system evidence must fail closed")


def test_preview_autoproof_is_guarded_and_uses_monster_authority_only():
    text = RUNLESS_INIT.read_text(encoding="utf-8")
    assert "_monster_step2g_maybe_auto_prove" in text
    assert 'VERCEL_ENV' in text and 'preview' in text
    assert 'monster-step2g-production-identity-promotion-v1' in text
    assert "prove_production_promotion" in text
    assert "MONSTER_STEP2G_AUTO_PROOF_GREEN" in text
    assert "RUNLESS_PROOF_AUTH_TOKEN" not in text


def test_monster_proof_path_never_reads_shared_control_state():
    text = PROOF.read_text(encoding="utf-8")
    forbidden = (
        "monster-scope-aware-execution-leases",
        "monster-frozen-artifact-registry",
        "runless-proof-receipts",
        "monster-finalization-ledger-v2",
        "project=\"API2\"",
    )
    assert all(token not in text for token in forbidden)
    assert 'RECEIPT_REF = "monster-step2g-proof-receipts-v1"' in text
    assert 'AUTHORITY = "MONSTER_ONLY"' in text


def test_proof_plan_compiles_and_tests_monster_only_authority_surface():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    flat = " ".join(" ".join(command) for command in plan["commands"])
    assert "tests/test_devsystem_monster_step2g_production_promotion_v1.py" in flat
    assert "runless_v2/monster_step2g_proof_v1.py" in flat
    assert "runless_v2/__init__.py" in flat
    assert "runless_v2/monster_step2g_proof_v1.py" in plan["artifacts"]
    assert "runless_v2/__init__.py" in plan["artifacts"]
