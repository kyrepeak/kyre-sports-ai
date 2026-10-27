from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
HELPER = ROOT / "devsystem" / "monster_runtime_identity_v1.py"
CERT = ROOT / "devsystem" / "monster_runtime_certification_v1.json"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "monster-step2g-prerender-runtime-identity-r1.json"
LEDGER = ROOT / "devsystem" / "task_ledgers" / "monster-step2g-prerender-runtime-identity-r1.json"
PROOF = ROOT / "runless_v2" / "monster_step2g_prerender_proof_r1.py"
RUNLESS_INIT = ROOT / "runless_v2" / "__init__.py"
TASK_ID = "monster-step2g-prerender-runtime-identity-r1"


def _load_proof():
    spec = importlib.util.spec_from_file_location("monster_step2g_prerender_proof_r1", PROOF)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_monster_runtime_identity_is_registered_as_shared_prerender_hook():
    text = APP.read_text(encoding="utf-8")
    assert "from devsystem.monster_runtime_identity_v1 import emit_runtime_identity_marker" in text
    assert "from devsystem.shared_runtime_lifecycle_v1 import run_shared_runtime_lifecycle" in text
    assert "render=render_app" in text
    assert "pre_render_hooks=(emit_runtime_identity_marker,)" in text
    assert "\nrender_app()\n" not in text
    assert "\nemit_runtime_identity_marker()\n" not in text


def test_runtime_identity_surface_remains_monster_owned_and_certified():
    helper = HELPER.read_text(encoding="utf-8")
    cert = json.loads(CERT.read_text(encoding="utf-8"))
    assert cert["authority"] == "MONSTER_ONLY"
    assert cert["certified_monster_sha"]
    assert cert["certified_monster_tree_sha"]
    assert '"owner": "MONSTER"' in helper
    assert 'payload.get("authority") != "MONSTER_ONLY"' in helper
    assert "certified_monster_sha" in helper
    assert "runtime_sha" in helper


def test_runless_plan_ledger_and_isolated_proof_lock_one_monster_authority_path():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    proof = _load_proof()
    assert plan["task_id"] == TASK_ID and plan["workstream"] == TASK_ID
    assert plan["source_main_sha"] == "e7af6a71018e43d08fff445b5c719aa256217bd5"
    assert plan["required_check"] == "runless-final-gate" and plan["required_check_app_id"] == 5204253
    assert plan["github_actions_fallback"] == 0
    assert ledger["authority"] == "MONSTER_ONLY"
    assert ledger["step2a"]["one_active_problem"] is True
    assert ledger["step2a"]["one_branch"] is True and ledger["step2a"]["one_pr"] is True
    assert ledger["anti_loop"]["blind_retry_allowed"] is False and ledger["anti_loop"]["duplicate_lane_allowed"] is False
    assert proof.AUTHORITY == "MONSTER_ONLY"
    assert proof.PR_NUMBER == 1857 and proof.BRANCH == "monster-step2g-prerender-runtime-identity-r1"
    assert proof.EXPECTED_MAIN_SHA == "e7af6a71018e43d08fff445b5c719aa256217bd5"


def test_isolated_proof_receipt_is_deterministic_and_rejects_foreign_evidence():
    proof = _load_proof()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    kwargs = {
        "candidate_sha": "1" * 40,
        "changed_paths": ["app.py"],
        "artifact_map": {"app.py": "2" * 40},
        "dependency_map": {"universal_page_experience_runtime_v5.py": "3" * 40},
        "evidence": [{"name": "focused", "ok": True, "detail": "MONSTER_ONLY"}],
        "plan": plan,
    }
    first = proof.build_receipt(**kwargs)
    second = proof.build_receipt(**kwargs)
    assert first == second and first["authority"] == "MONSTER_ONLY"
    assert proof.validate_receipt(first) == first
    poisoned = dict(kwargs)
    poisoned["evidence"] = [{"name": "foreign", "ok": True, "detail": "api2-foreign-state"}]
    try:
        proof.build_receipt(**poisoned)
    except Exception as exc:
        assert "FOREIGN" in str(exc).upper()
    else:
        raise AssertionError("foreign evidence must fail closed")


def test_preview_autoproof_is_exact_branch_and_secretless_in_source():
    text = RUNLESS_INIT.read_text(encoding="utf-8")
    assert "_monster_step2g_prerender_maybe_auto_prove" in text
    assert "monster-step2g-prerender-runtime-identity-r1" in text
    assert "prove_prerender_runtime_identity" in text
    assert "MONSTER_STEP2G_PRERENDER_AUTO_PROOF_GREEN" in text
    assert "RUNLESS_PROOF_AUTH_TOKEN" not in text


def test_repair_scope_does_not_change_sports_or_projection_logic():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["artifacts"] == [
        "app.py",
        "devsystem/monster_runtime_identity_v1.py",
        "devsystem/monster_runtime_certification_v1.json",
        "tests/test_devsystem_monster_step2g_prerender_runtime_identity_r1.py",
        "runless_v2/monster_step2g_prerender_proof_r1.py",
        "runless_v2/__init__.py",
        ".github/workflows/monster-step2g-prerender-runtime-identity-r1.yml",
        "devsystem/runless_proof_plans/monster-step2g-prerender-runtime-identity-r1.json",
        "devsystem/task_ledgers/monster-step2g-prerender-runtime-identity-r1.json",
    ]
