from __future__ import annotations

from . import cfb_step8_terminal_route_lock_fast_cert_r6 as fast

terminal = fast.r5.terminal

STALE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-route-pointer-lock-postmerge-r1"
STALE_LEASE_ID = "SCOPE-LEASE-F5A2266F52B41427BB1634DF"
CANDIDATE_SHA = fast.r5.CANDIDATE_SHA
PRODUCT_MAIN_SHA = fast.r5.PRODUCT_MAIN_SHA

_original_execute = terminal.execute


def _release_oom_terminal_lease(client) -> dict:
    raw = client.content(terminal.LEASE_PATH, ref=terminal.LEASE_BRANCH)
    state = terminal.validate_scope_state(terminal._decode(raw))
    matches = [
        holder
        for holder in state.get("holders", [])
        if holder.get("owner_id") == STALE_OWNER
        and holder.get("lease_id") == STALE_LEASE_ID
    ]
    if not matches:
        return {
            "status": "ALREADY_RELEASED",
            "revision": state["revision"],
            "state_hash": state["state_hash"],
        }
    if len(matches) != 1:
        raise terminal.TerminalFreezeFailure("R7_STALE_LEASE_NOT_UNIQUE")

    holder = matches[0]
    scope = holder.get("scope") or {}
    deps = set(scope.get("dependency_tokens") or [])
    identity = scope.get("resource_identity") or {}
    if (
        f"candidate:{CANDIDATE_SHA}" not in deps
        or f"product-main:{PRODUCT_MAIN_SHA}" not in deps
        or "cfb:game-total:step8" not in deps
        or identity.get("main_sha") != PRODUCT_MAIN_SHA
    ):
        raise terminal.TerminalFreezeFailure("R7_STALE_LEASE_IDENTITY_DRIFT")

    released = terminal.release_scope(
        state,
        owner_id=STALE_OWNER,
        lease_id=STALE_LEASE_ID,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    if released["result"].get("allowed") is not True:
        raise terminal.TerminalFreezeFailure(
            "R7_STALE_LEASE_RELEASE_FAILED:" + str(released["result"])
        )

    client.update_content(
        terminal.LEASE_PATH,
        terminal._text(released["state"]),
        terminal.LEASE_BRANCH,
        "lease: recover OOM CFB Step8 terminal owner",
        raw["sha"],
    )
    readback = terminal.validate_scope_state(
        terminal._decode(client.content(terminal.LEASE_PATH, ref=terminal.LEASE_BRANCH))
    )
    if any(
        holder.get("owner_id") == STALE_OWNER
        and holder.get("lease_id") == STALE_LEASE_ID
        for holder in readback.get("holders", [])
    ):
        raise terminal.TerminalFreezeFailure("R7_STALE_LEASE_RELEASE_READBACK_FAILED")
    return {
        "status": "RELEASED_AFTER_RENDER_OOM",
        "revision": readback["revision"],
        "state_hash": readback["state_hash"],
    }


def _execute_r7(app):
    recovery = _release_oom_terminal_lease(app.state.github_client)
    result = _original_execute(app)
    result["oom_deadman_recovery"] = recovery
    return result


terminal.execute = _execute_r7
install_startup = terminal.install_startup
