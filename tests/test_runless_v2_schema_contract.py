from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261013_runless_v2_durable_state.sql"


def sql() -> str:
    assert MIGRATION.exists(), "Runless V2 migration must exist"
    return MIGRATION.read_text().lower()


def test_schema_and_all_control_tables_exist():
    text = sql()
    assert "create schema if not exists runless_v2" in text
    for table in ("proof_runs", "workstream_leases", "failed_fingerprints", "receipt_mirrors"):
        assert re.search(rf"create\s+table\s+if\s+not\s+exists\s+runless_v2\.{table}\b", text)


def test_all_six_atomic_rpcs_exist():
    text = sql()
    for fn in (
        "claim_workstream",
        "renew_workstream",
        "advance_proof_state",
        "record_failure_and_release",
        "record_merge_authorized_and_release_execution",
        "closeout_green_frozen",
    ):
        assert re.search(rf"create\s+or\s+replace\s+function\s+runless_v2\.{fn}\b", text)


def test_claim_serializes_per_workstream_and_uses_database_time():
    text = sql()
    assert "pg_advisory_xact_lock" in text
    assert "hashtextextended" in text or "hashtext" in text
    assert "clock_timestamp()" in text or "now()" in text or "current_timestamp" in text
    assert "runless_v2_workstream_busy" in text
    assert "runless_v2_authority_conflict" in text
    assert "merge_authorized" in text


def test_fencing_generation_is_persisted_monotonic_and_stale_writes_fail_closed():
    text = sql()
    assert re.search(r"fencing_generation\s+bigint\s+not\s+null", text)
    assert "fencing_generation + 1" in text or "fencing_generation=runless_v2.workstream_leases.fencing_generation + 1" in text
    assert "runless_v2_stale_fence" in text
    for fn in ("renew_workstream", "advance_proof_state", "record_failure_and_release", "record_merge_authorized_and_release_execution"):
        block = text[text.index(f"function runless_v2.{fn}"):]
        assert "p_fencing_generation" in block[:12000]


def test_state_machine_validation_and_closeout_sequence_are_explicit():
    text = sql()
    assert "runless_v2_illegal_transition" in text
    for state in (
        "identify", "2a_lock", "fingerprint", "reuse_or_prove", "public_check_if_required",
        "receipt", "runless_final_gate", "merge_authorized", "merged", "post_merge_verify",
        "freeze", "read_back", "green_frozen", "failed",
    ):
        assert state in text
    for state in ("merged", "post_merge_verify", "freeze", "read_back", "green_frozen"):
        assert state in text


def test_failed_fingerprint_and_merge_authorized_release_are_atomic_contracts():
    text = sql()
    failure_block = text[text.index("function runless_v2.record_failure_and_release"):]
    assert "failed_fingerprints" in failure_block[:12000]
    assert "delete from runless_v2.workstream_leases" in failure_block[:12000]
    merge_block = text[text.index("function runless_v2.record_merge_authorized_and_release_execution"):]
    assert "receipt_digest" in merge_block[:12000]
    assert "gate_check_run_id" in merge_block[:12000]
    assert "delete from runless_v2.workstream_leases" in merge_block[:12000]


def test_public_roles_cannot_mutate_control_state():
    text = sql()
    assert "revoke all on schema runless_v2 from anon" in text
    assert "revoke all on schema runless_v2 from authenticated" in text
    assert "revoke all on all tables in schema runless_v2 from anon" in text
    assert "revoke all on all tables in schema runless_v2 from authenticated" in text
    assert "revoke all on all functions in schema runless_v2 from anon" in text
    assert "revoke all on all functions in schema runless_v2 from authenticated" in text
    assert "grant usage on schema runless_v2 to service_role" in text


def test_base_drift_supersession_extension_is_separate_and_fail_closed():
    extension = ROOT / "supabase" / "migrations" / "20261017_runless_base_drift_authority_supersession_v1.sql"
    assert extension.exists()
    text = extension.read_text().lower()
    assert "superseded_base_drift" in text
    assert "authority_supersessions" in text
    assert "supersede_base_drift_authority" in text
