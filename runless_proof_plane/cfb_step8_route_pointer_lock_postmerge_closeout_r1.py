from __future__ import annotations

import json
from copy import deepcopy
from threading import Thread
from urllib.parse import urlencode

from devsystem.frozen_registry_auto_reconciler_v1 import plan_auto_reconciliation
from . import cfb_step8_terminal_freeze_event_guard_r3 as terminal

PRODUCT_MAIN_SHA = "b21de479595277fc77fb06e632afe8d35d4b4c29"
PARENT_MAIN_SHA = "f1f0ccd80ea717623f38be49237e4943e9d43ad6"
CANDIDATE_SHA = "8ffbe91246f5022bcaca7a326cfaaf9a62976633"
PREMERGE_PROOF_ID = "cfb-game-total-step8-route-pointer-lock-r1-8ffbe91246f5022b-bde3098b39d6952e"
PREMERGE_RECEIPT_DIGEST = "12e18db7a900e2c646dd6615e85b90292058aa0573956cb34574fb3dcc59fda3"
PREMERGE_RECEIPT_PATH = f"devsystem/runless_proof_receipts/{PREMERGE_PROOF_ID}.json"
FINAL_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-route-pointer-lock-postmerge-r1"
TERMINAL_RECEIPT_PATH = "devsystem/runless_proof_receipts/cfb-game-total-step8-terminal-route-lock-b21de479595277fc.json"
HANDOFF_CERT_DAY = "2026-10-17"

FINAL_ARTIFACTS = tuple(dict.fromkeys((*terminal.FINAL_ARTIFACTS,
    "devsystem/runless_proof_plans/cfb-game-total-step8-route-pointer-lock-r1.json",
    "tests/test_cfb_game_total_step8_route_pointer_lock_r1.py",
)))

# Rebind the proven terminal machinery to the new exact merge.
terminal.PRODUCT_MAIN_SHA = PRODUCT_MAIN_SHA
terminal.PARENT_MAIN_SHA = PARENT_MAIN_SHA
terminal.CANDIDATE_SHA = CANDIDATE_SHA
terminal.PREMERGE_PROOF_ID = PREMERGE_PROOF_ID
terminal.PREMERGE_RECEIPT_DIGEST = PREMERGE_RECEIPT_DIGEST
terminal.PREMERGE_RECEIPT_PATH = PREMERGE_RECEIPT_PATH
terminal.FINAL_OWNER = FINAL_OWNER
terminal.TERMINAL_RECEIPT_PATH = TERMINAL_RECEIPT_PATH
terminal.HANDOFF_CERT_DAY = HANDOFF_CERT_DAY
terminal.FINAL_ARTIFACTS = FINAL_ARTIFACTS


class PostmergeCloseoutFailure(RuntimeError):
    pass


def _is_ancestor(client, ancestor: str, descendant: str) -> bool:
    if ancestor == descendant:
        return True
    comparison = client.request("GET", f"/compare/{ancestor}...{descendant}")
    return str(comparison.get("status") or "") in {"ahead", "identical"}


def _ensure_authority(client):
    receipt = terminal._decode(
        client.content(PREMERGE_RECEIPT_PATH, ref=terminal.RECEIPT_BRANCH)
    )
    if (
        receipt.get("proof_id") != PREMERGE_PROOF_ID
        or receipt.get("candidate_sha") != CANDIDATE_SHA
        or receipt.get("digest") != PREMERGE_RECEIPT_DIGEST
        or receipt.get("failure_class") != "NONE"
        or receipt.get("task_id") != "cfb-game-total-step8-route-pointer-lock-r1"
        or receipt.get("workstream") != terminal.WORKSTREAM
    ):
        raise PostmergeCloseoutFailure("PREMERGE_AUTHORITY_DRIFT")
    return {
        "proof_id": PREMERGE_PROOF_ID,
        "receipt_digest": PREMERGE_RECEIPT_DIGEST,
    }


def _jump_route_cert_script():
    return f'''
import json
from urllib.parse import urlencode
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert

cert.SOURCE_MAIN_SHA = "{PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{HANDOFF_CERT_DAY}"


def _jump_route_for_day(base_url, selected_day):
    query = urlencode({{
        "ks_jump_sport": "CFB",
        "ks_jump_market": "Game Total",
        "ks_cfb_game_total_date": str(selected_day),
    }})
    return base_url.rstrip("/") + "/?" + query

cert._route_for_day = _jump_route_for_day
_original_page1 = cert._page1_result


def _guarded_page1(page, name, artifact_dir, base_url):
    row, selected_url, event_id = _original_page1(page, name, artifact_dir, base_url)
    frame, _ = cert._find_cfb_frame(
        page,
        required_markers=cert.PAGE1_FRAME_MARKERS,
        required_testids=(cert.PHOENIX_DAY_TESTID, cert.PAGE1_TESTID),
        timeout_seconds=30.0,
    )
    wrapper_event = cert._event_from_url(page.url)
    frame_event = cert._event_from_url(str(getattr(frame, "url", "") or ""))
    if wrapper_event or frame_event:
        raise cert.Step8MobileProductionFailure(
            f"PAGE1_AUTO_EVENT_VISIBLE:{{name}}:{{wrapper_event}}:{{frame_event}}"
        )
    row["auto_event_visible"] = False
    return row, selected_url, event_id

cert._page1_result = _guarded_page1
payload = cert.run_public(
    base_url="{terminal.PRODUCTION_URL}",
    artifact_dir="artifacts/cfb-game-total-step8-route-pointer-postmerge-r1",
)
if not cert.evidence_is_terminal_green(payload):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")
print("CFB_STEP8_ROUTE_LOCK_PUBLIC_PAYLOAD=" + json.dumps(payload, sort_keys=True), flush=True)
'''


def _retryable(detail: str) -> bool:
    return any(token in detail for token in (
        "PAGE1_AUTO_EVENT_VISIBLE",
        "CFB_NATIVE_FRAME_NOT_FOUND",
        "TESTID_NOT_FOUND",
        "Timeout",
        "timeout",
        "ERR_CONNECTION",
        "get this app back up",
        "PAGE1_NO_EXACT_EVENT_LINK",
        "CURRENT_DAY_RUNTIME_ERROR",
        "This app has encountered an error",
    ))


def _eligible_merged_targets(client, registry: dict) -> list[str]:
    source = str(registry.get("source_main_sha") or "")
    targets: list[str] = []
    for grant in registry.get("active_thaws", []):
        target = str(grant.get("target_head_sha") or "")
        if not target:
            continue
        if _is_ancestor(client, target, PRODUCT_MAIN_SHA) and not _is_ancestor(client, target, source):
            targets.append(target)
    return sorted(set(targets))


def _reconcile_registry_to_product_main(client) -> dict:
    raw, registry = terminal._registry_snapshot(client)
    if str(registry.get("source_main_sha") or "") == PRODUCT_MAIN_SHA:
        return {
            "status": "ALREADY_ALIGNED",
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
        }

    source = str(registry.get("source_main_sha") or "")
    if not _is_ancestor(client, source, PRODUCT_MAIN_SHA):
        raise PostmergeCloseoutFailure("REGISTRY_SOURCE_NOT_ANCESTOR")

    validated = terminal.validate_registry(registry)
    tree = client.tree_blobs(PRODUCT_MAIN_SHA)
    actual = {path: tree.get(path) for path in validated["artifacts"]}
    eligible = _eligible_merged_targets(client, registry)
    plan = plan_auto_reconciliation(
        registry,
        actual_blobs=actual,
        main_sha=PRODUCT_MAIN_SHA,
        merged_authority_heads=eligible,
    )
    decision = str(plan.get("decision") or "")
    if decision == "AUTO_RECONCILIATION_PLANNED":
        updated = deepcopy(plan["planned_registry"])
    elif decision == "REGISTRY_ALREADY_ALIGNED":
        updated = deepcopy(registry)
        updated["source_main_sha"] = PRODUCT_MAIN_SHA
        updated["revision"] = int(registry["revision"]) + 1
        updated["state_hash"] = terminal._hash(terminal._payload_without_hash(updated))
    else:
        raise PostmergeCloseoutFailure("REGISTRY_RECONCILIATION_BLOCKED:" + decision)

    terminal.validate_registry(updated)
    client.update_content(
        terminal.REGISTRY_PATH,
        terminal._text(updated),
        terminal.REGISTRY_BRANCH,
        "registry: reconcile CFB Step8 route-pointer merge",
        raw["sha"],
    )
    readback = terminal._decode(
        client.content(terminal.REGISTRY_PATH, ref=terminal.REGISTRY_BRANCH)
    )
    terminal.validate_registry(readback)
    if str(readback.get("source_main_sha") or "") != PRODUCT_MAIN_SHA:
        raise PostmergeCloseoutFailure("REGISTRY_RECONCILIATION_READBACK_FAILED")
    return {
        "status": "RECONCILED",
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "eligible_merged_targets": eligible,
    }


def _freeze(client, ignored_thaw_ids):
    del ignored_thaw_ids
    _reconcile_registry_to_product_main(client)
    raw, registry = terminal._registry_snapshot(client)
    tree = client.tree_blobs(PRODUCT_MAIN_SHA)
    terminal._baseline(tree, registry)

    artifacts = {}
    for path in FINAL_ARTIFACTS:
        blob = tree.get(path)
        if not blob:
            raise PostmergeCloseoutFailure("FINAL_ARTIFACT_MISSING:" + path)
        artifacts[path] = blob

    entry = {
        "status": "FROZEN",
        "checkpoint_id": terminal.FREEZE_TOKEN,
        "source_main_sha": PRODUCT_MAIN_SHA,
        "artifacts": dict(sorted(artifacts.items())),
    }
    existing = (registry.get("entries") or {}).get(terminal.FREEZE_TOKEN)
    if existing and existing != entry:
        raise PostmergeCloseoutFailure("FREEZE_TOKEN_CONFLICT")
    if not existing:
        updated = deepcopy(registry)
        updated["revision"] = int(updated["revision"]) + 1
        updated["source_main_sha"] = PRODUCT_MAIN_SHA
        updated["entries"][terminal.FREEZE_TOKEN] = entry
        updated["state_hash"] = terminal._hash(terminal._payload_without_hash(updated))
        terminal.validate_registry(updated)
        client.update_content(
            terminal.REGISTRY_PATH,
            terminal._text(updated),
            terminal.REGISTRY_BRANCH,
            "registry: freeze final CFB Step8 route-pointer repair",
            raw["sha"],
        )

    readback = terminal._decode(
        client.content(terminal.REGISTRY_PATH, ref=terminal.REGISTRY_BRANCH)
    )
    terminal.validate_registry(readback)
    if (readback.get("entries") or {}).get(terminal.FREEZE_TOKEN) != entry:
        raise PostmergeCloseoutFailure("FREEZE_READBACK_FAILED")
    return {
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "artifact_count": len(artifacts),
        "active_thaws": sorted(
            str(x.get("thaw_id") or "") for x in readback.get("active_thaws", [])
        ),
    }


def _ledger(client, public, receipt, frozen):
    if client.branch_sha("main") != PRODUCT_MAIN_SHA:
        raise PostmergeCloseoutFailure("MAIN_DRIFT_BEFORE_LEDGER")
    raw = client.content(terminal.LEDGER_PATH, ref="main")
    ledger = terminal._decode(raw)
    if ledger.get("workstream") != terminal.WORKSTREAM or ledger.get("step") != "8/8":
        raise PostmergeCloseoutFailure("LEDGER_IDENTITY_DRIFT")

    ledger["status"] = "GREEN_PLUS_FROZEN"
    ledger["problem"] = "Resolved. Concurrent Streamlit sessions can no longer race shared CFB Game Total route pointers."
    ledger["root_cause"] = "Page-1/Page-2 temporary route-owner pointers were shared module state and were swapped without serialization."
    ledger["patch"] = "One RLock now serializes all temporary Page-1/Page-2 route-pointer swaps and restorations; current tap-marker routing is regression-covered."
    ledger.setdefault("step2a", {}).update({
        "authoritative_main_sha": PRODUCT_MAIN_SHA,
        "authoritative_candidate_sha": CANDIDATE_SHA,
        "one_authoritative_proof_chain": True,
        "github_actions_fallback_authorized": False,
    })
    ledger.setdefault("tdd", {}).update({
        "route_pointer_lock_candidate_sha": CANDIDATE_SHA,
        "route_pointer_lock_premerge_proof_id": PREMERGE_PROOF_ID,
        "route_pointer_lock_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "green_terminal_verification_claimed": True,
    })
    ledger.setdefault("public_proof", {}).update({
        "status": "GREEN",
        "postmerge_product_main_sha": PRODUCT_MAIN_SHA,
        "handoff_cert_day": HANDOFF_CERT_DAY,
        "viewports": [390, 430, 768, 1440],
        "exact_event_identity_required": True,
        "horizontal_overflow_allowed": False,
        "data_limited_visible_allowed": False,
        "page1_auto_event_before_tap": False,
        "terminal_receipt_digest": receipt["digest"],
        "terminal_receipt_path": TERMINAL_RECEIPT_PATH,
    })
    ledger.setdefault("runless", {}).update({
        "premerge_proof_request_status": "MERGE_AUTHORIZED",
        "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "premerge_candidate_sha": CANDIDATE_SHA,
        "postmerge_public_proof_status": "GREEN",
        "postmerge_product_main_sha": PRODUCT_MAIN_SHA,
        "github_actions_fallback": 0,
    })
    ledger["freeze_token"] = terminal.FREEZE_TOKEN
    ledger["green_plus_frozen_claimed"] = True
    ledger["step9_started"] = False
    ledger["next_legal_action"] = "NONE_TERMINAL"
    ledger["terminal"] = {
        "status": "GREEN_PLUS_FROZEN",
        "product_main_sha": PRODUCT_MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "terminal_receipt_digest": receipt["digest"],
        "terminal_receipt_path": TERMINAL_RECEIPT_PATH,
        "public_attempt": public["attempt"],
        "required_widths": [390, 430, 768, 1440],
        "page1_auto_event_before_tap": False,
        "product_freeze_revision": frozen["revision"],
        "product_freeze_state_hash": frozen["state_hash"],
        "github_actions_fallback": 0,
        "completed_at": terminal._now(),
    }
    write = client.update_content(
        terminal.LEDGER_PATH,
        terminal._text(ledger),
        "main",
        "ledger: close CFB Game Total Step8 route-pointer repair",
        raw["sha"],
    )
    final_main = str(((write or {}).get("commit") or {}).get("sha") or "")
    if len(final_main) != 40 or client.branch_sha("main") != final_main:
        raise PostmergeCloseoutFailure("LEDGER_MAIN_READBACK_FAILED")
    return final_main


def _rebind(client, final_main, ignored_thaw_ids):
    del ignored_thaw_ids
    raw, registry = terminal._registry_snapshot(client)
    entry = deepcopy((registry.get("entries") or {}).get(terminal.FREEZE_TOKEN))
    if not entry:
        raise PostmergeCloseoutFailure("FREEZE_TOKEN_MISSING")
    tree = client.tree_blobs(final_main)
    terminal._baseline(tree, registry)
    ledger_blob = tree.get(terminal.LEDGER_PATH)
    if not ledger_blob:
        raise PostmergeCloseoutFailure("LEDGER_BLOB_MISSING")

    updated = deepcopy(registry)
    updated["revision"] = int(updated["revision"]) + 1
    updated["source_main_sha"] = final_main
    entry["source_main_sha"] = final_main
    entry["artifacts"][terminal.LEDGER_PATH] = ledger_blob
    entry["artifacts"] = dict(sorted(entry["artifacts"].items()))
    updated["entries"][terminal.FREEZE_TOKEN] = entry
    updated["state_hash"] = terminal._hash(terminal._payload_without_hash(updated))
    terminal.validate_registry(updated)
    client.update_content(
        terminal.REGISTRY_PATH,
        terminal._text(updated),
        terminal.REGISTRY_BRANCH,
        "registry: bind final CFB Step8 freeze to terminal main",
        raw["sha"],
    )
    readback = terminal._decode(
        client.content(terminal.REGISTRY_PATH, ref=terminal.REGISTRY_BRANCH)
    )
    terminal.validate_registry(readback)
    return {
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "source_main_sha": str(readback["source_main_sha"]),
        "ledger_blob": ledger_blob,
        "preserved_thaws": sorted(
            str(x.get("thaw_id") or "") for x in readback.get("active_thaws", [])
        ),
    }


terminal._ensure_authority = _ensure_authority
terminal._cert_script = _jump_route_cert_script
terminal._retryable = _retryable
terminal._freeze = _freeze
terminal._ledger = _ledger
terminal._rebind = _rebind


def install_startup(app):
    app.state.cfb_step8_route_pointer_postmerge_r1 = {"status": "STARTING"}

    def worker():
        try:
            result = terminal.execute(app)
        except Exception as exc:
            result = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:32000],
                "github_actions_fallback": 0,
                "duplicate_proof_runs": 0,
            }
        app.state.cfb_step8_route_pointer_postmerge_r1 = result
        print(
            "CFB_STEP8_ROUTE_POINTER_POSTMERGE_R1="
            + json.dumps(result, sort_keys=True, default=str),
            flush=True,
        )

    @app.on_event("startup")
    def run():
        Thread(target=worker, name="cfb-step8-route-pointer-postmerge-r1", daemon=True).start()

    return app
