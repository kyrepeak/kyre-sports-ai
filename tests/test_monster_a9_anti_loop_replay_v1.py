from __future__ import annotations

from devsystem.a9_anti_loop_replay_v1 import run_replay


def test_a9_replay_reaches_finish_line_without_looping():
    result = run_replay()

    assert result["status"] == "GREEN"
    assert result["scenario"] == "MONSTER_A9_ANTI_LOOP_REPLAY_V1"
    assert result["duplicate_proofs_rejected"] >= 1
    assert result["closed_checkpoint_reopens_rejected"] >= 1
    assert result["second_blockers_deferred"] >= 1
    assert result["max_active_blockers"] == 1
    assert result["in_scope_approval_stops"] == 0
    assert result["final_task_status"] == "DONE"
    assert result["remaining_checkpoints"] == 0
    assert result["post_finish_decision"] == "TASK_COMPLETE"
    assert result["invented_post_finish_checkpoints"] == 0
