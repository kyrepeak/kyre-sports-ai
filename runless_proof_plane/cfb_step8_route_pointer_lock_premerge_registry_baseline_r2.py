from __future__ import annotations

from copy import deepcopy

from . import cfb_step8_route_pointer_lock_premerge_r1 as r1

REGISTRY_BASE_MAIN_SHA = "283151c3792a73520a37b54bb8f480910004b6d6"


def _ensure_thaw(client):
    raw = client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH)
    reg = r1._decode(raw)
    r1.validate_registry(reg)

    registry_source = str(reg.get("source_main_sha") or "")
    if registry_source not in {REGISTRY_BASE_MAIN_SHA, r1.MAIN_SHA}:
        raise r1.RoutePointerPremergeFailure(
            "REGISTRY_MAIN_DRIFT:" + registry_source
        )

    # The global registry may legitimately still point at the previously
    # certified baseline while later frozen entries already bind the exact
    # router blob used by current main. Allow that state only when current
    # main still carries the exact frozen router blob that this thaw starts
    # from. Any product drift fails closed.
    main_tree = client.tree_blobs(r1.MAIN_SHA)
    if main_tree.get(r1.ROUTER_PATH) != r1.FROM_BLOB:
        raise r1.RoutePointerPremergeFailure("MAIN_ROUTER_BASELINE_DRIFT")

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
    same_id = [x for x in reg.get("active_thaws", []) if x.get("thaw_id") == r1.THAW_ID]
    if same_id:
        if len(same_id) != 1 or same_id[0] != expected:
            raise r1.RoutePointerPremergeFailure("THAW_IDENTITY_DRIFT")
        return {
            "revision": int(reg["revision"]),
            "state_hash": str(reg["state_hash"]),
            "reused": True,
        }

    duplicates = [
        x
        for x in reg.get("active_thaws", [])
        if x.get("target_head_sha") == r1.CANDIDATE_SHA
        and r1.ROUTER_PATH in (x.get("files") or {})
    ]
    if duplicates:
        raise r1.RoutePointerPremergeFailure("DUPLICATE_EXACT_HEAD_THAW")

    updated = deepcopy(reg)
    updated["active_thaws"].append(expected)
    updated["active_thaws"] = sorted(
        updated["active_thaws"], key=lambda x: str(x.get("thaw_id") or "")
    )
    updated["revision"] = int(updated["revision"]) + 1
    updated["state_hash"] = r1.registry_hash(r1._payload_without_hash(updated))
    r1.validate_registry(updated)
    client.update_content(
        r1.REGISTRY_PATH,
        r1._text(updated),
        r1.REGISTRY_BRANCH,
        "registry: thaw CFB Step8 route-pointer lock candidate",
        raw["sha"],
    )
    rb = r1._decode(client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH))
    r1.validate_registry(rb)
    match = [x for x in rb.get("active_thaws", []) if x.get("thaw_id") == r1.THAW_ID]
    if len(match) != 1 or match[0] != expected:
        raise r1.RoutePointerPremergeFailure("THAW_READBACK_FAILED")
    return {
        "revision": int(rb["revision"]),
        "state_hash": str(rb["state_hash"]),
        "reused": False,
    }


r1._ensure_thaw = _ensure_thaw
install_startup = r1.install_startup
