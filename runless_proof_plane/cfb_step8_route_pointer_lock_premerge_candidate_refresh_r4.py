from __future__ import annotations

from copy import deepcopy

from . import cfb_step8_route_pointer_lock_premerge_r1 as r1

OLD_CANDIDATE_SHA = "892798332abfd1b696a9e4809d51861302c6c3b3"
NEW_CANDIDATE_SHA = "4049b40d90a325928dd8d142ff6827ab7af97294"
REGISTRY_BASE_MAIN_SHA = "283151c3792a73520a37b54bb8f480910004b6d6"

# Refresh the exact candidate identity before importing the descendant verifier.
r1.CANDIDATE_SHA = NEW_CANDIDATE_SHA

from . import cfb_step8_route_pointer_lock_premerge_descendant_r3 as r3  # noqa: E402,F401


def _ensure_thaw(client):
    raw = client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH)
    reg = r1._decode(raw)
    r1.validate_registry(reg)

    registry_source = str(reg.get("source_main_sha") or "")
    if registry_source not in {REGISTRY_BASE_MAIN_SHA, r1.MAIN_SHA}:
        raise r1.RoutePointerPremergeFailure("REGISTRY_MAIN_DRIFT:" + registry_source)

    main_tree = client.tree_blobs(r1.MAIN_SHA)
    if main_tree.get(r1.ROUTER_PATH) != r1.FROM_BLOB:
        raise r1.RoutePointerPremergeFailure("MAIN_ROUTER_BASELINE_DRIFT")

    expected_files = {
        r1.ROUTER_PATH: {
            "from_blob": r1.FROM_BLOB,
            "to_blob": r1.TO_BLOB,
        }
    }
    same_id = [x for x in reg.get("active_thaws", []) if x.get("thaw_id") == r1.THAW_ID]
    updated = deepcopy(reg)
    changed = False

    if same_id:
        if len(same_id) != 1:
            raise r1.RoutePointerPremergeFailure("THAW_IDENTITY_DRIFT")
        grant = same_id[0]
        if grant.get("status") != "ACTIVE" or (grant.get("files") or {}) != expected_files:
            raise r1.RoutePointerPremergeFailure("THAW_IDENTITY_DRIFT")
        target = str(grant.get("target_head_sha") or "")
        if target not in {OLD_CANDIDATE_SHA, NEW_CANDIDATE_SHA}:
            raise r1.RoutePointerPremergeFailure("THAW_TARGET_DRIFT:" + target)
        if target == OLD_CANDIDATE_SHA:
            for item in updated["active_thaws"]:
                if item.get("thaw_id") == r1.THAW_ID:
                    item["target_head_sha"] = NEW_CANDIDATE_SHA
                    changed = True
                    break
    else:
        updated["active_thaws"].append({
            "thaw_id": r1.THAW_ID,
            "status": "ACTIVE",
            "target_head_sha": NEW_CANDIDATE_SHA,
            "files": expected_files,
        })
        updated["active_thaws"] = sorted(
            updated["active_thaws"], key=lambda x: str(x.get("thaw_id") or "")
        )
        changed = True

    duplicates = [
        x for x in updated.get("active_thaws", [])
        if x.get("target_head_sha") == NEW_CANDIDATE_SHA
        and r1.ROUTER_PATH in (x.get("files") or {})
        and x.get("thaw_id") != r1.THAW_ID
    ]
    if duplicates:
        raise r1.RoutePointerPremergeFailure("DUPLICATE_EXACT_HEAD_THAW")

    if changed:
        updated["revision"] = int(reg["revision"]) + 1
        updated["state_hash"] = r1.registry_hash(r1._payload_without_hash(updated))
        r1.validate_registry(updated)
        client.update_content(
            r1.REGISTRY_PATH,
            r1._text(updated),
            r1.REGISTRY_BRANCH,
            "registry: retarget CFB Step8 route-pointer lock exact head",
            raw["sha"],
        )

    rb = r1._decode(client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH))
    r1.validate_registry(rb)
    match = [x for x in rb.get("active_thaws", []) if x.get("thaw_id") == r1.THAW_ID]
    if len(match) != 1:
        raise r1.RoutePointerPremergeFailure("THAW_READBACK_FAILED")
    grant = match[0]
    if (
        grant.get("target_head_sha") != NEW_CANDIDATE_SHA
        or grant.get("status") != "ACTIVE"
        or (grant.get("files") or {}) != expected_files
    ):
        raise r1.RoutePointerPremergeFailure("THAW_READBACK_FAILED")
    return {
        "revision": int(rb["revision"]),
        "state_hash": str(rb["state_hash"]),
        "reused": not changed,
    }


r1._ensure_thaw = _ensure_thaw
install_startup = r1.install_startup
