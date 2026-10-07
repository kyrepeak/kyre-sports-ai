from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry

from .registry import GithubRegistryBackend, REGISTRY_PATH

OLD_MAIN_SHA = "51762ad9226b119626284655a90bd7ac7da80d5e"
NEW_MAIN_SHA = "552f7b88b507f132a739900ce05adae96dc7fca1"
EXPECTED_REVISION = 168
EXPECTED_REGISTRY_HASH = "d0ff4e8c17bd4c290a2911f9236e7ef3261acc44402956a05120bc64ac5d5a3b"


class Task17Step3RegistryReconcileFailure(RuntimeError):
    pass


def _authorized_frozen_delta(registry: dict, *, path: str, expected: str, actual: str, parent_shas: set[str]) -> bool:
    for grant in registry.get("active_thaws", []):
        if str(grant.get("target_head_sha") or "") not in parent_shas:
            continue
        pair = (grant.get("files") or {}).get(path)
        if not isinstance(pair, dict):
            continue
        if str(pair.get("from_blob") or "").lower() == expected and str(pair.get("to_blob") or "").lower() == actual:
            return True
    return False


def execute(client):
    if client.branch_sha("main") != NEW_MAIN_SHA:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_MAIN_DRIFT")

    commit = client.commit(NEW_MAIN_SHA)
    parent_shas = {str(item.get("sha") or "") for item in (commit.get("parents") or [])}
    if OLD_MAIN_SHA not in parent_shas:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_OLD_MAIN_NOT_PARENT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validated = validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != OLD_MAIN_SHA:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_SOURCE_MAIN_DRIFT")

    old_tree = client.tree_blobs(OLD_MAIN_SHA)
    new_tree = client.tree_blobs(NEW_MAIN_SHA)
    frozen_deltas = []
    inherited_frozen_drift = []
    for path, expected in sorted(validated["artifacts"].items()):
        old_blob = str(old_tree.get(path) or "").lower()
        new_blob = str(new_tree.get(path) or "").lower()
        if not old_blob or not new_blob:
            raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_FROZEN_PATH_MISSING:" + path)
        if old_blob == new_blob:
            if old_blob != expected:
                inherited_frozen_drift.append(path)
            continue
        if not _authorized_frozen_delta(
            registry,
            path=path,
            expected=expected,
            actual=new_blob,
            parent_shas=parent_shas,
        ):
            raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_UNAUTHORIZED_FROZEN_DELTA:" + path)
        frozen_deltas.append(path)

    entries_before = deepcopy(registry.get("entries") or {})
    thaws_before = deepcopy(registry.get("active_thaws") or [])
    updated = deepcopy(registry)
    updated["source_main_sha"] = NEW_MAIN_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)

    try:
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            backend.branch,
            "registry: reconcile source main after authorized WNBA merge",
            backend._blob_sha,
        )
    except Exception as exc:
        raise Task17Step3RegistryReconcileFailure("WAIT_REGISTRY_CAS_CONFLICT") from exc

    readback = backend.read_registry()
    validate_registry(readback)
    if readback.get("entries") != entries_before:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_ENTRY_DRIFT")
    if readback.get("active_thaws") != thaws_before:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_THAW_DRIFT")
    if str(readback.get("source_main_sha") or "") != NEW_MAIN_SHA:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_READBACK_MAIN_MISMATCH")
    if client.branch_sha("main") != NEW_MAIN_SHA:
        raise Task17Step3RegistryReconcileFailure("STEP3_RECONCILE_MAIN_MOVED_AFTER_WRITE")

    return {
        "status": "GREEN",
        "decision": "RUNLESS_TASK17_STEP3_REGISTRY_RECONCILED",
        "old_main_sha": OLD_MAIN_SHA,
        "new_main_sha": NEW_MAIN_SHA,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "authorized_frozen_delta_count": len(frozen_deltas),
        "authorized_frozen_deltas": frozen_deltas,
        "inherited_frozen_drift_count": len(inherited_frozen_drift),
        "entries_preserved": True,
        "thaws_preserved": True,
    }


def install_startup(app):
    app.state.task17_step3_registry_reconcile = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step3_registry_reconcile = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step3_registry_reconcile = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1600],
            }
        print(
            "RUNLESS_TASK17_STEP3_REGISTRY_RECONCILE="
            + json.dumps(app.state.task17_step3_registry_reconcile, sort_keys=True),
            flush=True,
        )

    return app
