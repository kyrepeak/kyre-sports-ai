from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/wnba_pra_repair_v1_step1_load_audit.py"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-repair-v1-step1-load-audit.json"
WORKFLOW = ROOT / ".github/workflows/wnba-pra-repair-v1-step1-load-audit.yml"


def _source() -> str:
    return CERT.read_text(encoding="utf-8")


def test_step1_is_proof_only_and_parses():
    source = _source()
    assert ast.parse(source)
    assert 'PROJECT = "WNBA PRA Repair V1"' in source
    assert 'STEP = "1/7"' in source
    assert "PRODUCT_RUNTIME_CHANGED = False" in source
    assert "MODEL_CHANGED = False" in source
    assert "PROJECTION_MATH_CHANGED = False" in source
    assert "MARKET_MATH_CHANGED = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE_CHANGED = False" in source


def test_step1_uses_current_step9_runtime_and_all_three_pages():
    source = _source()
    assert "streamlit_memory_lazy_router_wnba_pra_speed_v3_step9_duplicate_key_guard.py" in source
    assert "wnba_pra_slate_v2_step2.py" in source
    assert "wnba_pra_game_center_v2_step3.py" in source
    assert "wnba_pra_player_intelligence_v2_step4.py" in source
    assert "render_slate_page" in source
    assert "render_game_center" in source
    assert "render_player_intelligence" in source


def test_step1_reuses_one_frozen_authoritative_browser_pass():
    source = _source()
    assert "speed9._prime_wnba_pra_route" in source
    assert "nav._find_game_date()" in source
    assert "nav.run(" in source
    assert "nav.CERTIFIED_GAME_DATES = (target_date,)" in source
    assert "Step 2A: one authoritative browser pass only" in source


def test_step1_requires_slate_game_player_and_round_trip_green():
    source = _source()
    required = (
        "WNBA_PRA_REPAIR_V1_STEP1_SLATE_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP1_GAME_CENTER_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP1_PLAYER_INTELLIGENCE_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP1_ROUND_TRIP_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP1_FROZEN_SPEED_V3_STEPS1_9_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP1_GREEN",
        "WNBA_PRA_REPAIR_V1_STEP1_FROZEN",
    )
    for token in required:
        assert token in source


def test_step1_ledger_locks_step2a_and_protects_previous_nine_steps():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["project"] == "WNBA PRA Repair V1"
    assert ledger["step"] == 1
    assert ledger["total_steps"] == 7
    assert ledger["status"] == "DONE"
    assert ledger["protected"]["wnba_pra_speed_v3_steps_1_9"] is True
    assert ledger["two_a"]["one_active_problem"] is True
    assert ledger["two_a"]["one_active_branch"] is True
    assert ledger["two_a"]["one_active_pr_max"] == 1
    assert ledger["two_a"]["no_duplicate_async_runs"] is True
    assert ledger["two_a"]["no_unchanged_failed_reruns"] is True


def test_step1_workflow_has_pr_contract_and_merged_main_public_gate():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "WNBA PRA Repair V1 Step 1 Load Audit" in workflow
    assert "Enforce exact Step-1 scope" in workflow
    assert "Run Step-1 permanent contract" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "python -m devsystem.wnba_pra_repair_v1_step1_load_audit" in workflow
    assert "WNBA_PRA_REPAIR_V1_STEP1_BRANCH_GREEN" in workflow
