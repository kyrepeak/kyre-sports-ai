from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "supabase/migrations/20261017_runless_post_merge_public_failure_recovery_v1.sql"
TRANSPORT = ROOT / "supabase/migrations/20261017_runless_post_merge_public_failure_transport_v1.sql"


def test_recovery_sql_verifies_github_merge_identity_before_state_change():
    sql = RECOVERY.read_text().lower()
    assert "extensions.http" in sql
    assert "/pulls/" in sql
    assert "/compare/" in sql
    assert "merge_commit_sha" in sql
    assert "head" in sql and "sha" in sql
    assert "merged_at" in sql
    assert "current_main_sha" in sql
    assert "post_merge_public_failure" in sql


def test_recovery_sql_preserves_proof_evidence_and_retires_fingerprint():
    sql = RECOVERY.read_text().lower().replace(" ", "").replace("\n", "")
    assert "when'merged'thenp_target_statein('post_merge_verify','failed')" in sql
    assert "failure_class='public_proof'" in sql
    assert "failed_fingerprints" in sql
    assert "receipt_digest" in sql and "gate_check_run_id" in sql
    assert "terminal_at" in sql


def test_recovery_sql_is_idempotent_and_rejects_live_workstream_lease():
    sql = RECOVERY.read_text().lower()
    assert "workstream_leases" in sql
    assert "runless_v2_workstream_busy" in sql
    assert "v_proof.state = 'failed'" in sql
    assert "public_proof" in sql


def test_transport_is_private_server_side_wrapper():
    sql = TRANSPORT.read_text().lower()
    assert "request_post_merge_public_failure_transport" in sql
    assert "security definer" in sql
    assert "revoke all" in sql and "from public" in sql
    assert "record_post_merge_public_failure" in sql
