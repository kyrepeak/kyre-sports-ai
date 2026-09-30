from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devsystem.mandatory_2a_adversarial_certification_v1 import (
    contract_self_test,
)


def test_permanent_adversarial_matrix_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["attack_count"] >= 12
    assert result["all_attacks_fail_closed"] is True
    assert result["legal_global_proof_valid"] is True
    assert result["step4_preserved"] is True
    assert result["steps1_3_preserved"] is True
    assert result["safe_continue_no_user"] is True
    assert result["product_runtime_mutation"] is False

    attacks = result["attacks"]
    assert attacks["stale_main_blocked"] is True
    assert attacks["stale_head_blocked"] is True
    assert attacks["frozen_checkpoint_blocked"] is True
    assert attacks["frozen_brain_mutation_blocked"] is True
    assert attacks["replay_blocked"] is True
    assert attacks["missing_authorization_blocked"] is True
    assert attacks["competing_run_blocked"] is True
    assert attacks["duplicate_poll_skipped"] is True
    assert attacks["unknown_action_blocked"] is True
    assert attacks["tampered_proof_blocked"] is True
    assert attacks["step5_final_layer_required"] is True


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "mandatory_2a_adversarial_certification_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_2A_ADVERSARIAL_CERTIFICATION_V1_GREEN" in completed.stdout
