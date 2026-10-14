import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "devsystem" / "contracts" / "runless-vercel-supabase-v2.json"
PLAN_PATH = ROOT / "devsystem" / "runless_proof_plans" / "runless-vercel-supabase-v2-cutover.json"
RUNBOOK_PATH = ROOT / "docs" / "runless-proof-plane-v2-operations.md"

WORKSTREAM = "runless-vercel-supabase-v2"
FREEZE_TOKEN = "RUNLESS_VERCEL_SUPABASE_V2_CUTOVER_FROZEN"


def load(path):
    assert path.exists(), f"missing required artifact: {path}"
    return json.loads(path.read_text())


def test_contract_locks_v2_authority_and_zero_legacy_fallbacks():
    contract = load(CONTRACT_PATH)
    assert contract["version"] == "RUNLESS_VERCEL_SUPABASE_V2_CUTOVER_V1"
    assert contract["workstream"] == WORKSTREAM
    assert contract["freeze_token"] == FREEZE_TOKEN
    assert contract["render_dependency"] is False
    assert contract["github_actions_fallback"] == 0
    assert contract["initial_authority_enabled"] is False
    assert contract["render_v1_after_cutover"] == "LEGACY_NON_AUTHORITATIVE"
    assert contract["new_render_v1_proof_requests"] is False
    assert contract["github_app_id"] == 5204253
    assert contract["gate_name"] == "runless-final-gate"
    assert contract["authority_components"] == [
        "SUPABASE_DURABLE_PROOF_IDENTITY",
        "GITHUB_IMMUTABLE_RECEIPT",
        "GITHUB_APP_5204253_RUNLESS_FINAL_GATE",
        "GITHUB_FINALIZATION_LEDGER_V2",
    ]


def test_certification_matrix_is_complete_and_activation_requires_every_item_green():
    contract = load(CONTRACT_PATH)
    expected = {
        "cold_start_status_recovery",
        "simultaneous_claim_single_winner",
        "expired_lease_takeover_increments_generation",
        "stale_fence_rejected",
        "same_proof_idempotency",
        "different_candidate_outstanding_authority_rejection",
        "deterministic_failure_anti_loop",
        "exact_candidate_checkout",
        "sandbox_cleanup",
        "api_auth_failure_before_mutation",
        "zero_production_gate_while_authority_disabled",
    }
    matrix = contract["certification_matrix"]
    assert set(matrix) == expected
    assert all(value == "REQUIRED_GREEN" for value in matrix.values())
    assert contract["activation_rule"] == "ALL_CERTIFICATION_MATRIX_ITEMS_GREEN"


def test_cutover_proof_plan_is_runless_only_and_self_certifies_contract():
    plan = load(PLAN_PATH)
    assert plan["task_id"] == "runless-vercel-supabase-v2-cutover"
    assert plan["workstream"] == WORKSTREAM
    assert plan["freeze_token"] == FREEZE_TOKEN
    assert plan["github_actions_fallback"] == 0
    assert plan["render_dependency"] is False
    assert CONTRACT_PATH.relative_to(ROOT).as_posix() in plan["artifacts"]
    assert RUNBOOK_PATH.relative_to(ROOT).as_posix() in plan["artifacts"]
    assert "runless_v2/app.py" in plan["artifacts"]
    assert "runless_v2/proof_service.py" in plan["artifacts"]
    assert "supabase/migrations/20261013_runless_v2_durable_state.sql" in plan["artifacts"]
    commands = plan["commands"]
    assert commands
    assert all(command[:3] == ["python", "-m", "pytest"] or command[:2] == ["python", "-m"] for command in commands)
    assert not plan.get("probes")


def test_operations_runbook_hard_codes_safe_cutover_sequence():
    assert RUNBOOK_PATH.exists()
    text = RUNBOOK_PATH.read_text()
    for required in (
        "RUNLESS_AUTHORITY_ENABLED=0",
        "LEGACY_NON_AUTHORITATIVE",
        "GitHub Actions fallback remains 0",
        "no new proof request is sent to Render V1",
        "Vercel Sandbox",
        "Supabase",
        "App 5204253",
        "GREEN + FROZEN",
        "cold start",
        "fencing generation",
        "same proof",
        "different candidate",
        "stale fence",
    ):
        assert required.lower() in text.lower()
