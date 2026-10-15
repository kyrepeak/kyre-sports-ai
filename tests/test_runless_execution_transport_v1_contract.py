import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "devsystem/contracts/runless-execution-transport-v1.json"
PLAN = ROOT / "devsystem/runless_proof_plans/runless-execution-transport-v1.json"
OPS = ROOT / "docs/runless-execution-transport-v1-operations.md"
MIGRATION = ROOT / "supabase/migrations/20261015_runless_execution_transport_v1.sql"


def test_transport_contract_locks_existing_authority_and_isolation():
    data = json.loads(CONTRACT.read_text())
    assert data["version"] == "RUNLESS_EXECUTION_TRANSPORT_V1"
    assert data["authority"] == "RUNLESS_V2_EXISTING_POST_PROVE"
    assert data["gate_name"] == "runless-final-gate"
    assert data["github_app_id"] == 5204253
    assert data["github_actions_fallback"] == 0
    assert data["transport_project"] == "kyre-runless-proof"
    assert data["repair_branch"] == "api2-runless-execution-transport-v1"
    assert data["connected_transport"] == "SUPABASE_SECURITY_DEFINER_HTTP_TO_EXISTING_POST_PROVE"
    assert data["transport_secret_store"] == "SUPABASE_VAULT"
    forbidden = set(data["forbidden_mutation_scopes"])
    assert {"pull/1541", "pull/1544", "sports-runtime", "sports-model", "sports-page"} <= forbidden


def test_proof_plan_is_focused_and_has_no_public_sports_probe():
    plan = json.loads(PLAN.read_text())
    assert plan["task_id"] == "runless-execution-transport-v1"
    assert plan["workstream"] == "runless-execution-transport-v1"
    assert plan["probes"] == []
    commands = [" ".join(command) for command in plan["commands"]]
    assert any("test_runless_v2_transport_client.py" in command for command in commands)
    assert any("test_runless_v2_proof_service.py" in command for command in commands)
    assert any("test_runless_execution_transport_v1_contract.py" in command for command in commands)
    assert any("py_compile" in command for command in commands)
    assert "supabase/migrations/20261015_runless_execution_transport_v1.sql" in plan["artifacts"]


def test_operations_define_one_named_secretless_transport_lane():
    text = OPS.read_text()
    assert "api2-runless-transport" in text
    assert "RUNLESS_PROOF_AUTH_TOKEN" in text
    assert "command-scoped" in text
    assert "durable state first" in text.lower()
    assert "third blind" in text.lower()
    assert "proof authority" in text.lower()


def test_committed_transport_files_contain_no_bearer_literal():
    for path in [CONTRACT, PLAN, OPS, ROOT / "runless_v2/transport_client.py", MIGRATION]:
        text = path.read_text()
        assert "Bearer super-secret" not in text
        assert "RUNLESS_PROOF_AUTH_TOKEN=" not in text


def test_server_side_transport_migration_is_secret_safe_and_idempotent():
    text = MIGRATION.read_text()
    assert "runless_v2.request_proof_transport" in text
    assert "vault.decrypted_secrets" in text
    assert "runless_v2_transport_bearer" in text
    assert "pg_advisory_xact_lock" in text
    assert "runless_v2.proof_runs" in text
    assert "extensions.http" in text
    assert "Authorization" in text
    assert "kyre-runless-proof" in text
    assert "revoke all on function" in text.lower()
    assert "grant execute" in text.lower()
    assert "RUNLESS_PROOF_AUTH_TOKEN=" not in text
    assert "Bearer super-secret" not in text
