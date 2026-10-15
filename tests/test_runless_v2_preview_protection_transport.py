from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261015_runless_execution_transport_v1.sql"


def test_server_transport_bypasses_vercel_preview_protection_without_leaking_secret():
    text = MIGRATION.read_text()
    assert "runless_v2_vercel_protection_bypass" in text
    assert "x-vercel-protection-bypass" in text
    assert "vault.decrypted_secrets" in text
    assert "Authorization" in text
    assert "RUNLESS_PROOF_AUTH_TOKEN=" not in text
    assert "Bearer super-secret" not in text
