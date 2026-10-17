from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261017_runless_base_drift_supersession_transport_v1.sql"
OPS = ROOT / "docs/runless-base-drift-authority-supersession-v1-operations.md"


def sql() -> str:
    assert MIGRATION.exists(), "base-drift transport migration must exist"
    return MIGRATION.read_text(encoding="utf-8")


def test_transport_is_server_side_secret_safe_and_service_role_only():
    text = sql()
    lower = text.lower()
    assert "runless_v2.request_base_drift_supersession_transport" in text
    assert "vault.decrypted_secrets" in text
    assert "runless_v2_transport_bearer" in text
    assert "runless_v2_vercel_protection_bypass" in text
    assert "extensions.http" in text
    assert "Authorization" in text
    assert "x-vercel-protection-bypass" in text
    assert "revoke all on function" in lower
    assert "grant execute" in lower
    assert "to service_role" in lower
    assert "RUNLESS_PROOF_AUTH_TOKEN=" not in text


def test_transport_validates_repository_shas_identity_pr_branch_and_vercel_origin():
    text = sql()
    for marker in (
        "RUNLESS_SUPERSESSION_TRANSPORT_REPOSITORY_REJECTED",
        "RUNLESS_SUPERSESSION_TRANSPORT_OLD_SHA_INVALID",
        "RUNLESS_SUPERSESSION_TRANSPORT_SUCCESSOR_SHA_INVALID",
        "RUNLESS_SUPERSESSION_TRANSPORT_EXPECTED_MAIN_SHA_INVALID",
        "RUNLESS_SUPERSESSION_TRANSPORT_IDENTITY_REQUIRED",
        "RUNLESS_SUPERSESSION_TRANSPORT_PR_INVALID",
        "RUNLESS_SUPERSESSION_TRANSPORT_BASE_URL_REJECTED",
    ):
        assert marker in text
    assert "kyre-runless-proof" in text
    assert "/supersede-base-drift" in text


def test_transport_serializes_one_identity_and_reuses_only_exact_durable_supersession():
    text = sql()
    assert "pg_advisory_xact_lock" in text
    assert "runless_v2.authority_supersessions" in text
    assert "old_proof_id = p_old_proof_id" in text
    assert "RUNLESS_SUPERSESSION_TRANSPORT_IDENTITY_COLLISION" in text
    assert "'reused', true" in text
    assert "'reused', false" in text


def test_transport_sanitizes_remote_error_and_reads_durable_authority_not_http_claims():
    text = sql()
    assert "RUNLESS_SUPERSESSION_TRANSPORT_HTTP_ERROR" in text
    assert "RUNLESS_SUPERSESSION_TRANSPORT_BAD_JSON" in text
    assert "RUNLESS_SUPERSESSION_TRANSPORT_RESPONSE_IDENTITY_REQUIRED" in text
    assert "select * into strict v_existing" in text.lower()
    assert "from runless_v2.authority_supersessions" in text
    assert "v_payload->>'supersession_id'" in text


def test_operations_document_connected_transport_and_no_parallel_successor_proof():
    text = OPS.read_text(encoding="utf-8")
    lower = text.lower()
    assert "request_base_drift_supersession_transport" in text
    assert "supabase vault" in lower
    assert "connected" in lower
    assert "fresh exact-head proof" in lower
    assert "parallel" in lower
    assert "github actions fallback" in lower
    assert "0" in text
