from __future__ import annotations

import json
from copy import deepcopy

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry

from .registry import GithubRegistryBackend, REGISTRY_PATH

OLD_MAIN_SHA = "552f7b88b507f132a739900ce05adae96dc7fca1"
MERGED_MAIN_SHA = "d2e2b45398e4a22c1e020a5fb5aca7b10e1debbb"
CANDIDATE_SHA = "87544f9ddced25a6c390709a4d3c039637a6e4b0"
EXPECTED_REVISION = 169
EXPECTED_REGISTRY_HASH = "65089f6ea26017bdf74b1c41eecca03b506ecde752a315d816fb1313c2757b9c"


class Task17Step3PostmergeRetargetFailure(RuntimeError):
    pass


def execute(client):
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_MAIN_DRIFT")

    commit = client.commit(MERGED_MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in (commit.get("parents") or [])}
    if parents != {OLD_MAIN_SHA, CANDIDATE_SHA}:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_LINEAGE_DRIFT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validated = validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != OLD_MAIN_SHA:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_SOURCE_MAIN_DRIFT")

    old_tree = client.tree_blobs(OLD_MAIN_SHA)
    merged_tree = client.tree_blobs(MERGED_MAIN_SHA)
    changed_frozen = []
    inherited_frozen_drift = []
    for path, expected in sorted(validated["artifacts"].items()):
        old_blob = str(old_tree.get(path) or "").lower()
        merged_blob = str(merged_tree.get(path) or "").lower()
        if not old_blob or not merged_blob:
            raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_FROZEN_PATH_MISSING:" + path)
        if old_blob != merged_blob:
            changed_frozen.append(path)
        elif old_blob != expected:
            inherited_frozen_drift.append(path)
    if changed_frozen:
        raise Task17Step3PostmergeRetargetFailure(
            "STEP3_POSTMERGE_UNEXPECTED_FROZEN_DELTA:" + ",".join(changed_frozen)
        )

    entries_before = deepcopy(registry.get("entries") or {})
    thaws_before = deepcopy(registry.get("active_thaws") or [])
    updated = deepcopy(registry)
    updated["source_main_sha"] = MERGED_MAIN_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)

    try:
        client.update_content(
            REGISTRY_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            backend.branch,
            "registry: retarget Runless Task 17 Step 3 merged main",
            backend._blob_sha,
        )
    except Exception as exc:
        raise Task17Step3PostmergeRetargetFailure("WAIT_REGISTRY_CAS_CONFLICT") from exc

    readback = backend.read_registry()
    validate_registry(readback)
    if readback.get("entries") != entries_before:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_ENTRY_DRIFT")
    if readback.get("active_thaws") != thaws_before:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_THAW_DRIFT")
    if str(readback.get("source_main_sha") or "") != MERGED_MAIN_SHA:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_READBACK_MAIN_MISMATCH")
    if client.branch_sha("main") != MERGED_MAIN_SHA:
        raise Task17Step3PostmergeRetargetFailure("STEP3_POSTMERGE_MAIN_MOVED_AFTER_WRITE")

    return {
        "status": "GREEN",
        "decision": "RUNLESS_TASK17_STEP3_POSTMERGE_RETARGET_GREEN",
        "merged_main_sha": MERGED_MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "registry_revision": int(readback["revision"]),
        "registry_state_hash": str(readback["state_hash"]),
        "changed_frozen_path_count": 0,
        "inherited_frozen_drift_count": len(inherited_frozen_drift),
        "entries_preserved": True,
        "thaws_preserved": True,
        "main_mutated": False,
    }


def install_startup(app):
    app.state.task17_step3_postmerge_retarget = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step3_postmerge_retarget = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step3_postmerge_retarget = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1600],
            }
        print(
            "RUNLESS_TASK17_STEP3_POSTMERGE_RETARGET="
            + json.dumps(app.state.task17_step3_postmerge_retarget, sort_keys=True),
            flush=True,
        )

    return app
