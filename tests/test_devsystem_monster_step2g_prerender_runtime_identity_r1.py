from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
HELPER = ROOT / "devsystem" / "monster_runtime_identity_v1.py"
CERT = ROOT / "devsystem" / "monster_runtime_certification_v1.json"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "monster-step2g-prerender-runtime-identity-r1.json"
LEDGER = ROOT / "devsystem" / "task_ledgers" / "monster-step2g-prerender-runtime-identity-r1.json"
TASK_ID = "monster-step2g-prerender-runtime-identity-r1"


def test_monster_runtime_identity_mounts_before_any_page_renderer_can_interrupt():
    text = APP.read_text(encoding="utf-8")
    assert "from devsystem.monster_runtime_identity_v1 import emit_runtime_identity_marker" in text
    assert text.count("emit_runtime_identity_marker()") == 1
    assert text.count("render_app()") == 1
    marker_call = text.index("emit_runtime_identity_marker()")
    render_call = text.index("render_app()")
    assert marker_call < render_call, "MONSTER runtime identity must mount before page rendering"


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


def test_runless_plan_and_ledger_lock_one_monster_authority_path():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert plan["task_id"] == TASK_ID
    assert plan["workstream"] == TASK_ID
    assert plan["source_main_sha"] == "e7af6a71018e43d08fff445b5c719aa256217bd5"
    assert plan["required_check"] == "runless-final-gate"
    assert plan["required_check_app_id"] == 5204253
    assert plan["github_actions_fallback"] == 0
    assert ledger["authority"] == "MONSTER_ONLY"
    assert ledger["step2a"]["one_active_problem"] is True
    assert ledger["step2a"]["one_branch"] is True
    assert ledger["step2a"]["one_pr"] is True
    assert ledger["anti_loop"]["blind_retry_allowed"] is False
    assert ledger["anti_loop"]["duplicate_lane_allowed"] is False


def test_repair_scope_does_not_change_sports_or_projection_logic():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["artifacts"] == [
        "app.py",
        "devsystem/monster_runtime_identity_v1.py",
        "devsystem/monster_runtime_certification_v1.json",
        "tests/test_devsystem_monster_step2g_prerender_runtime_identity_r1.py",
        "devsystem/runless_proof_plans/monster-step2g-prerender-runtime-identity-r1.json",
        "devsystem/task_ledgers/monster-step2g-prerender-runtime-identity-r1.json",
    ]
