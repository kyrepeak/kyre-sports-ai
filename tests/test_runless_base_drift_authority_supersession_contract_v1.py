import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "devsystem/runless_proof_plans/runless-base-drift-authority-supersession-v1.json"
SPEC = ROOT / "docs/superpowers/specs/2026-10-17-runless-base-drift-authority-supersession-v1-design.md"
OPS = ROOT / "docs/runless-base-drift-authority-supersession-v1-operations.md"

REQUIRED_ARTIFACTS = {
    "runless_v2/models.py",
    "runless_v2/state_store.py",
    "runless_v2/github_authority.py",
    "runless_v2/app.py",
    "vercel_finalizer/authority.py",
    "supabase/migrations/20261017_runless_base_drift_authority_supersession_v1.sql",
    "supabase/migrations/20261017_runless_base_drift_supersession_transport_v1.sql",
    "docs/runless-base-drift-authority-supersession-v1-operations.md",
    "tests/test_runless_base_drift_authority_supersession_schema_v1.py",
    "tests/test_runless_v2_base_drift_supersession_v1.py",
    "tests/test_runless_base_drift_supersession_transport_v1.py",
    "tests/test_runless_base_drift_authority_supersession_contract_v1.py",
}


def plan():
    assert PLAN.exists(), "focused Runless proof plan must exist"
    return json.loads(PLAN.read_text(encoding="utf-8"))


def test_proof_plan_locks_exact_workstream_gate_and_zero_actions_fallback():
    data = plan()
    assert data["task_id"] == "runless-base-drift-authority-supersession-v1"
    assert data["workstream"] == "runless-base-drift-authority-supersession-v1"
    assert data["freeze_token"] == "RUNLESS_BASE_DRIFT_AUTHORITY_SUPERSESSION_V1_FROZEN"
    assert data["required_check"] == "runless-final-gate"
    assert data["github_app_id"] == 5204253
    assert data["github_actions_fallback"] == 0
    assert len(data["source_main_sha"]) == 40
    assert data["probes"] == []


def test_proof_plan_contains_only_control_plane_artifacts_and_required_migrations():
    data = plan()
    artifacts = set(data["artifacts"])
    assert REQUIRED_ARTIFACTS <= artifacts
    assert not any(path.startswith(("streamlit_", "nfl_", "cfb_", "nba_", "wnba_", "mlb_")) for path in artifacts)


def test_proof_plan_runs_full_focused_regression_and_compile_contract():
    data = plan()
    commands = [" ".join(command) for command in data["commands"]]
    joined = "\n".join(commands)
    for required in (
        "test_runless_base_drift_authority_supersession_schema_v1.py",
        "test_runless_v2_base_drift_supersession_v1.py",
        "test_runless_base_drift_supersession_transport_v1.py",
        "test_runless_base_drift_authority_supersession_contract_v1.py",
        "test_runless_v2_state_store.py",
        "test_runless_v2_github_authority.py",
        "test_runless_v2_schema_contract.py",
        "test_runless_v2_proof_service.py",
        "test_runless_v2_finalization_readback.py",
        "vercel_finalizer/test_authority.py",
        "vercel_finalizer/test_dynamic_authority.py",
        "vercel_finalizer/test_app.py",
    ):
        assert required in joined
    assert "py_compile" in joined
    for module in (
        "runless_v2/models.py",
        "runless_v2/state_store.py",
        "runless_v2/github_authority.py",
        "runless_v2/app.py",
        "vercel_finalizer/authority.py",
    ):
        assert module in joined


def test_operations_and_design_preserve_old_evidence_and_require_fresh_successor_proof():
    text = (SPEC.read_text(encoding="utf-8") + "\n" + OPS.read_text(encoding="utf-8")).lower()
    assert "superseded_base_drift" in text
    assert "old_receipt_digest" in text
    assert "old_gate_check_run_id" in text
    assert "fresh exact-head proof" in text
    assert "parallel" in text
