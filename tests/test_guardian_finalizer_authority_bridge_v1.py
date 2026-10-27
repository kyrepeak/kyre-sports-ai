from pathlib import Path

import runless_v2.guardian_finalizer_authority_bridge_proof_v1 as proof

ROOT = Path(__file__).resolve().parents[1]


def test_guardian_finalizer_authority_bridge_identity_is_locked():
    assert proof.TASK_ID == "guardian-finalizer-authority-bridge-v1"
    assert proof.WORKSTREAM == proof.TASK_ID
    assert proof.PR_NUMBER == 1904
    assert proof.BRANCH == "guardian-finalizer-authority-bridge-v1"
    assert proof.EXPECTED_MAIN_SHA == "e4e42fb0338c55c16fc4aa5fd08aeb181e142e03"


def test_capability_edge_source_is_narrow_and_never_contains_plaintext_secret():
    source = (ROOT / "supabase/functions/guardian-finalizer-authority-bridge-v1/index.ts").read_text()
    assert "EXPECTED_CAPABILITY_SHA256" in source
    assert "x-finalizer-capability" in source
    assert "FINALIZER_CAPABILITY_INVALID" in source
    assert "claim_final_gate_publication" in source
    assert "complete_final_gate_publication" in source
    assert "Deno.serve" in source
    assert "SfKZb9x" not in source
    assert "service_role" not in source.lower().replace("supabase_service_role_key", "")


def test_finalizer_custom_entrypoint_is_bridge_only():
    pyproject = (ROOT / "vercel_finalizer/pyproject.toml").read_text()
    entrypoint = (ROOT / "vercel_finalizer/bridge_entrypoint.py").read_text()
    runtime = (ROOT / "vercel_finalizer/bridge_runtime.py").read_text()
    assert 'entrypoint = "bridge_entrypoint:app"' in pyproject
    assert "install_bridge(_base.__dict__)" in entrypoint
    assert "FINALIZER_CAPABILITY_TOKEN" in runtime
    assert '"capability_edge"' in runtime
