from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNLESS_INIT = ROOT / "runless_v2" / "__init__.py"
RUNLESS_CONFIG = ROOT / "runless_v2" / "config.py"
PROOF = ROOT / "runless_v2" / "guardian_shared_runtime_freeze_closeout_proof_v1.py"
PLAN = ROOT / "devsystem" / "runless_proof_plans" / "guardian-shared-runtime-lifecycle-freeze-closeout-v1.json"

BRANCH = "guardian-shared-runtime-lifecycle-freeze-closeout-v1"
BASELINE_INIT_BLOB = "994b966597295686946e49a647d73e5a9b57bb81"


def test_monster_frozen_runless_init_has_no_guardian_bootstrap():
    source = RUNLESS_INIT.read_text(encoding="utf-8")
    assert "_guardian_shared_runtime_lifecycle_maybe_auto_prove" not in source
    assert "guardian_shared_runtime_lifecycle_proof_v1" not in source
    assert "GUARDIAN_SHARED_RUNTIME_AUTO_PROOF_GREEN" not in source


def test_guardian_closeout_bootstrap_moves_to_nonfrozen_runless_config():
    source = RUNLESS_CONFIG.read_text(encoding="utf-8")
    assert "_guardian_shared_runtime_freeze_closeout_maybe_auto_prove" in source
    assert BRANCH in source
    assert "guardian_shared_runtime_freeze_closeout_proof_v1" in source
    assert "GUARDIAN_SHARED_RUNTIME_FREEZE_CLOSEOUT_AUTO_PROOF_GREEN" in source


def test_guardian_closeout_has_its_own_proof_module_and_plan():
    assert PROOF.is_file(), "Guardian closeout Runless proof publisher is missing"
    assert PLAN.is_file(), "Guardian closeout Runless proof plan is missing"
