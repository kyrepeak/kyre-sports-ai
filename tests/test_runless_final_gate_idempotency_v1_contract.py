from pathlib import Path


def test_final_gate_claim_contract_is_durable_and_single_authority():
    text = Path("supabase/migrations/20261015_runless_final_gate_idempotency_v1.sql").read_text()
    lowered = text.lower()
    assert "alter table runless_v2.proof_runs" in lowered
    assert "gate_publication_claim_token" in lowered
    assert "gate_publication_claimed_at" in lowered
    assert "claim_final_gate_publication" in lowered
    assert "complete_final_gate_publication" in lowered
    assert "release_final_gate_publication" in lowered
    assert "for update" in lowered
    assert "gate_check_run_id" in lowered
    assert "create table" not in lowered
