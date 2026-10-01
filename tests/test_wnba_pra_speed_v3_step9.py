from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/wnba_pra_speed_v3_step9_final_cert.py"
LEDGER = ROOT / "devsystem/task_ledgers/wnba-pra-speed-v3-step9-final-cert.json"
WORKFLOW = ROOT / ".github/workflows/wnba-pra-speed-v3-step9-final-cert.yml"


def _source() -> str:
    return CERT.read_text(encoding="utf-8")


def test_step9_direct_script_bootstraps_repo_root_permanently():
    source = _source()
    assert "if __package__ in {None, \"\"}:" in source
    assert "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))" in source


def test_step9_is_certification_only_and_keeps_final_speed_budgets():
    source = _source()
    tree = ast.parse(source)
    assert tree is not None
    assert "WARM_SAME_SESSION_SECONDS_MAX = 0.75" in source
    assert "CACHED_COLD_SECONDS_MAX = 1.50" in source
    assert "TRUE_COLD_SECONDS_MAX = 2.50" in source
    assert "VISIBLE_CONTINUITY_SECONDS_MAX = 0.75" in source
    assert "step5_profile.run(" in source
    assert "step8_profile.run(" in source
    assert '"frozen_steps_1_8_preserved": True' in source
    assert '"product_runtime_changed_by_step9": False' in source
    assert '"projection_math_changed_by_step9": False' in source
    assert '"market_math_changed_by_step9": False' in source
    assert '"data_meaning_changed_by_step9": False' in source


def test_step9_requires_browser_resident_step8_continuity():
    source = _source()
    assert '"game_card_continuity"' in source
    assert '"client_preview"' in source
    assert "server_shell_runtime_fallback_preserved" in source
    assert "frozen_steps_1_7_preserved" in source
    assert "WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_GREEN" in source


def test_step9_emits_final_green_and_frozen_tokens():
    source = _source()
    required = (
        "WNBA_PRA_SPEED_V3_STEP9_TRUE_COLD_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_WARM_SAME_SESSION_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_CACHED_COLD_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_VISIBLE_CONTINUITY_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_FROZEN_STEPS1_8_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_PROFILE_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_GREEN",
        "WNBA_PRA_SPEED_V3_STEP9_FROZEN",
    )
    for token in required:
        assert token in source


def test_step9_ledger_is_done_and_step2a_locked():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["project"] == "WNBA PRA Speed V3"
    assert ledger["step"] == 9
    assert ledger["total_steps"] == 9
    assert ledger["status"] == "DONE"
    assert ledger["speed_targets"] == {
        "warm_same_session_seconds_max": 0.75,
        "cached_cold_seconds_max": 1.5,
        "true_cold_seconds_max": 2.5,
        "visible_continuity_seconds_max": 0.75,
    }
    assert ledger["protected"]["speed_v3_steps_1_8"] is True
    assert ledger["two_a"]["one_active_pr_max"] == 1
    assert ledger["two_a"]["no_duplicate_async_runs"] is True
    assert ledger["two_a"]["no_unchanged_failed_reruns"] is True
    assert ledger["action_log"]["head_chain_hash"] == "0" * 64
    assert ledger["action_log"]["events"] == []
    assert ledger["action_log"]["consumed_receipts"] == []


def test_step9_workflow_has_exact_scope_and_main_production_gate():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "WNBA PRA Speed V3 Step 9 Final Certification" in workflow
    assert "Enforce exact Step-9 PR scope" in workflow
    assert "Run Step-9 permanent contract" in workflow
    assert "Run final production speed certification" in workflow
    assert "python -m devsystem.wnba_pra_speed_v3_step9_final_cert" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP9_IMPORT_PATH_REPAIR_GREEN" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "WNBA_PRA_SPEED_V3_STEP9_BRANCH_GREEN" in workflow
