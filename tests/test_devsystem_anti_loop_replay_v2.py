from devsystem.anti_loop_replay_v2 import run_replay


def test_v2_adversarial_replay_is_green():
    result = run_replay()
    assert result["status"] == "GREEN"
    assert result["exact_duplicates_denied"] >= 1
    assert result["semantic_root_cause_loops_denied"] >= 2
    assert result["stagnation_locks"] >= 1
    assert result["closed_checkpoint_reopens_denied"] >= 1
    assert result["second_blockers_deferred"] >= 1
    assert result["invalid_overrides_denied"] >= 1
    assert result["valid_single_use_overrides"] == 1
    assert result["receipt_replays_denied"] >= 1
    assert result["tamper_attempts_denied"] >= 1
    assert result["final_task_status"] == "DONE"
    assert result["remaining_checkpoints"] == 0
    assert result["post_finish_decision"] == "TASK_COMPLETE"
    assert result["invented_post_finish_checkpoints"] == 0


def test_v2_replay_runs_directly_as_script():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "anti_loop_replay_v2.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_ANTI_LOOP_V2_REPLAY_GREEN" in completed.stdout
