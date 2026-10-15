import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "devsystem/contracts/runless-execution-transport-v1.json"
PLAN = ROOT / "devsystem/runless_proof_plans/runless-execution-transport-v1.json"
OPS = ROOT / "docs/runless-execution-transport-v1-operations.md"


def test_transport_contract_locks_existing_authority_and_isolation():
    data = json.loads(CONTRACT.read_text())
    assert data["version"] == "RUNLESS_EXECUTION_TRANSPORT_V1"
    assert data["authority"] == "RUNLESS_V2_EXISTING_POST_PROVE"
    assert data["gate_name"] == "runless-final-gate"
    assert data["github_app_id"] == 5204253
    assert data["github_actions_fallback"] == 0
    assert data["transport_project"] == "kyre-runless-proof"
    assert data["repair_branch"] == "api2-runless-execution-transport-v1"
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


def test_operations_define_one_named_secretless_transport_lane():
    text = OPS.read_text()
    assert "api2-runless-transport" in text
    assert "RUNLESS_PROOF_AUTH_TOKEN" in text
    assert "command-scoped" in text
    assert "durable state first" in text.lower()
    assert "third blind" in text.lower()
    assert "proof authority" in text.lower()


def test_committed_transport_files_contain_no_bearer_literal():
    for path in [CONTRACT, PLAN, OPS, ROOT / "runless_v2/transport_client.py"]:
        text = path.read_text()
        assert "Bearer super-secret" not in text
        assert "RUNLESS_PROOF_AUTH_TOKEN=" not in text
