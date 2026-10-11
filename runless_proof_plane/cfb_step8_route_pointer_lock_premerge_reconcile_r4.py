from __future__ import annotations

from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import (
    _hash as registry_hash,
    _payload_without_hash,
    validate_registry,
)
from devsystem.frozen_registry_auto_reconciler_v1 import plan_auto_reconciliation

from . import cfb_step8_route_pointer_lock_premerge_descendant_r3 as r3
from . import cfb_step8_route_pointer_lock_premerge_r1 as r1


class RegistryReconciliationFailure(RuntimeError):
    pass


def _eligible_merged_targets(client, registry: dict, main_sha: str) -> list[str]:
    source = str(registry.get("source_main_sha") or "")
    targets: list[str] = []
    for grant in registry.get("active_thaws", []):
        target = str(grant.get("target_head_sha") or "")
        if not target:
            continue
        if r3._is_ancestor(client, target, main_sha) and not r3._is_ancestor(client, target, source):
            targets.append(target)
    return sorted(set(targets))


def _candidate_thaw_intact(registry: dict) -> bool:
    expected = {
        "thaw_id": r1.THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": r1.CANDIDATE_SHA,
        "files": {
            r1.ROUTER_PATH: {
                "from_blob": r1.FROM_BLOB,
                "to_blob": r1.TO_BLOB,
            }
        },
    }
    matches = [x for x in registry.get("active_thaws", []) if x.get("thaw_id") == r1.THAW_ID]
    return len(matches) == 1 and matches[0] == expected


def reconcile_registry_to_main(client) -> dict:
    raw = client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH)
    registry = r1._decode(raw)
    validated = validate_registry(registry)

    main_sha = client.branch_sha("main")
    if main_sha != r1.MAIN_SHA:
        raise RegistryReconciliationFailure("MAIN_DRIFT:" + main_sha)

    source = str(registry.get("source_main_sha") or "")
    if source == main_sha:
        if not _candidate_thaw_intact(registry):
            raise RegistryReconciliationFailure("CANDIDATE_THAW_DRIFT")
        return {
            "status": "ALREADY_ALIGNED",
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
        }

    if not r3._is_ancestor(client, source, main_sha):
        raise RegistryReconciliationFailure(
            "REGISTRY_SOURCE_NOT_ANCESTOR:" + source + ":" + main_sha
        )

    main_tree = client.tree_blobs(main_sha)
    actual = {path: main_tree.get(path) for path in validated["artifacts"]}
    eligible = _eligible_merged_targets(client, registry, main_sha)
    plan = plan_auto_reconciliation(
        registry,
        actual_blobs=actual,
        main_sha=main_sha,
        merged_authority_heads=eligible,
    )

    decision = str(plan.get("decision") or "")
    if decision == "AUTO_RECONCILIATION_PLANNED":
        updated = deepcopy(plan["planned_registry"])
    elif decision == "REGISTRY_ALREADY_ALIGNED":
        updated = deepcopy(registry)
        updated["source_main_sha"] = main_sha
        updated["revision"] = int(registry["revision"]) + 1
        updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    else:
        raise RegistryReconciliationFailure(
            "REGISTRY_RECONCILIATION_BLOCKED:" + decision
        )

    validate_registry(updated)
    if str(updated.get("source_main_sha") or "") != main_sha:
        raise RegistryReconciliationFailure("PLANNED_MAIN_IDENTITY_DRIFT")
    if not _candidate_thaw_intact(updated):
        raise RegistryReconciliationFailure("PLANNED_CANDIDATE_THAW_DRIFT")

    client.update_content(
        r1.REGISTRY_PATH,
        r1._text(updated),
        r1.REGISTRY_BRANCH,
        "registry: reconcile frozen baseline to CFB Step8 main",
        raw["sha"],
    )

    readback = r1._decode(client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH))
    validate_registry(readback)
    if str(readback.get("source_main_sha") or "") != main_sha:
        raise RegistryReconciliationFailure("REGISTRY_MAIN_READBACK_FAILED")
    if not _candidate_thaw_intact(readback):
        raise RegistryReconciliationFailure("CANDIDATE_THAW_READBACK_FAILED")

    return {
        "status": "RECONCILED",
        "decision": decision,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "eligible_merged_targets": eligible,
    }


_original_execute = r1.execute


def _execute_with_registry_reconciliation(app):
    reconcile_registry_to_main(app.state.github_client)
    return _original_execute(app)


r1.execute = _execute_with_registry_reconciliation
install_startup = r1.install_startup
