from __future__ import annotations

import hashlib
import json
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.frozen_artifact_registry_v1 import (
    REGISTRY_PATH,
    REGISTRY_REF,
    VERSION as REGISTRY_VERSION,
)
from devsystem.pre_mutation_blast_radius_simulator_v1 import (
    PreMutationBlastRadiusFailure,
    compile_required_scope,
    contract_self_test,
    simulate_mutation,
)
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    new_state as new_lease_state,
)
from devsystem.shared_resource_lease_sharding_v1 import shard_resource


HEAD = "a" * 40
NOW = "2026-10-02T03:00:00Z"


def _hash(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def _registry(path="frozen_guard.py"):
    state = {
        "schema_version": 1,
        "version": REGISTRY_VERSION,
        "repository": "owner/repo",
        "registry_ref": REGISTRY_REF,
        "registry_path": REGISTRY_PATH,
        "revision": 1,
        "source_main_sha": HEAD,
        "entries": {
            "TEST": {
                "status": "FROZEN",
                "checkpoint_id": "TEST",
                "source_main_sha": HEAD,
                "artifacts": {path: "f" * 40},
            }
        },
        "active_thaws": [],
    }
    state["state_hash"] = _hash(state)
    return state


@pytest.fixture()
def project():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "leaf.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "feature.py").write_text("import leaf\n", encoding="utf-8")
        (root / "app.py").write_text("import feature\n", encoding="utf-8")
        (root / "frozen_guard.py").write_text("VALUE = 1\n", encoding="utf-8")
        yield root


def _surfaces():
    workflows = [
        {
            "name": "unit",
            "trigger_paths": ["leaf.py", "feature.py"],
            "shared_resource": "workflow:unit",
        }
    ]
    deployments = [
        {
            "name": "app",
            "trigger_paths": ["app.py"],
            "shared_resource": "deploy:app",
        }
    ]
    return workflows, deployments


def _compiled(root, workflows=None, deployments=None):
    workflows, deployments = (
        (workflows, deployments)
        if workflows is not None
        else _surfaces()
    )
    return compile_required_scope(
        ["leaf.py"],
        root=root,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
        workflow_surfaces=workflows,
        deployment_surfaces=deployments,
    )


def _declared(compiled, **changes):
    req = compiled["required_scope"]
    payload = build_scope(
        write_paths=req["write_paths"],
        dependency_tokens=req["dependency_tokens"],
        shared_resources=req["shared_resources"],
        resource_identity={"main:base": HEAD},
    )
    payload.update(changes)
    return payload


def _simulate(root, *, declared=None, registry=None, lease=None, owner="chat:monster", observed=HEAD, workflows=None, deployments=None):
    workflows, deployments = (
        (workflows, deployments)
        if workflows is not None
        else _surfaces()
    )
    compiled = compile_required_scope(
        ["leaf.py"],
        root=root,
        expected_head_sha=HEAD,
        observed_head_sha=observed,
        workflow_surfaces=workflows,
        deployment_surfaces=deployments,
    )
    return simulate_mutation(
        ["leaf.py"],
        root=root,
        expected_head_sha=HEAD,
        observed_head_sha=observed,
        owner_id=owner,
        now_utc=NOW,
        declared_scope=declared or _declared(compiled),
        frozen_registry=registry or _registry(),
        lease_state=lease or new_lease_state("owner/repo"),
        workflow_surfaces=workflows,
        deployment_surfaces=deployments,
    )


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["safe_change_allowed_to_gate"] is True
    assert result["transitive_frozen_reach_blocked"] is True


def test_safe_change_only_requests_existing_mutation_gate(project):
    result = _simulate(project)
    assert result["status"] == "GREEN"
    assert result["decision"] == "SAFE_TO_REQUEST_MUTATION_GATE"
    assert result["next_legal_action"] == "REQUEST_STEP_2A_MUTATION_GATE"
    assert result["mutation_authority"] is False


def test_stale_head_fails_closed(project):
    result = _simulate(project, observed="b" * 40)
    assert result["decision"] == "PRE_MUTATION_BLOCKED"
    assert any(row["code"] == "STALE_HEAD" for row in result["blockers"])
    assert result["next_legal_action"] == "REFRESH_HEAD_AND_REPLAN"


def test_direct_frozen_write_is_blocked(project):
    compiled = compile_required_scope(
        ["frozen_guard.py"],
        root=project,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    declared = _declared(compiled)
    result = simulate_mutation(
        ["frozen_guard.py"],
        root=project,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
        owner_id="chat:monster",
        now_utc=NOW,
        declared_scope=declared,
        frozen_registry=_registry("frozen_guard.py"),
        lease_state=new_lease_state("owner/repo"),
    )
    assert any(row["code"] == "DIRECT_FROZEN_ARTIFACT" for row in result["blockers"])
    assert result["direct_frozen_artifacts"] == ["frozen_guard.py"]


def test_transitive_frozen_dependent_is_blocked(project):
    result = _simulate(project, registry=_registry("app.py"))
    assert result["transitive_frozen_reach"] == ["app.py"]
    assert any(row["code"] == "TRANSITIVE_FROZEN_REACH" for row in result["blockers"])


def test_undeclared_write_path_is_blocked(project):
    compiled = _compiled(project)
    declared = build_scope(
        write_paths=["other.py"],
        dependency_tokens=compiled["required_scope"]["dependency_tokens"],
        shared_resources=compiled["required_scope"]["shared_resources"],
        resource_identity={"main:base": HEAD},
    )
    result = _simulate(project, declared=declared)
    assert any(row["code"] == "UNDECLARED_WRITE_PATH" for row in result["blockers"])


def test_missing_dependency_token_is_blocked(project):
    compiled = _compiled(project)
    req = compiled["required_scope"]
    declared = build_scope(
        write_paths=req["write_paths"],
        dependency_tokens=req["dependency_tokens"][1:],
        shared_resources=req["shared_resources"],
        resource_identity={"main:base": HEAD},
    )
    result = _simulate(project, declared=declared)
    assert any(row["code"] == "UNDECLARED_DEPENDENCY_TOKEN" for row in result["blockers"])


def test_missing_workflow_resource_is_blocked(project):
    compiled = _compiled(project)
    req = compiled["required_scope"]
    declared = build_scope(
        write_paths=req["write_paths"],
        dependency_tokens=req["dependency_tokens"],
        shared_resources=[
            item for item in req["shared_resources"] if item != "workflow:unit"
        ],
        resource_identity={"main:base": HEAD},
    )
    result = _simulate(project, declared=declared)
    blocker = next(row for row in result["blockers"] if row["code"] == "UNDECLARED_SHARED_RESOURCE")
    assert "workflow:unit" in blocker["resources"]


def test_transitive_deployment_surface_is_detected(project):
    result = _simulate(project)
    assert [row["name"] for row in result["deployment_impacts"]] == ["app"]
    assert result["deployment_impacts"][0]["matched_paths"] == ["app.py"]


def test_missing_deployment_resource_is_blocked(project):
    compiled = _compiled(project)
    req = compiled["required_scope"]
    declared = build_scope(
        write_paths=req["write_paths"],
        dependency_tokens=req["dependency_tokens"],
        shared_resources=[
            item for item in req["shared_resources"] if item != "deploy:app"
        ],
        resource_identity={"main:base": HEAD},
    )
    result = _simulate(project, declared=declared)
    blocker = next(row for row in result["blockers"] if row["code"] == "UNDECLARED_SHARED_RESOURCE")
    assert "deploy:app" in blocker["resources"]


def test_declared_main_base_identity_is_mandatory(project):
    compiled = _compiled(project)
    req = compiled["required_scope"]
    declared = build_scope(
        write_paths=req["write_paths"],
        dependency_tokens=req["dependency_tokens"],
        shared_resources=req["shared_resources"],
        resource_identity={"main:base": "b" * 40},
    )
    result = _simulate(project, declared=declared)
    assert any(row["code"] == "BASE_IDENTITY_MISMATCH" for row in result["blockers"])


def test_live_conflicting_holder_blocks(project):
    compiled = _compiled(project)
    declared = _declared(compiled)
    state = new_lease_state("owner/repo")
    claimed = claim_scope(
        state,
        owner_id="other-chat",
        now_utc=NOW,
        scope=declared,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=1800,
    )
    result = _simulate(project, declared=declared, lease=claimed["state"])
    assert any(row["code"] == "LIVE_WORKSTREAM_CONFLICT" for row in result["blockers"])
    assert result["live_workstream_conflicts"][0]["owner_id"] == "other-chat"


def test_same_owner_holder_is_not_self_conflict(project):
    compiled = _compiled(project)
    declared = _declared(compiled)
    state = new_lease_state("owner/repo")
    claimed = claim_scope(
        state,
        owner_id="chat:monster",
        now_utc=NOW,
        scope=declared,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=1800,
    )
    result = _simulate(project, declared=declared, lease=claimed["state"])
    assert result["live_workstream_conflicts"] == []


def test_expired_holder_does_not_block(project):
    compiled = _compiled(project)
    declared = _declared(compiled)
    state = new_lease_state("owner/repo")
    claimed = claim_scope(
        state,
        owner_id="other-chat",
        now_utc="2026-10-02T02:00:00Z",
        scope=declared,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=60,
    )
    result = _simulate(project, declared=declared, lease=claimed["state"])
    assert result["live_workstream_conflicts"] == []


def test_disjoint_shards_do_not_conflict(project):
    workflows = [
        {
            "name": "cfb-ci",
            "trigger_paths": ["leaf.py"],
            "shared_resource": shard_resource(
                "workflow:shared-ci", {"domain": "cfb"}
            ),
        }
    ]
    deployments = []
    compiled = _compiled(project, workflows, deployments)
    declared = _declared(compiled)
    state = new_lease_state("owner/repo")
    other_scope = build_scope(
        write_paths=["wnba.py"],
        shared_resources=[
            shard_resource("workflow:shared-ci", {"domain": "wnba"})
        ],
    )
    claimed = claim_scope(
        state,
        owner_id="wnba-chat",
        now_utc=NOW,
        scope=other_scope,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
        ttl_seconds=1800,
    )
    result = _simulate(
        project,
        declared=declared,
        lease=claimed["state"],
        workflows=workflows,
        deployments=deployments,
    )
    assert result["decision"] == "SAFE_TO_REQUEST_MUTATION_GATE"
    assert result["live_workstream_conflicts"] == []


def test_global_parent_holder_blocks_child_shard(project):
    workflows = [
        {
            "name": "cfb-ci",
            "trigger_paths": ["leaf.py"],
            "shared_resource": shard_resource(
                "workflow:shared-ci", {"domain": "cfb"}
            ),
        }
    ]
    compiled = _compiled(project, workflows, [])
    declared = _declared(compiled)
    state = new_lease_state("owner/repo")
    global_scope = build_scope(
        write_paths=["global.py"],
        shared_resources=["workflow:shared-ci"],
    )
    claimed = claim_scope(
        state,
        owner_id="global-chat",
        now_utc=NOW,
        scope=global_scope,
        expected_revision=0,
        expected_state_hash=state["state_hash"],
        ttl_seconds=1800,
    )
    result = _simulate(
        project,
        declared=declared,
        lease=claimed["state"],
        workflows=workflows,
        deployments=[],
    )
    assert any(row["code"] == "LIVE_WORKSTREAM_CONFLICT" for row in result["blockers"])


def test_unknown_target_fails_safe(project):
    compiled = compile_required_scope(
        ["mystery.bin"],
        root=project,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
    )
    declared = _declared(compiled)
    result = simulate_mutation(
        ["mystery.bin"],
        root=project,
        expected_head_sha=HEAD,
        observed_head_sha=HEAD,
        owner_id="chat:monster",
        now_utc=NOW,
        declared_scope=declared,
        frozen_registry=_registry(),
        lease_state=new_lease_state("owner/repo"),
    )
    assert result["decision"] == "PRE_MUTATION_BLOCKED"
    assert any(row["code"] == "LEGACY_BLAST_BLOCKED" for row in result["blockers"])


def test_receipt_changes_when_declared_scope_changes(project):
    first = _simulate(project)
    compiled = _compiled(project)
    req = compiled["required_scope"]
    broader = build_scope(
        write_paths=[*req["write_paths"], "extra.py"],
        dependency_tokens=req["dependency_tokens"],
        shared_resources=req["shared_resources"],
        resource_identity={"main:base": HEAD},
    )
    second = _simulate(project, declared=broader)
    assert first["simulation_receipt_digest"] != second["simulation_receipt_digest"]


def test_tampered_registry_is_rejected(project):
    registry = _registry()
    registry["revision"] = 99
    with pytest.raises(Exception):
        _simulate(project, registry=registry)


def test_invalid_surface_fails_closed(project):
    with pytest.raises(
        PreMutationBlastRadiusFailure,
        match="requires name/shared_resource/trigger_paths",
    ):
        compile_required_scope(
            ["leaf.py"],
            root=project,
            expected_head_sha=HEAD,
            observed_head_sha=HEAD,
            workflow_surfaces=[{"name": "broken"}],
        )


def test_simulator_is_read_only_and_step2a_remains_authority(project):
    result = _simulate(project)
    assert result["step_2a_required"] is True
    assert result["mutation_authority"] is False
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
