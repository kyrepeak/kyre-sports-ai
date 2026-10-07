from __future__ import annotations

import json
from copy import deepcopy

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import validate_registry

from .registry import GithubRegistryBackend, REGISTRY_PATH

MAIN_SHA = "d908cdc3e8ea4b0224333268e7b02d0af3bd9063"
STEP17_MERGE_SHA = "ef550e9bd9898a67cc54a25ffd7ee5fcb1c6b129"
MERGED_CANDIDATE_SHA = "85e631a923b8433f3a7b86fbd4f0ad4a583a56df"
PATH = "runless_proof_plane/api.py"
FROM_BLOB = "185c07cb05fb5dc4937011330c6da6b7d5e8d1c5"
TO_BLOB = "3734146408aefba224f3ceed7c9385fc91eca68a"
THAW_ID = "THAW-RUNLESS-TASK17-STEP1-REAL-PROVE-R1"
EXPECTED_REVISION = 160
EXPECTED_HASH = "72a3706c04672c424d44169c880506625ec8dee6b7663b569ed83fb459d5ff22"


class Task17PostMergeForwardPortFailure(RuntimeError):
    pass


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise Task17PostMergeForwardPortFailure("WAIT_MAIN_IDENTITY_MOVED")

    step17_merge = client.commit(STEP17_MERGE_SHA)
    merge_parents = {str(item.get("sha") or "") for item in step17_merge.get("parents", [])}
    if MERGED_CANDIDATE_SHA not in merge_parents:
        raise Task17PostMergeForwardPortFailure("STEP17_CANDIDATE_NOT_PARENT_OF_MERGE")

    lineage = client.request("GET", f"/compare/{STEP17_MERGE_SHA}...{MAIN_SHA}")
    if str(lineage.get("status") or "") not in {"ahead", "identical"}:
        raise Task17PostMergeForwardPortFailure("STEP17_MERGE_NOT_ANCESTOR_OF_MAIN")

    main_tree = client.tree_blobs(MAIN_SHA)
    if str(main_tree.get(PATH) or "").lower() != TO_BLOB:
        raise Task17PostMergeForwardPortFailure("MERGED_MAIN_API_BLOB_DRIFT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REVISION:
        raise Task17PostMergeForwardPortFailure("WAIT_REGISTRY_REVISION_MOVED")
    if str(registry.get("state_hash") or "") != EXPECTED_HASH:
        raise Task17PostMergeForwardPortFailure("WAIT_REGISTRY_HASH_MOVED")

    matches = [item for item in registry.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise Task17PostMergeForwardPortFailure("STEP17_THAW_MISSING_OR_AMBIGUOUS")
    grant = matches[0]
    pair = (grant.get("files") or {}).get(PATH) or {}
    if str(grant.get("target_head_sha") or "") != MERGED_CANDIDATE_SHA:
        raise Task17PostMergeForwardPortFailure("STEP17_THAW_TARGET_DRIFT")
    if pair != {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}:
        raise Task17PostMergeForwardPortFailure("STEP17_THAW_BLOB_PAIR_DRIFT")

    unrelated_before = [
        deepcopy(item)
        for item in registry.get("active_thaws", [])
        if item.get("thaw_id") != THAW_ID
    ]

    planned = plan_baseline_forward_port(
        registry,
        updates={PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
        source_main_sha=MAIN_SHA,
    )
    updated = planned["registry"]

    if THAW_ID not in planned.get("retired_empty_thaw_grants", []):
        raise Task17PostMergeForwardPortFailure("STEP17_THAW_NOT_RETIRED")
    unrelated_after_plan = [
        item for item in updated.get("active_thaws", []) if item.get("thaw_id") != THAW_ID
    ]
    if unrelated_after_plan != unrelated_before:
        raise Task17PostMergeForwardPortFailure("UNRELATED_THAW_DRIFT_IN_PLAN")
    if int(updated["revision"]) != EXPECTED_REVISION + 1:
        raise Task17PostMergeForwardPortFailure("FORWARD_PORT_REVISION_INVALID")
    if str(updated.get("source_main_sha") or "") != MAIN_SHA:
        raise Task17PostMergeForwardPortFailure("FORWARD_PORT_MAIN_IDENTITY_INVALID")

    text = json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    try:
        client.update_content(
            REGISTRY_PATH,
            text,
            backend.branch,
            "registry: forward-port Runless Task 17 Step 1 merged api baseline",
            backend._blob_sha,
        )
    except Exception as exc:
        raise Task17PostMergeForwardPortFailure("WAIT_REGISTRY_CAS_CONFLICT") from exc

    readback = backend.read_registry()
    validated = validate_registry(readback)
    if int(readback["revision"]) != EXPECTED_REVISION + 1:
        raise Task17PostMergeForwardPortFailure("FORWARD_PORT_READBACK_REVISION_MISMATCH")
    if str(readback.get("source_main_sha") or "") != MAIN_SHA:
        raise Task17PostMergeForwardPortFailure("FORWARD_PORT_READBACK_MAIN_MISMATCH")
    if any(item.get("thaw_id") == THAW_ID for item in readback.get("active_thaws", [])):
        raise Task17PostMergeForwardPortFailure("STEP17_THAW_STILL_ACTIVE")
    if readback.get("active_thaws", []) != unrelated_before:
        raise Task17PostMergeForwardPortFailure("UNRELATED_THAW_READBACK_DRIFT")
    if str(validated["artifacts"].get(PATH) or "").lower() != TO_BLOB:
        raise Task17PostMergeForwardPortFailure("API_BASELINE_READBACK_MISMATCH")

    return {
        "status": "GREEN",
        "decision": "RUNLESS_TASK17_STEP1_POSTMERGE_FORWARD_PORT_GREEN",
        "merged_main_sha": MAIN_SHA,
        "step17_merge_sha": STEP17_MERGE_SHA,
        "previous_revision": EXPECTED_REVISION,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "updated_owner_count": len(planned.get("updated_entries", [])),
        "retired_thaw": THAW_ID,
        "unrelated_thaws_preserved": len(unrelated_before),
        "api_blob": TO_BLOB,
    }


def install_startup(app):
    app.state.task17_step1_postmerge_forward_port = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.task17_step1_postmerge_forward_port = execute(app.state.github_client)
        except Exception as exc:
            app.state.task17_step1_postmerge_forward_port = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1200],
            }
        print(
            "RUNLESS_TASK17_STEP1_POSTMERGE_FORWARD_PORT="
            + json.dumps(app.state.task17_step1_postmerge_forward_port, sort_keys=True),
            flush=True,
        )

    @app.get("/task17-step1-postmerge-forward-port/status")
    def _status():
        return app.state.task17_step1_postmerge_forward_port

    return app
