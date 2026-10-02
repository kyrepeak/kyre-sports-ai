"""MONSTER V8 Step 1 — Pre-Mutation Blast-Radius Simulator V1.

This layer upgrades the frozen V3 blast-radius map from "what can this path
reach?" to "is this exact mutation safe to attempt against current repository
truth?"

It reconciles:
- exact base/head identity;
- V3 transitive dependency and entrypoint blast;
- authoritative frozen artifact registry;
- declared write/dependency/shared-resource scope;
- live non-expired workstream leases using V7 shard semantics;
- declared workflow and deployment impact surfaces.

A GREEN simulation grants no mutation authority. It only permits the caller to
request the existing Step-2A mutation gate.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.frozen_artifact_registry_v1 import (
    REGISTRY_PATH,
    REGISTRY_REF,
    VERSION as FROZEN_REGISTRY_VERSION,
    validate_registry,
)
from devsystem.project_blast_radius_map_v1 import (
    VERSION as BLAST_MAP_VERSION,
    plan_change,
)
from devsystem.scope_aware_execution_lease_v1 import (
    VERSION as SCOPE_LEASE_VERSION,
    build_scope,
    scope_from_blast_radius,
    validate_state as validate_lease_state,
)
from devsystem.shared_resource_lease_sharding_v1 import (
    VERSION as SHARDING_VERSION,
    parse_resource,
    shard_aware_scopes_conflict,
)
from sports_api.monster_dependency_map_v1 import build_dependency_map

VERSION = "MONSTER_V8_PRE_MUTATION_BLAST_RADIUS_SIMULATOR_V1"

REQUIRED_BLAST_MAP_VERSION = "MONSTER_PROJECT_BLAST_RADIUS_MAP_V1"
REQUIRED_FROZEN_REGISTRY_VERSION = "MONSTER_V4_FROZEN_ARTIFACT_REGISTRY_V1"
REQUIRED_SCOPE_LEASE_VERSION = "MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_V1"
REQUIRED_SHARDING_VERSION = "MONSTER_V7_SHARED_RESOURCE_LEASE_SHARDING_V1"

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class PreMutationBlastRadiusFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _norm_path(value: Any) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or path.startswith("/") or ".." in Path(path).parts:
        raise PreMutationBlastRadiusFailure("invalid repository-relative path")
    return path


def _sha(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not _SHA40.fullmatch(out):
        raise PreMutationBlastRadiusFailure(f"{field} must be a full git SHA")
    return out


def _utc(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PreMutationBlastRadiusFailure("invalid UTC timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _path_covered(path: str, declared_paths: Sequence[str]) -> bool:
    target = _norm_path(path)
    for raw in declared_paths:
        declared = _norm_path(raw)
        if target == declared:
            return True
        prefix = declared.rstrip("/") + "/"
        if target.startswith(prefix):
            return True
    return False


def _resource_covers(required: str, declared: str) -> bool:
    if required == declared:
        return True
    try:
        req = parse_resource(required)
        dec = parse_resource(declared)
    except Exception:
        return False
    if req["parent"] != dec["parent"]:
        return False
    if not dec["is_sharded"]:
        return True
    if not req["is_sharded"]:
        return False
    req_dims = req["dimensions"]
    dec_dims = dec["dimensions"]
    return all(dec_dims.get(key) == value for key, value in req_dims.items())


def _missing_resources(
    required: Sequence[str],
    declared: Sequence[str],
) -> list[str]:
    return sorted(
        resource
        for resource in required
        if not any(_resource_covers(resource, item) for item in declared)
    )


def _normalize_surfaces(
    surfaces: Sequence[Mapping[str, Any]],
    *,
    kind: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in surfaces:
        if not isinstance(raw, Mapping):
            raise PreMutationBlastRadiusFailure(f"{kind} surface must be an object")
        name = str(raw.get("name") or "").strip()
        resource = str(raw.get("shared_resource") or "").strip().lower()
        patterns = [
            str(item or "").strip().replace("\\", "/")
            for item in (raw.get("trigger_paths") or [])
            if str(item or "").strip()
        ]
        if not name or not resource or not patterns:
            raise PreMutationBlastRadiusFailure(
                f"{kind} surface requires name/shared_resource/trigger_paths"
            )
        parse_resource(resource)
        normalized.append(
            {
                "name": name,
                "shared_resource": resource,
                "trigger_paths": sorted(set(patterns)),
            }
        )
    names = [row["name"] for row in normalized]
    if len(names) != len(set(names)):
        raise PreMutationBlastRadiusFailure(f"duplicate {kind} surface name")
    return normalized


def _surface_impacts(
    surfaces: Sequence[Mapping[str, Any]],
    *,
    candidate_paths: Sequence[str],
    kind: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for surface in _normalize_surfaces(surfaces, kind=kind):
        matches = sorted(
            path
            for path in candidate_paths
            if any(
                fnmatch.fnmatchcase(path, pattern)
                for pattern in surface["trigger_paths"]
            )
        )
        if matches:
            out.append(
                {
                    **surface,
                    "matched_paths": matches,
                }
            )
    return out


def _impact_paths(
    proposed_paths: Sequence[str],
    *,
    plan: Mapping[str, Any],
    root: str | Path,
) -> list[str]:
    paths = set(proposed_paths)
    paths.update(str(item) for item in (plan.get("impacted_entrypoints") or []))
    try:
        graph = build_dependency_map(root)
    except Exception as exc:
        raise PreMutationBlastRadiusFailure(
            "unable to build dependency map for exact impact paths"
        ) from exc

    for report in plan.get("reports") or []:
        for field in ("direct_dependents", "transitive_dependents"):
            for module in report.get(field) or []:
                path = graph.module_to_path.get(module)
                if path:
                    paths.add(str(path).replace("\\", "/"))
    return sorted(_norm_path(path) for path in paths if str(path).strip())


def compile_required_scope(
    proposed_paths: Iterable[str],
    *,
    root: str | Path = ".",
    expected_head_sha: str,
    observed_head_sha: str,
    workflow_surfaces: Sequence[Mapping[str, Any]] = (),
    deployment_surfaces: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    proposed = sorted({_norm_path(path) for path in proposed_paths})
    if not proposed:
        raise PreMutationBlastRadiusFailure("at least one proposed path is required")

    expected = _sha(expected_head_sha, "expected_head_sha")
    observed = _sha(observed_head_sha, "observed_head_sha")

    plan = plan_change(
        proposed,
        root=root,
        expected_head_sha=expected,
        observed_head_sha=observed,
    )
    impact_paths = (
        _impact_paths(proposed, plan=plan, root=root)
        if plan.get("state") != "STALE_HEAD"
        else proposed
    )
    workflows = _surface_impacts(
        workflow_surfaces,
        candidate_paths=impact_paths,
        kind="workflow",
    )
    deployments = _surface_impacts(
        deployment_surfaces,
        candidate_paths=impact_paths,
        kind="deployment",
    )

    blast_scope = scope_from_blast_radius(plan, write_paths=proposed)
    surface_resources = [
        row["shared_resource"] for row in workflows + deployments
    ]
    required_scope = build_scope(
        write_paths=blast_scope["write_paths"],
        dependency_tokens=blast_scope["dependency_tokens"],
        shared_resources=[
            *blast_scope["shared_resources"],
            *surface_resources,
        ],
        resource_identity={"main:base": expected},
        exclusive=blast_scope["exclusive"],
    )
    return {
        "plan": plan,
        "impact_paths": impact_paths,
        "workflow_impacts": workflows,
        "deployment_impacts": deployments,
        "required_scope": required_scope,
    }


def _live_holders(
    lease_state: Mapping[str, Any],
    *,
    now_utc: str,
    excluding_owner_id: str,
) -> list[dict[str, Any]]:
    validated = validate_lease_state(lease_state)
    now = _utc(now_utc)
    return [
        deepcopy(holder)
        for holder in validated["holders"]
        if holder["owner_id"] != excluding_owner_id
        and now < _utc(holder["expires_at_utc"])
    ]


def _next_action(blockers: Sequence[Mapping[str, Any]]) -> str:
    if not blockers:
        return "REQUEST_STEP_2A_MUTATION_GATE"
    mapping = {
        "STALE_HEAD": "REFRESH_HEAD_AND_REPLAN",
        "LEGACY_BLAST_BLOCKED": "NARROW_EDIT_SCOPE",
        "DIRECT_FROZEN_ARTIFACT": "STOP_OR_REQUEST_EXPLICIT_THAW",
        "TRANSITIVE_FROZEN_REACH": "NARROW_OR_RECERTIFY_FROZEN_DEPENDENT",
        "UNDECLARED_WRITE_PATH": "EXPAND_OR_NARROW_DECLARED_SCOPE",
        "UNDECLARED_DEPENDENCY_TOKEN": "EXPAND_DECLARED_DEPENDENCY_SCOPE",
        "UNDECLARED_SHARED_RESOURCE": "EXPAND_DECLARED_RESOURCE_SCOPE",
        "BASE_IDENTITY_MISMATCH": "REBUILD_SCOPE_FROM_CURRENT_HEAD",
        "LIVE_WORKSTREAM_CONFLICT": "QUEUE_OR_SHARD_CONFLICTING_RESOURCE",
    }
    return mapping.get(str(blockers[0].get("code")), "RUN_AUTOMATIC_ROOT_CAUSE_BACKTRACE")


def simulate_mutation(
    proposed_paths: Iterable[str],
    *,
    root: str | Path = ".",
    expected_head_sha: str,
    observed_head_sha: str,
    owner_id: str,
    now_utc: str,
    declared_scope: Mapping[str, Any],
    frozen_registry: Mapping[str, Any],
    lease_state: Mapping[str, Any],
    workflow_surfaces: Sequence[Mapping[str, Any]] = (),
    deployment_surfaces: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if BLAST_MAP_VERSION != REQUIRED_BLAST_MAP_VERSION:
        raise PreMutationBlastRadiusFailure("V3 blast-map version mismatch")
    if FROZEN_REGISTRY_VERSION != REQUIRED_FROZEN_REGISTRY_VERSION:
        raise PreMutationBlastRadiusFailure("frozen-registry version mismatch")
    if SCOPE_LEASE_VERSION != REQUIRED_SCOPE_LEASE_VERSION:
        raise PreMutationBlastRadiusFailure("scope-lease version mismatch")
    if SHARDING_VERSION != REQUIRED_SHARDING_VERSION:
        raise PreMutationBlastRadiusFailure("sharding version mismatch")

    owner = str(owner_id or "").strip()
    if not owner:
        raise PreMutationBlastRadiusFailure("owner_id is required")
    expected = _sha(expected_head_sha, "expected_head_sha")
    observed = _sha(observed_head_sha, "observed_head_sha")
    declared = build_scope(**dict(declared_scope))
    registry = validate_registry(frozen_registry)
    validated_lease = validate_lease_state(lease_state)

    compiled = compile_required_scope(
        proposed_paths,
        root=root,
        expected_head_sha=expected,
        observed_head_sha=observed,
        workflow_surfaces=workflow_surfaces,
        deployment_surfaces=deployment_surfaces,
    )
    plan = compiled["plan"]
    required = compiled["required_scope"]
    impact_paths = compiled["impact_paths"]
    frozen_paths = set(registry["artifacts"])

    blockers: list[dict[str, Any]] = []

    if expected != observed:
        blockers.append(
            {
                "code": "STALE_HEAD",
                "expected_head_sha": expected,
                "observed_head_sha": observed,
            }
        )

    if plan.get("edit_allowed") is not True:
        blockers.append(
            {
                "code": "LEGACY_BLAST_BLOCKED",
                "legacy_state": plan.get("state"),
                "legacy_next_action": plan.get("next_legal_action"),
            }
        )

    proposed_set = set(required["write_paths"])
    direct_frozen = sorted(proposed_set & frozen_paths)
    transitive_frozen = sorted((set(impact_paths) & frozen_paths) - proposed_set)
    if direct_frozen:
        blockers.append(
            {
                "code": "DIRECT_FROZEN_ARTIFACT",
                "paths": direct_frozen,
            }
        )
    if transitive_frozen:
        blockers.append(
            {
                "code": "TRANSITIVE_FROZEN_REACH",
                "paths": transitive_frozen,
            }
        )

    undeclared_writes = sorted(
        path
        for path in required["write_paths"]
        if not _path_covered(path, declared["write_paths"])
    )
    if undeclared_writes:
        blockers.append(
            {
                "code": "UNDECLARED_WRITE_PATH",
                "paths": undeclared_writes,
            }
        )

    missing_dependencies = sorted(
        set(required["dependency_tokens"]) - set(declared["dependency_tokens"])
    )
    if missing_dependencies:
        blockers.append(
            {
                "code": "UNDECLARED_DEPENDENCY_TOKEN",
                "tokens": missing_dependencies,
            }
        )

    missing_resources = _missing_resources(
        required["shared_resources"],
        declared["shared_resources"],
    )
    if missing_resources:
        blockers.append(
            {
                "code": "UNDECLARED_SHARED_RESOURCE",
                "resources": missing_resources,
            }
        )

    declared_base = str(
        declared["resource_identity"].get("main:base") or ""
    ).strip().lower()
    if declared_base != expected:
        blockers.append(
            {
                "code": "BASE_IDENTITY_MISMATCH",
                "expected_main_base": expected,
                "declared_main_base": declared_base,
            }
        )

    live_conflicts: list[dict[str, Any]] = []
    for holder in _live_holders(
        validated_lease,
        now_utc=now_utc,
        excluding_owner_id=owner,
    ):
        conflict, reasons = shard_aware_scopes_conflict(
            declared,
            holder["scope"],
        )
        if conflict:
            live_conflicts.append(
                {
                    "owner_id": holder["owner_id"],
                    "lease_id": holder["lease_id"],
                    "conflict_reasons": reasons,
                    "expires_at_utc": holder["expires_at_utc"],
                }
            )
    if live_conflicts:
        blockers.append(
            {
                "code": "LIVE_WORKSTREAM_CONFLICT",
                "holders": live_conflicts,
            }
        )

    status = "GREEN" if not blockers else "BLOCKED"
    decision = (
        "SAFE_TO_REQUEST_MUTATION_GATE"
        if not blockers
        else "PRE_MUTATION_BLOCKED"
    )
    next_action = _next_action(blockers)

    receipt_core = {
        "version": VERSION,
        "owner_id": owner,
        "expected_head_sha": expected,
        "observed_head_sha": observed,
        "proposed_paths": required["write_paths"],
        "impact_paths": impact_paths,
        "required_scope": required,
        "declared_scope": declared,
        "workflow_impacts": compiled["workflow_impacts"],
        "deployment_impacts": compiled["deployment_impacts"],
        "frozen_registry_state_hash": registry["state_hash"],
        "lease_state_hash": validated_lease["state_hash"],
        "legacy_blast_state": plan.get("state"),
        "legacy_blast_risk": plan.get("risk"),
        "blockers": blockers,
        "decision": decision,
    }
    receipt_digest = "sha256:" + _digest(receipt_core)

    return {
        "version": VERSION,
        "status": status,
        "decision": decision,
        "owner_id": owner,
        "expected_head_sha": expected,
        "observed_head_sha": observed,
        "proposed_paths": required["write_paths"],
        "impact_paths": impact_paths,
        "legacy_blast": {
            "version": plan.get("version"),
            "state": plan.get("state"),
            "risk": plan.get("risk"),
            "blast_radius": plan.get("blast_radius"),
            "impacted_entrypoints": plan.get("impacted_entrypoints") or [],
            "protected_reach": plan.get("protected_reach") or [],
        },
        "required_scope": required,
        "declared_scope": declared,
        "workflow_impacts": compiled["workflow_impacts"],
        "deployment_impacts": compiled["deployment_impacts"],
        "direct_frozen_artifacts": direct_frozen,
        "transitive_frozen_reach": transitive_frozen,
        "live_workstream_conflicts": live_conflicts,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "simulation_receipt_digest": receipt_digest,
        "frozen_registry_state_hash": registry["state_hash"],
        "lease_state_hash": validated_lease["state_hash"],
        "next_legal_action": next_action,
        "step_2a_required": True,
        "mutation_authority": False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def _self_test_registry(path: str) -> dict[str, Any]:
    registry = {
        "schema_version": 1,
        "version": FROZEN_REGISTRY_VERSION,
        "repository": "owner/repo",
        "registry_ref": REGISTRY_REF,
        "registry_path": REGISTRY_PATH,
        "revision": 1,
        "source_main_sha": "a" * 40,
        "entries": {
            "TEST": {
                "status": "FROZEN",
                "checkpoint_id": "TEST",
                "source_main_sha": "a" * 40,
                "artifacts": {path: "f" * 40},
            }
        },
        "active_thaws": [],
    }
    registry["state_hash"] = _digest(registry)
    return registry


def contract_self_test() -> dict[str, Any]:
    import tempfile

    from devsystem.scope_aware_execution_lease_v1 import new_state as new_lease_state

    head = "a" * 40
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "leaf.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "feature.py").write_text("import leaf\n", encoding="utf-8")
        (root / "app.py").write_text("import feature\n", encoding="utf-8")
        (root / "frozen_guard.py").write_text("VALUE = 1\n", encoding="utf-8")

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
        compiled = compile_required_scope(
            ["leaf.py"],
            root=root,
            expected_head_sha=head,
            observed_head_sha=head,
            workflow_surfaces=workflows,
            deployment_surfaces=deployments,
        )
        req = compiled["required_scope"]
        declared = build_scope(
            write_paths=req["write_paths"],
            dependency_tokens=req["dependency_tokens"],
            shared_resources=req["shared_resources"],
            resource_identity={"main:base": head},
        )
        lease = new_lease_state("owner/repo")
        allowed = simulate_mutation(
            ["leaf.py"],
            root=root,
            expected_head_sha=head,
            observed_head_sha=head,
            owner_id="chat:monster",
            now_utc="2026-10-02T03:00:00Z",
            declared_scope=declared,
            frozen_registry=_self_test_registry("frozen_guard.py"),
            lease_state=lease,
            workflow_surfaces=workflows,
            deployment_surfaces=deployments,
        )

        frozen_dependency = _self_test_registry("app.py")
        frozen_reach = simulate_mutation(
            ["leaf.py"],
            root=root,
            expected_head_sha=head,
            observed_head_sha=head,
            owner_id="chat:monster",
            now_utc="2026-10-02T03:00:00Z",
            declared_scope=declared,
            frozen_registry=frozen_dependency,
            lease_state=lease,
            workflow_surfaces=workflows,
            deployment_surfaces=deployments,
        )

        stale = simulate_mutation(
            ["leaf.py"],
            root=root,
            expected_head_sha=head,
            observed_head_sha="b" * 40,
            owner_id="chat:monster",
            now_utc="2026-10-02T03:00:00Z",
            declared_scope=declared,
            frozen_registry=_self_test_registry("frozen_guard.py"),
            lease_state=lease,
            workflow_surfaces=workflows,
            deployment_surfaces=deployments,
        )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "blast_map_version_bound": BLAST_MAP_VERSION == REQUIRED_BLAST_MAP_VERSION,
        "frozen_registry_version_bound": (
            FROZEN_REGISTRY_VERSION == REQUIRED_FROZEN_REGISTRY_VERSION
        ),
        "scope_lease_version_bound": SCOPE_LEASE_VERSION == REQUIRED_SCOPE_LEASE_VERSION,
        "sharding_version_bound": SHARDING_VERSION == REQUIRED_SHARDING_VERSION,
        "safe_change_allowed_to_gate": (
            allowed["decision"] == "SAFE_TO_REQUEST_MUTATION_GATE"
            and allowed["blocker_count"] == 0
        ),
        "workflow_impact_detected": (
            [row["name"] for row in allowed["workflow_impacts"]] == ["unit"]
        ),
        "transitive_deployment_impact_detected": (
            [row["name"] for row in allowed["deployment_impacts"]] == ["app"]
        ),
        "transitive_frozen_reach_blocked": (
            frozen_reach["decision"] == "PRE_MUTATION_BLOCKED"
            and frozen_reach["transitive_frozen_reach"] == ["app.py"]
        ),
        "stale_head_blocked": (
            stale["decision"] == "PRE_MUTATION_BLOCKED"
            and any(row["code"] == "STALE_HEAD" for row in stale["blockers"])
        ),
        "receipt_is_tamper_evident": (
            allowed["simulation_receipt_digest"].startswith("sha256:")
            and len(allowed["simulation_receipt_digest"]) == 71
        ),
        "step_2a_still_required": allowed["step_2a_required"] is True,
        "mutation_authority_granted": allowed["mutation_authority"] is True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }

    # mutation_authority_granted is intentionally false; express the invariant
    # without weakening the self-test readability.
    result["mutation_authority_granted"] = allowed["mutation_authority"]

    required = [
        "blast_map_version_bound",
        "frozen_registry_version_bound",
        "scope_lease_version_bound",
        "sharding_version_bound",
        "safe_change_allowed_to_gate",
        "workflow_impact_detected",
        "transitive_deployment_impact_detected",
        "transitive_frozen_reach_blocked",
        "stale_head_blocked",
        "receipt_is_tamper_evident",
        "step_2a_still_required",
    ]
    if not all(result[name] is True for name in required):
        raise PreMutationBlastRadiusFailure("pre-mutation simulator self-test failed")
    if (
        result["mutation_authority_granted"]
        or result["network_calls"]
        or result["auto_mutate"]
        or result["may_modify_product_runtime"]
    ):
        raise PreMutationBlastRadiusFailure("read-only safety invariant failed")
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V8_STEP1_PRE_MUTATION_BLAST_RADIUS_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreMutationBlastRadiusFailure as exc:
        print("MONSTER_V8_STEP1_PRE_MUTATION_BLAST_RADIUS_BLOCKED: " + str(exc))
        raise SystemExit(1)
