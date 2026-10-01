from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    contract_self_test,
    new_state,
    release_scope,
    scope_from_blast_radius,
    verify_scope_identity,
)


def test_disjoint_scopes_can_hold_leases_concurrently():
    state=new_state("owner/repo")
    a=claim_scope(state,owner_id="a",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["app.py"],dependency_tokens=["wnba"]),expected_revision=0,expected_state_hash=state["state_hash"])
    b=claim_scope(a["state"],owner_id="b",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["devsystem/v5.py"],dependency_tokens=["devsystem"]),expected_revision=a["state"]["revision"],expected_state_hash=a["state"]["state_hash"])
    assert b["result"]["allowed"] is True
    assert b["result"]["parallel_holder_count"] == 2


def test_overlap_and_frozen_scope_fail_closed():
    state=new_state("owner/repo")
    a=claim_scope(state,owner_id="a",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["sports_api"]),expected_revision=0,expected_state_hash=state["state_hash"])
    b=claim_scope(a["state"],owner_id="b",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["sports_api/api/x.py"]),expected_revision=a["state"]["revision"],expected_state_hash=a["state"]["state_hash"])
    assert b["result"]["allowed"] is False
    frozen=claim_scope(state,owner_id="f",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["devsystem/frozen.py"]),expected_revision=0,expected_state_hash=state["state_hash"],frozen_paths=["devsystem/frozen.py"])
    assert frozen["result"]["decision"] == "SCOPE_FROZEN_ARTIFACT_BLOCKED"


def test_dependency_and_shared_resource_overlap_serialize():
    state=new_state("owner/repo")
    a=claim_scope(state,owner_id="a",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["a.py"],dependency_tokens=["provider:shared"],shared_resources=["workflow:deploy"]),expected_revision=0,expected_state_hash=state["state_hash"])
    dep=claim_scope(a["state"],owner_id="b",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["b.py"],dependency_tokens=["provider:shared"]),expected_revision=a["state"]["revision"],expected_state_hash=a["state"]["state_hash"])
    shared=claim_scope(a["state"],owner_id="c",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["c.py"],shared_resources=["workflow:deploy"]),expected_revision=a["state"]["revision"],expected_state_hash=a["state"]["state_hash"])
    assert dep["result"]["allowed"] is False
    assert shared["result"]["allowed"] is False


def test_scope_identity_ignores_unrelated_main_but_blocks_scoped_drift():
    scope=build_scope(write_paths=["x.py"],resource_identity={"blob:x.py":"abc"})
    assert verify_scope_identity(scope,observed_resource_identity={"blob:x.py":"abc","main":"new"})["allowed"] is True
    assert verify_scope_identity(scope,observed_resource_identity={"blob:x.py":"def"})["allowed"] is False


def test_release_does_not_drop_other_parallel_holder():
    state=new_state("owner/repo")
    a=claim_scope(state,owner_id="a",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["a.py"]),expected_revision=0,expected_state_hash=state["state_hash"])
    b=claim_scope(a["state"],owner_id="b",now_utc="2026-10-01T00:00:00Z",scope=build_scope(write_paths=["b.py"]),expected_revision=a["state"]["revision"],expected_state_hash=a["state"]["state_hash"])
    holder=next(h for h in b["state"]["holders"] if h["owner_id"]=="b")
    released=release_scope(b["state"],owner_id="b",lease_id=holder["lease_id"],expected_revision=b["state"]["revision"],expected_state_hash=b["state"]["state_hash"])
    assert [h["owner_id"] for h in released["state"]["holders"]] == ["a"]


def test_blast_radius_output_becomes_scope_tokens():
    scope=scope_from_blast_radius({
        "direct_dependencies":["a"],"direct_dependents":["b"],
        "transitive_dependencies":["c"],"transitive_dependents":["d"],
        "impacted_entrypoints":["app.py"],"protected_reach":["frozen.py"],
    },write_paths=["feature.py"])
    assert "direct_dependencies:a" in scope["dependency_tokens"]
    assert "entrypoint:app.py" in scope["shared_resources"]


def test_contract_self_test_green_and_runtime_safe():
    result=contract_self_test()
    assert result["status"] == "GREEN"
    assert result["disjoint_parallel_allowed"] is True
    assert result["same_path_overlap_blocked"] is True
    assert result["dependency_overlap_blocked"] is True
    assert result["shared_resource_overlap_blocked"] is True
    assert result["exclusive_scope_blocks_parallel"] is True
    assert result["frozen_path_blocked"] is True
    assert result["stale_cas_blocked"] is True
    assert result["action_within_scope_authorized"] is True
    assert result["action_outside_scope_blocked"] is True
    assert result["unrelated_main_movement_tolerated"] is True
    assert result["scoped_identity_drift_blocked"] is True
    assert result["release_is_holder_local"] is True
    assert result["blast_radius_tokens_reused"] is True
    assert result["step_2a_chain_preserved"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_green():
    root=Path(__file__).resolve().parents[1]
    completed=subprocess.run([sys.executable,str(root/"devsystem"/"scope_aware_execution_lease_v1.py")],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_GREEN" in completed.stdout
