from __future__ import annotations

from . import cfb_step8_terminal_route_lock_r5 as r5

terminal = r5.terminal

FINAL_MAIN_SHA = "d4d5b5d4a0a2f376bf17eb7db0ec39d2a5adaee8"
FINAL_FREEZE_TOKEN = terminal.FREEZE_TOKEN
TERMINAL_RECEIPT_DIGEST = "60dc3939b565280a76d28ca706aa193674103f57a1662a46d0abe98f3a48cc65"
FINAL_OWNER = (
    "api2/cfb-game-total-native-website-rebuild-v1/"
    "step8-terminal-registry-rebind-v1"
)


class PostmergeRebindFailure(terminal.TerminalFreezeFailure):
    pass


def validate_closeout_snapshot(ledger, receipt, freeze_entry):
    if (
        ledger.get("status") != "GREEN_PLUS_FROZEN"
        or ledger.get("green_plus_frozen_claimed") is not True
        or ledger.get("next_legal_action") != "NONE_TERMINAL"
    ):
        raise PostmergeRebindFailure("TERMINAL_LEDGER_NOT_CLOSED")
    if receipt.get("digest") != TERMINAL_RECEIPT_DIGEST:
        raise PostmergeRebindFailure("TERMINAL_RECEIPT_DIGEST_DRIFT")
    if receipt.get("github_actions_fallback") != 0:
        raise PostmergeRebindFailure("GITHUB_ACTIONS_FALLBACK_DRIFT")
    if (
        freeze_entry.get("checkpoint_id") != FINAL_FREEZE_TOKEN
        or freeze_entry.get("status") != "FROZEN"
    ):
        raise PostmergeRebindFailure("FINAL_FREEZE_TOKEN_NOT_FROZEN")
    return {"status": "GREEN", "github_actions_fallback": 0}


def _claim(client, registry_hash):
    raw = client.content(terminal.LEASE_PATH, ref=terminal.LEASE_BRANCH)
    state = terminal.validate_scope_state(terminal._decode(raw))
    scope = terminal.build_scope(
        write_paths=[terminal.REGISTRY_PATH],
        dependency_tokens=[
            f"candidate:{r5.CANDIDATE_SHA}",
            f"product-main:{r5.PRODUCT_MAIN_SHA}",
            f"terminal-main:{FINAL_MAIN_SHA}",
            "cfb:game-total:step8",
        ],
        shared_resources=[
            "ref:monster-frozen-artifact-registry",
            "ref:runless-proof-receipts",
            "route:cfb-game-total",
        ],
        resource_identity={
            "main_sha": FINAL_MAIN_SHA,
            "registry_state_hash": registry_hash,
        },
        exclusive=False,
    )
    claimed = terminal.claim_scope(
        state,
        owner_id=FINAL_OWNER,
        now_utc=terminal._now(),
        scope=scope,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=1200,
    )
    if claimed["result"].get("allowed") is not True:
        raise PostmergeRebindFailure(
            "FINAL_REBIND_LEASE_BLOCKED:" + terminal.json.dumps(claimed["result"], sort_keys=True)
        )
    client.update_content(
        terminal.LEASE_PATH,
        terminal._text(claimed["state"]),
        terminal.LEASE_BRANCH,
        "lease: claim CFB Step8 terminal registry rebind",
        raw["sha"],
    )
    return str(claimed["result"]["lease_id"])


def _release(client, lease_id):
    raw = client.content(terminal.LEASE_PATH, ref=terminal.LEASE_BRANCH)
    state = terminal.validate_scope_state(terminal._decode(raw))
    holder = next(
        (
            h
            for h in state.get("holders", [])
            if h.get("lease_id") == lease_id and h.get("owner_id") == FINAL_OWNER
        ),
        None,
    )
    if not holder:
        return {"status": "ALREADY_RELEASED"}
    released = terminal.release_scope(
        state,
        owner_id=FINAL_OWNER,
        lease_id=lease_id,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    if released["result"].get("allowed") is not True:
        raise PostmergeRebindFailure("FINAL_REBIND_LEASE_RELEASE_FAILED")
    client.update_content(
        terminal.LEASE_PATH,
        terminal._text(released["state"]),
        terminal.LEASE_BRANCH,
        "lease: release CFB Step8 terminal registry rebind",
        raw["sha"],
    )
    return {"status": "RELEASED"}


def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != FINAL_MAIN_SHA:
        raise PostmergeRebindFailure("FINAL_MAIN_DRIFT")

    ledger = terminal._decode(client.content(terminal.LEDGER_PATH, ref="main"))
    receipt = terminal._decode(
        client.content(terminal.TERMINAL_RECEIPT_PATH, ref=terminal.RECEIPT_BRANCH)
    )
    _, registry = terminal._registry_snapshot(client)
    freeze_entry = dict((registry.get("entries") or {}).get(FINAL_FREEZE_TOKEN) or {})
    validate_closeout_snapshot(ledger, receipt, freeze_entry)
    thaws = sorted(
        str(item.get("thaw_id") or "")
        for item in registry.get("active_thaws", [])
    )

    lease_id = _claim(client, str(registry["state_hash"]))
    released = None
    try:
        final_registry = terminal._rebind(client, FINAL_MAIN_SHA, thaws)
        client.publish_check(
            FINAL_MAIN_SHA,
            "cfb-step8-terminal-freeze",
            "success",
            {
                "title": "CFB Step 8 GREEN + FROZEN",
                "summary": (
                    f"{FINAL_FREEZE_TOKEN}; receipt={TERMINAL_RECEIPT_DIGEST}; "
                    f"registry={final_registry['revision']}:{final_registry['state_hash']}"
                ),
            },
        )
        released = _release(client, lease_id)
        readback = terminal._readback(
            client,
            FINAL_MAIN_SHA,
            receipt,
            final_registry,
            lease_id,
        )
        return {
            "status": "GREEN+FROZEN",
            "step": "8/8",
            "workstream": terminal.WORKSTREAM,
            "final_main_sha": FINAL_MAIN_SHA,
            "terminal_receipt_digest": TERMINAL_RECEIPT_DIGEST,
            "freeze_token": FINAL_FREEZE_TOKEN,
            "final_registry": final_registry,
            "lease_release": released,
            "readback": readback,
            "github_actions_fallback": 0,
            "duplicate_proof_runs": 0,
            "public_browser_recheck": False,
        }
    except Exception:
        if released is None:
            try:
                _release(client, lease_id)
            except Exception:
                pass
        raise


def install_startup(app):
    app.state.cfb_step8_terminal_postmerge_registry_rebind_v1 = {"status": "STARTING"}

    def worker():
        try:
            result = execute(app)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:32000],
                "github_actions_fallback": 0,
                "duplicate_proof_runs": 0,
                "public_browser_recheck": False,
            }
        app.state.cfb_step8_terminal_postmerge_registry_rebind_v1 = result
        print(
            "CFB_STEP8_TERMINAL_POSTMERGE_REGISTRY_REBIND_V1="
            + terminal.json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )

    @app.on_event("startup")
    def _start_postmerge_rebind():
        terminal.Thread(target=worker, daemon=True).start()


install_startup = install_startup
