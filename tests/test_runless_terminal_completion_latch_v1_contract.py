from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "20261015_runless_terminal_completion_latch_v1.sql"


def test_step4_migration_defines_resumable_terminal_latch_contract():
    text = MIGRATION.read_text().lower()

    assert "create or replace function runless_v2.resume_closeout_green_frozen" in text
    assert "for update" in text
    assert "pg_advisory_xact_lock" in text
    assert "runless_v2_workstream_busy" in text
    assert "runless_v2_closeout_evidence_mismatch" in text
    assert "runless_v2_closeout_non_resumable_state" in text

    for state in (
        "merge_authorized",
        "merged",
        "post_merge_verify",
        "freeze",
        "read_back",
        "green_frozen",
    ):
        assert state in text

    assert "state='merged'" in text
    assert "state='post_merge_verify'" in text
    assert "state='freeze'" in text
    assert "state='read_back'" in text
    assert "state='green_frozen'" in text
    assert "terminal_at" in text


def test_terminal_latch_is_idempotent_and_does_not_regress_green_frozen():
    text = MIGRATION.read_text().lower()
    green = text.index("if v_proof.state = 'green_frozen'")
    merged = text.index("if v_proof.state = 'merge_authorized'")

    assert green < merged
    terminal_block = text[green:merged]
    assert "return v_proof" in terminal_block
    assert "update runless_v2.proof_runs" not in terminal_block
