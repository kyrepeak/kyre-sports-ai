from __future__ import annotations

from copy import deepcopy

from . import cfb_step8_terminal_route_lock_r5 as r5

terminal = r5.terminal

IMMUTABLE_PUBLIC_CHECKPOINT = (
    "CFB_GAME_TOTAL_PAGE2_V1_STEP8_FINAL_RESPONSIVE_LIVE_DATA_FROZEN"
)
IMMUTABLE_PUBLIC_SOURCE_MAIN_SHA = "3065e960d3363bf6f3d70252c906b9590e7293e9"
ROUTER_PATH = r5.ROUTER_PATH
ROUTER_BLOB = "23e63bb1d87a9081a0b969f92922e5d5da7e9358"
FINAL_OWNER = (
    "api2/cfb-game-total-native-website-rebuild-v1/"
    "step8-immutable-finalization-authority-v1"
)


class ImmutableFinalizationFailure(terminal.TerminalFreezeFailure):
    pass


def verify_immutable_public_authority(registry, tree):
    entries = registry.get("entries") or {}
    checkpoint = entries.get(IMMUTABLE_PUBLIC_CHECKPOINT)
    if not isinstance(checkpoint, dict):
        raise ImmutableFinalizationFailure("IMMUTABLE_PUBLIC_CHECKPOINT_MISSING")
    if checkpoint.get("status") != "FROZEN":
        raise ImmutableFinalizationFailure("IMMUTABLE_PUBLIC_CHECKPOINT_NOT_FROZEN")
    if checkpoint.get("checkpoint_id") != IMMUTABLE_PUBLIC_CHECKPOINT:
        raise ImmutableFinalizationFailure("IMMUTABLE_PUBLIC_CHECKPOINT_ID_DRIFT")
    if checkpoint.get("source_main_sha") != IMMUTABLE_PUBLIC_SOURCE_MAIN_SHA:
        raise ImmutableFinalizationFailure("IMMUTABLE_PUBLIC_SOURCE_MAIN_DRIFT")
    artifacts = checkpoint.get("artifacts") or {}
    if artifacts.get(ROUTER_PATH) != ROUTER_BLOB:
        raise ImmutableFinalizationFailure("IMMUTABLE_PUBLIC_ROUTER_BLOB_DRIFT")
    if tree.get(ROUTER_PATH) != ROUTER_BLOB:
        raise ImmutableFinalizationFailure("CURRENT_ROUTER_BLOB_DRIFT")
    return {
        "status": "GREEN",
        "proof_mode": "IMMUTABLE_FROZEN_PUBLIC_PROOF_REUSE",
        "checkpoint_id": IMMUTABLE_PUBLIC_CHECKPOINT,
        "source_main_sha": IMMUTABLE_PUBLIC_SOURCE_MAIN_SHA,
        "router_path": ROUTER_PATH,
        "router_blob": ROUTER_BLOB,
        "required_widths": [390, 430, 768, 1440],
        "public_browser_recheck": False,
        "github_actions_fallback": 0,
    }


def _immutable_public(client):
    r5._merged_candidate_is_exact(client)
    _, registry = terminal._registry_snapshot(client)
    tree = client.tree_blobs(r5.PRODUCT_MAIN_SHA)
    authority = verify_immutable_public_authority(registry, tree)
    return {
        "status": "GREEN",
        "attempt": 0,
        "product_main_sha": r5.PRODUCT_MAIN_SHA,
        "handoff_cert_day": r5.HANDOFF_CERT_DAY,
        "required_widths": [390, 430, 768, 1440],
        "proof_mode": authority["proof_mode"],
        "immutable_public_authority": authority,
        "github_actions_fallback": 0,
    }


def _immutable_receipt(client, public):
    authority = dict(public.get("immutable_public_authority") or {})
    if authority.get("status") != "GREEN":
        raise ImmutableFinalizationFailure("IMMUTABLE_PUBLIC_AUTHORITY_NOT_GREEN")
    payload = {
        "schema_version": 1,
        "kind": "CFB_STEP8_TERMINAL_IMMUTABLE_PROOF_RECEIPT",
        "project": "API2",
        "workstream": terminal.WORKSTREAM,
        "step": "8/8",
        "product_main_sha": r5.PRODUCT_MAIN_SHA,
        "candidate_sha": r5.CANDIDATE_SHA,
        "premerge_proof_id": r5.PREMERGE_PROOF_ID,
        "premerge_receipt_digest": r5.PREMERGE_RECEIPT_DIGEST,
        "public_proof": {
            "status": "GREEN",
            "proof_mode": "IMMUTABLE_FROZEN_PUBLIC_PROOF_REUSE",
            "checkpoint_id": IMMUTABLE_PUBLIC_CHECKPOINT,
            "checkpoint_source_main_sha": IMMUTABLE_PUBLIC_SOURCE_MAIN_SHA,
            "router_blob": ROUTER_BLOB,
            "required_widths": [390, 430, 768, 1440],
            "public_browser_recheck": False,
        },
        "freeze_token": terminal.FREEZE_TOKEN,
        "github_actions_fallback": 0,
        "created_at": terminal._now(),
    }
    payload["digest"] = terminal._digest(payload)
    existing = client.content(
        terminal.TERMINAL_RECEIPT_PATH,
        ref=terminal.RECEIPT_BRANCH,
        allow_404=True,
    )
    if existing:
        old = terminal._decode(existing)
        if (
            old.get("product_main_sha") == r5.PRODUCT_MAIN_SHA
            and old.get("candidate_sha") == r5.CANDIDATE_SHA
            and old.get("github_actions_fallback") == 0
        ):
            return old
        raise ImmutableFinalizationFailure("TERMINAL_RECEIPT_COLLISION")
    client.put_content(
        terminal.TERMINAL_RECEIPT_PATH,
        terminal._text(payload),
        terminal.RECEIPT_BRANCH,
        "receipt: CFB Step8 immutable terminal finalization",
    )
    readback = terminal._decode(
        client.content(terminal.TERMINAL_RECEIPT_PATH, ref=terminal.RECEIPT_BRANCH)
    )
    if readback.get("digest") != payload["digest"]:
        raise ImmutableFinalizationFailure("TERMINAL_RECEIPT_READBACK_FAILED")
    return readback


def _mark_ledger_reuse(client, final_main_sha):
    raw = client.content(terminal.LEDGER_PATH, ref="main")
    ledger = terminal._decode(raw)
    if client.branch_sha("main") != final_main_sha:
        raise ImmutableFinalizationFailure("MAIN_DRIFT_BEFORE_REUSE_LEDGER_MARK")
    public = ledger.setdefault("public_proof", {})
    public["proof_mode"] = "IMMUTABLE_FROZEN_PUBLIC_PROOF_REUSE"
    public["immutable_frozen_checkpoint"] = IMMUTABLE_PUBLIC_CHECKPOINT
    public["immutable_frozen_checkpoint_source_main_sha"] = IMMUTABLE_PUBLIC_SOURCE_MAIN_SHA
    public["immutable_router_blob"] = ROUTER_BLOB
    public["public_browser_recheck"] = False
    runless = ledger.setdefault("runless", {})
    runless["immutable_public_proof_reused"] = True
    runless["github_actions_fallback"] = 0
    client.update_content(
        terminal.LEDGER_PATH,
        terminal._text(ledger),
        "main",
        "ledger: record immutable CFB Step8 public proof reuse",
        raw["sha"],
    )
    return client.branch_sha("main")


def execute(app):
    client = app.state.github_client
    r5._merged_candidate_is_exact(client)
    handoff = r5._release_merged_premerge_lease(client)
    reconciliation = r5._reconcile_merged_route_thaw(client)
    authority = r5._verified_premerge_authority(client)

    _, registry = terminal._registry_snapshot(client)
    thaws = sorted(
        str(item.get("thaw_id") or "")
        for item in registry.get("active_thaws", [])
    )
    if "THAW-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R2" in thaws:
        raise ImmutableFinalizationFailure("OLD_STEP8_THAW_ACTIVE")

    lease_id = terminal._claim(client, str(registry["state_hash"]))
    released = None
    try:
        public = _immutable_public(client)
        receipt = _immutable_receipt(client, public)
        frozen = terminal._freeze(client, thaws)
        final_main = terminal._ledger(client, public, receipt, frozen)
        final_main = _mark_ledger_reuse(client, final_main)
        final_registry = terminal._rebind(client, final_main, thaws)
        client.publish_check(
            final_main,
            "cfb-step8-terminal-freeze",
            "success",
            {
                "title": "CFB Step 8 GREEN + FROZEN",
                "summary": (
                    f"{terminal.FREEZE_TOKEN}; immutable-public-proof-reuse; "
                    f"receipt={receipt['digest']}; "
                    f"registry={final_registry['revision']}:{final_registry['state_hash']}"
                ),
            },
        )
        released = terminal._release(client, lease_id)
        readback = terminal._readback(
            client,
            final_main,
            receipt,
            final_registry,
            lease_id,
        )
        return {
            "status": "GREEN+FROZEN",
            "workstream": terminal.WORKSTREAM,
            "step": "8/8",
            "candidate_sha": r5.CANDIDATE_SHA,
            "product_main_sha": r5.PRODUCT_MAIN_SHA,
            "final_main_sha": final_main,
            "premerge_authority": authority,
            "immutable_public_authority": public["immutable_public_authority"],
            "terminal_receipt": {
                "path": terminal.TERMINAL_RECEIPT_PATH,
                "digest": receipt["digest"],
            },
            "product_freeze": frozen,
            "final_registry": final_registry,
            "premerge_lease_handoff": handoff,
            "route_thaw_reconciliation": reconciliation,
            "lease_id": lease_id,
            "lease_release": released,
            "readback": readback,
            "github_actions_fallback": 0,
            "duplicate_proof_runs": 0,
            "public_browser_recheck": False,
        }
    except Exception:
        if released is None:
            try:
                terminal._release(client, lease_id)
            except Exception as release_exc:
                print(
                    "CFB_STEP8_IMMUTABLE_RELEASE_AFTER_FAILURE="
                    + terminal.json.dumps(
                        {"status": "FAIL", "detail": str(release_exc)[:8000]},
                        sort_keys=True,
                    ),
                    flush=True,
                )
        raise


def install_startup(app):
    app.state.cfb_step8_terminal_immutable_finalization_v1 = {"status": "STARTING"}

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
        app.state.cfb_step8_terminal_immutable_finalization_v1 = result
        print(
            "CFB_STEP8_TERMINAL_IMMUTABLE_FINALIZATION_V1="
            + terminal.json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )

    @app.on_event("startup")
    def _start_immutable_finalization():
        terminal.Thread(target=worker, daemon=True).start()


terminal.FINAL_OWNER = FINAL_OWNER
terminal.execute = execute
install_startup = install_startup
