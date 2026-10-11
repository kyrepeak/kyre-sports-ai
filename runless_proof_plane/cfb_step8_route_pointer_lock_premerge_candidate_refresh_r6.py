from __future__ import annotations

from copy import deepcopy

from . import cfb_step8_route_pointer_lock_premerge_r1 as r1

OLD_CANDIDATE_SHA = "4049b40d90a325928dd8d142ff6827ab7af97294"
NEW_CANDIDATE_SHA = "62453749a79c5ffba944a27075fd4b69aaea9098"

# Refresh the exact candidate before loading registry reconciliation/proof execution.
r1.CANDIDATE_SHA = NEW_CANDIDATE_SHA

from . import cfb_step8_route_pointer_lock_premerge_reconcile_r4 as reconcile  # noqa: E402,F401


def _retarget_thaw(client) -> dict:
    raw = client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH)
    registry = r1._decode(raw)
    r1.validate_registry(registry)

    expected_files = {
        r1.ROUTER_PATH: {
            "from_blob": r1.FROM_BLOB,
            "to_blob": r1.TO_BLOB,
        }
    }
    matches = [x for x in registry.get("active_thaws", []) if x.get("thaw_id") == r1.THAW_ID]
    if len(matches) != 1:
        raise r1.RoutePointerPremergeFailure("CANDIDATE_THAW_NOT_UNIQUE")
    grant = matches[0]
    if grant.get("status") != "ACTIVE" or (grant.get("files") or {}) != expected_files:
        raise r1.RoutePointerPremergeFailure("CANDIDATE_THAW_FILE_DRIFT")

    target = str(grant.get("target_head_sha") or "")
    if target == NEW_CANDIDATE_SHA:
        return {
            "status": "ALREADY_RETARGETED",
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
        }
    if target != OLD_CANDIDATE_SHA:
        raise r1.RoutePointerPremergeFailure("CANDIDATE_THAW_TARGET_DRIFT:" + target)

    updated = deepcopy(registry)
    for item in updated["active_thaws"]:
        if item.get("thaw_id") == r1.THAW_ID:
            item["target_head_sha"] = NEW_CANDIDATE_SHA
            break
    updated["revision"] = int(registry["revision"]) + 1
    updated["state_hash"] = r1.registry_hash(r1._payload_without_hash(updated))
    r1.validate_registry(updated)
    client.update_content(
        r1.REGISTRY_PATH,
        r1._text(updated),
        r1.REGISTRY_BRANCH,
        "registry: retarget CFB Step8 proof to corrected static-plan head",
        raw["sha"],
    )

    readback = r1._decode(client.content(r1.REGISTRY_PATH, ref=r1.REGISTRY_BRANCH))
    r1.validate_registry(readback)
    rb = [x for x in readback.get("active_thaws", []) if x.get("thaw_id") == r1.THAW_ID]
    if (
        len(rb) != 1
        or rb[0].get("target_head_sha") != NEW_CANDIDATE_SHA
        or (rb[0].get("files") or {}) != expected_files
    ):
        raise r1.RoutePointerPremergeFailure("CANDIDATE_THAW_RETARGET_READBACK_FAILED")
    return {
        "status": "RETARGETED",
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
    }


_reconciled_execute = r1.execute


def _execute_refreshed_candidate(app):
    _retarget_thaw(app.state.github_client)
    return _reconciled_execute(app)


r1.execute = _execute_refreshed_candidate
install_startup = r1.install_startup
