from pathlib import Path

from runless_v2.models import ProofState

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261017_runless_base_drift_authority_supersession_v1.sql"
BASE_MIGRATION = ROOT / "supabase/migrations/20261013_runless_v2_durable_state.sql"


def sql() -> str:
    assert MIGRATION.exists(), "base-drift supersession migration must exist"
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_superseded_base_drift_is_terminal_historical_state():
    assert ProofState.SUPERSEDED_BASE_DRIFT.value == "SUPERSEDED_BASE_DRIFT"
    text = sql()
    assert "'superseded_base_drift'" in text
    assert "when 'merge_authorized' then p_target_state in ('merged','superseded_base_drift')" in text
    assert "when 'superseded_base_drift'" not in text


def test_authority_supersessions_table_has_required_identity_and_uniqueness():
    text = sql()
    assert "create table if not exists runless_v2.authority_supersessions" in text
    for column in (
        "supersession_id", "workstream", "old_proof_id", "old_candidate_sha",
        "old_expected_main_sha", "successor_candidate_sha", "successor_expected_main_sha",
        "reason", "github_pr_number", "github_branch", "old_gate_check_run_id",
        "old_receipt_digest", "created_at",
    ):
        assert column in text
    assert "unique (old_proof_id)" in text
    assert "unique (workstream, successor_candidate_sha)" in text


def test_supersession_rpc_requires_merge_authorized_no_live_lease_and_old_evidence():
    text = sql()
    assert "function runless_v2.supersede_base_drift_authority" in text
    assert "pg_advisory_xact_lock" in text
    assert "v_old.state <> 'merge_authorized'" in text
    assert "expires_at > v_now" in text
    assert "runless_v2_supersession_workstream_busy" in text
    assert "receipt_digest is null" in text
    assert "gate_check_run_id is null" in text
    assert "runless_v2_supersession_missing_evidence" in text
    assert "state = 'superseded_base_drift'" in text


def test_same_supersession_is_idempotent_but_different_successor_collides():
    text = sql()
    assert "runless_v2_supersession_identity_collision" in text
    assert "return v_existing" in text
    assert "successor_candidate_sha <> p_successor_candidate_sha" in text


def test_claim_workstream_ignores_superseded_historical_authority():
    text = BASE_MIGRATION.read_text(encoding="utf-8").lower()
    authority_conflict_block = text[text.index("create or replace function runless_v2.claim_workstream"):]
    conflict_slice = authority_conflict_block[:14000]
    assert "p.state in ('merge_authorized','merged','post_merge_verify','freeze','read_back')" in conflict_slice
    assert "superseded_base_drift" not in conflict_slice.split("select * into v_lease", 1)[0]
