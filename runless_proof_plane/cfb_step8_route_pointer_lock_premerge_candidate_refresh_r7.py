from __future__ import annotations

from copy import deepcopy

from . import cfb_step8_route_pointer_lock_premerge_r1 as r1

FINAL_CANDIDATE_SHA = "8ffbe91246f5022bcaca7a326cfaaf9a62976633"
ALLOWED_PREVIOUS_TARGETS = {
    "4049b40d90a325928dd8d142ff6827ab7af97294",
    "62453749a79c5ffba944a27075fd4b69aaea9098",
    FINAL_CANDIDATE_SHA,
}

# Pin the true branch head before loading descendant verification/reconciliation.
r1.CANDIDATE_SHA = FINAL_CANDIDATE_SHA

from . import cfb_step8_route_pointer_lock_premerge_reconcile_r4 as reconcile  # noqa: E402,F401


def _retarget_final_thaw(client) -> dict:
    raw = client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH)
    registry = r1._decode(raw)
    r1.validate_registry(registry)

    expected_files = {
        r1.ROUTER_PATH: {
            "from_blob": r1.FROM_BLOB,
            "to_blob": r1.TO_BLOB,
        }
    }
    matches = [
        x for x in registry.get("active_thaws", [])
        if x.get("thaw_id") == r1.THAW_ID
    ]
    if len(matches) != 1:
        raise r1.RoutePointerPremergeFailure("FINAL_CANDIDATE_THAW_NOT_UNIQUE")
    grant = matches[0]
    if grant.get("status") != "ACTIVE" or (grant.get("files") or {}) != expected_files:
        raise r1.RoutePointerPremergeFailure("FINAL_CANDIDATE_THAW_FILE_DRIFT")

    target = str(grant.get("target_head_sha") or "")
    if target not in ALLOWED_PREVIOUS_TARGETS:
        raise r1.RoutePointerPremergeFailure("FINAL_CANDIDATE_THAW_TARGET_DRIFT:" + target)
    if target == FINAL_CANDIDATE_SHA:
        return {
            "status": "ALREADY_RETARGETED",
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
        }

    updated = deepcopy(registry)
    for item in updated["active_thaws"]:
        if item.get("thaw_id") == r1.THAW_ID:
            item["target_head_sha"] = FINAL_CANDIDATE_SHA
            break
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = r1.registry_hash(r1._payload_without_hash(updated))
    r1.validate_registry(updated)
    client.update_content(
        r1.REGISTRY_PATH,
        r1._text(updated),
        r1.REGISTRY_BRANCH,
        "registry: pin final CFB Step8 route-pointer exact head",
        raw["sha"],
    )

    readback = r1._decode(client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH))
    r1.validate_registry(readback)
    rb = [
        x for x in readback.get("active_thaws", [])
        if x.get("thaw_id") == r1.THAW_ID
    ]
    if (
        len(rb) != 1
        or rb[0].get("target_head_sha") != FINAL_CANDIDATE_SHA
        or (rb[0].get("files") or {}) != expected_files
    ):
        raise r1.RoutePointerPremergeFailure("FINAL_CANDIDATE_THAW_READBACK_FAILED")
    return {
        "status": "RETARGETED",
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


_reconciled_execute = r1.execute


def _execute_final_candidate(app):
    _retarget_final_thaw(app.state.github_client)
    return _reconciled_execute(app)


r1.execute = _execute_final_candidate
install_startup = r1.install_startup
