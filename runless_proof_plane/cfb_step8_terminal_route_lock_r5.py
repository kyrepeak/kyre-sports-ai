from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlencode

from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.frozen_registry_auto_reconciler_v1 import plan_auto_reconciliation
from devsystem.scope_aware_execution_lease_v1 import release_scope

from . import cfb_step8_terminal_freeze_event_guard_r3 as terminal

PRODUCT_MAIN_SHA = "b21de479595277fc77fb06e632afe8d35d4b4c29"
PARENT_MAIN_SHA = "f1f0ccd80ea717623f38be49237e4943e9d43ad6"
CANDIDATE_SHA = "8ffbe91246f5022bcaca7a326cfaaf9a62976633"
PREMERGE_PROOF_ID = "cfb-game-total-step8-route-pointer-lock-r1-8ffbe91246f5022b-bde3098b39d6952e"
PREMERGE_RECEIPT_DIGEST = "12e18db7a900e2c646dd6615e85b90292058aa0573956cb34574fb3dcc59fda3"
PREMERGE_RECEIPT_PATH = f"devsystem/runless_proof_receipts/{PREMERGE_PROOF_ID}.json"
HANDOFF_CERT_DAY = "2026-10-17"
PREMERGE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-route-pointer-lock-r1"
ROUTE_THAW_ID = "THAW-CFB-GT-STEP8-ROUTE-POINTER-LOCK-R1"
ROUTER_PATH = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-step8-route-pointer-lock-r1.json"
TEST_PATH = "tests/test_cfb_game_total_step8_route_pointer_lock_r1.py"

# Rebind the frozen terminal engine to the exact merged concurrency-repair authority.
terminal.PRODUCT_MAIN_SHA = PRODUCT_MAIN_SHA
terminal.PARENT_MAIN_SHA = PARENT_MAIN_SHA
terminal.CANDIDATE_SHA = CANDIDATE_SHA
terminal.PREMERGE_PROOF_ID = PREMERGE_PROOF_ID
terminal.PREMERGE_RECEIPT_DIGEST = PREMERGE_RECEIPT_DIGEST
terminal.PREMERGE_RECEIPT_PATH = PREMERGE_RECEIPT_PATH
terminal.HANDOFF_CERT_DAY = HANDOFF_CERT_DAY
terminal.TERMINAL_RECEIPT_PATH = (
    f"devsystem/runless_proof_receipts/cfb-game-total-step8-terminal-r5-{PRODUCT_MAIN_SHA[:16]}.json"
)
terminal.FINAL_ARTIFACTS = tuple(dict.fromkeys((
    *terminal.FINAL_ARTIFACTS,
    PLAN_PATH,
    TEST_PATH,
)))


def _merged_candidate_is_exact(client) -> None:
    if client.branch_sha("main") != PRODUCT_MAIN_SHA:
        raise terminal.TerminalFreezeFailure("R5_MAIN_DRIFT")
    parents = {str(p.get("sha") or "") for p in client.commit(PRODUCT_MAIN_SHA).get("parents", [])}
    if CANDIDATE_SHA not in parents or PARENT_MAIN_SHA not in parents:
        raise terminal.TerminalFreezeFailure("R5_MERGE_PARENT_DRIFT")


def _verified_premerge_authority(client):
    receipt = terminal._decode(
        client.content(PREMERGE_RECEIPT_PATH, ref=terminal.RECEIPT_BRANCH)
    )
    if (
        receipt.get("proof_id") != PREMERGE_PROOF_ID
        or receipt.get("candidate_sha") != CANDIDATE_SHA
        or receipt.get("digest") != PREMERGE_RECEIPT_DIGEST
        or receipt.get("failure_class") != "NONE"
        or receipt.get("workstream") != terminal.WORKSTREAM
    ):
        raise terminal.TerminalFreezeFailure("R5_PREMERGE_AUTHORITY_DRIFT")
    return {
        "proof_id": PREMERGE_PROOF_ID,
        "receipt_digest": PREMERGE_RECEIPT_DIGEST,
    }


def _release_merged_premerge_lease(client) -> dict:
    _merged_candidate_is_exact(client)
    raw = client.content(terminal.LEASE_PATH, ref=terminal.LEASE_BRANCH)
    state = terminal.validate_scope_state(terminal._decode(raw))
    owned = [h for h in state.get("holders", []) if h.get("owner_id") == PREMERGE_OWNER]
    if not owned:
        return {"status": "ALREADY_RELEASED", "revision": state["revision"], "state_hash": state["state_hash"]}
    if len(owned) != 1:
        raise terminal.TerminalFreezeFailure("R5_PREMERGE_LEASE_NOT_UNIQUE")
    holder = owned[0]
    scope = holder.get("scope") or {}
    deps = set(scope.get("dependency_tokens") or [])
    identity = scope.get("resource_identity") or {}
    if (
        f"candidate:{CANDIDATE_SHA}" not in deps
        or "cfb:game-total:step8" not in deps
        or identity.get("main_sha") != PARENT_MAIN_SHA
    ):
        raise terminal.TerminalFreezeFailure("R5_PREMERGE_LEASE_IDENTITY_DRIFT")
    released = release_scope(
        state,
        owner_id=PREMERGE_OWNER,
        lease_id=str(holder.get("lease_id") or ""),
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    if released["result"].get("allowed") is not True:
        raise terminal.TerminalFreezeFailure(
            "R5_PREMERGE_LEASE_RELEASE_FAILED:" + str(released["result"])
        )
    client.update_content(
        terminal.LEASE_PATH,
        terminal._text(released["state"]),
        terminal.LEASE_BRANCH,
        "lease: hand off merged CFB Step8 premerge owner to terminal finalizer",
        raw["sha"],
    )
    check = terminal.validate_scope_state(
        terminal._decode(client.content(terminal.LEASE_PATH, ref=terminal.LEASE_BRANCH))
    )
    if any(h.get("owner_id") == PREMERGE_OWNER for h in check.get("holders", [])):
        raise terminal.TerminalFreezeFailure("R5_PREMERGE_LEASE_RELEASE_READBACK_FAILED")
    return {"status": "RELEASED", "revision": check["revision"], "state_hash": check["state_hash"]}


def _reconcile_merged_route_thaw(client) -> dict:
    _merged_candidate_is_exact(client)
    raw, registry = terminal._registry_snapshot(client)
    checked = validate_registry(registry)
    tree = client.tree_blobs(PRODUCT_MAIN_SHA)
    actual = {path: tree.get(path) for path in checked["artifacts"]}
    router_blob = tree.get(ROUTER_PATH)
    if not router_blob:
        raise terminal.TerminalFreezeFailure("R5_ROUTER_BLOB_MISSING")

    route_grants = [
        grant for grant in registry.get("active_thaws", [])
        if grant.get("thaw_id") == ROUTE_THAW_ID
    ]
    already_aligned = (
        checked["artifacts"].get(ROUTER_PATH) == router_blob
        and str(registry.get("source_main_sha") or "") == PRODUCT_MAIN_SHA
        and not route_grants
    )
    if already_aligned:
        return {
            "status": "ALREADY_RECONCILED",
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
        }

    if len(route_grants) != 1 or route_grants[0].get("target_head_sha") != CANDIDATE_SHA:
        raise terminal.TerminalFreezeFailure("R5_ROUTE_THAW_IDENTITY_DRIFT")

    plan = plan_auto_reconciliation(
        registry,
        actual_blobs=actual,
        main_sha=PRODUCT_MAIN_SHA,
        merged_authority_heads=[CANDIDATE_SHA],
    )
    if plan.get("decision") != "AUTO_RECONCILIATION_PLANNED" or plan.get("apply_allowed") is not True:
        raise terminal.TerminalFreezeFailure(
            "R5_REGISTRY_RECONCILIATION_BLOCKED:" + str(plan.get("decision"))
        )
    updated = deepcopy(plan["planned_registry"])
    validate_registry(updated)
    client.update_content(
        terminal.REGISTRY_PATH,
        terminal._text(updated),
        terminal.REGISTRY_BRANCH,
        "registry: reconcile merged CFB Step8 route-pointer repair",
        raw["sha"],
    )
    readback = terminal._decode(
        client.content(terminal.REGISTRY_PATH, ref=terminal.REGISTRY_BRANCH)
    )
    validated = validate_registry(readback)
    if str(readback.get("source_main_sha") or "") != PRODUCT_MAIN_SHA:
        raise terminal.TerminalFreezeFailure("R5_REGISTRY_MAIN_READBACK_FAILED")
    if validated["artifacts"].get(ROUTER_PATH) != router_blob:
        raise terminal.TerminalFreezeFailure("R5_ROUTER_BASELINE_READBACK_FAILED")
    if any(g.get("thaw_id") == ROUTE_THAW_ID for g in readback.get("active_thaws", [])):
        raise terminal.TerminalFreezeFailure("R5_ROUTE_THAW_NOT_RETIRED")
    return {
        "status": "RECONCILED",
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "retired_thaw": ROUTE_THAW_ID,
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
    artifact_dir="artifacts/cfb-game-total-step8-terminal-r5",
)
if not cert.evidence_is_terminal_green(payload):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")
print("CFB_STEP8_R5_PUBLIC_PAYLOAD=" + json.dumps(payload, sort_keys=True), flush=True)
'''


def _public_once_r5(client):
    token = client.auth.installation_token()
    with terminal.CandidateWorkspace(terminal._repo_url(client), PRODUCT_MAIN_SHA, token=token) as workspace:
        script = terminal.Path(workspace.path) / ".cfb_step8_terminal_r5.py"
        script.write_text(_jump_route_cert_script(), encoding="utf-8")
        cp = terminal.subprocess.run(
            [terminal.sys.executable, str(script)],
            cwd=str(workspace.path),
            text=True,
            capture_output=True,
            timeout=1100,
        )
        combined = (cp.stdout or "") + "\n" + (cp.stderr or "")
        if cp.returncode:
            raise terminal.TerminalFreezeFailure("PUBLIC_CERT_FAILED:" + combined[-24000:])
        prefix = "CFB_STEP8_R5_PUBLIC_PAYLOAD="
        lines = [x for x in (cp.stdout or "").splitlines() if x.startswith(prefix)]
        if len(lines) != 1:
            raise terminal.TerminalFreezeFailure("PUBLIC_PAYLOAD_MISSING:" + combined[-12000:])
        payload = terminal.json.loads(lines[0][len(prefix):])
        if payload.get("status") != "GREEN" or payload.get("source_main_sha") != PRODUCT_MAIN_SHA:
            raise terminal.TerminalFreezeFailure("PUBLIC_IDENTITY_DRIFT")
        if payload.get("handoff_cert_day") != HANDOFF_CERT_DAY:
            raise terminal.TerminalFreezeFailure("PUBLIC_DAY_DRIFT")
        if set((payload.get("viewports") or {}).keys()) != {"mobile390", "mobile430", "tablet", "desktop"}:
            raise terminal.TerminalFreezeFailure("PUBLIC_VIEWPORT_DRIFT")
        for name, row in payload["viewports"].items():
            if (row.get("page1") or {}).get("auto_event_visible") is not False:
                raise terminal.TerminalFreezeFailure("PUBLIC_AUTO_EVENT_NOT_PROVEN:" + name)
        return payload


def _public_r5(client):
    # One authoritative public certification. Fail closed; do not poll/retry the same state.
    payload = _public_once_r5(client)
    return {
        "status": "GREEN",
        "attempt": 1,
        "product_main_sha": PRODUCT_MAIN_SHA,
        "handoff_cert_day": HANDOFF_CERT_DAY,
        "required_widths": [390, 430, 768, 1440],
        "evidence": payload,
    }


def _ledger_r5(client, public, receipt, frozen):
    if client.branch_sha("main") != PRODUCT_MAIN_SHA:
        raise terminal.TerminalFreezeFailure("MAIN_DRIFT_BEFORE_LEDGER")
    raw = client.content(terminal.LEDGER_PATH, ref="main")
    led = terminal._decode(raw)
    if led.get("workstream") != terminal.WORKSTREAM or led.get("step") != "8/8":
        raise terminal.TerminalFreezeFailure("LEDGER_IDENTITY_DRIFT")

    led["status"] = "GREEN_PLUS_FROZEN"
    led["problem"] = "Resolved. Shared CFB Game Total Page-1/Page-2 route-pointer swaps are serialized and production-certified."
    led["root_cause"] = "Overlapping Streamlit sessions could mutate and restore shared module-level route owners concurrently, intermittently hiding the Page-1 selector or surfacing runtime errors."
    led["patch"] = "An RLock now serializes temporary Page-1 and Page-2 route-owner swaps; exact tap-marker runtime coverage verifies lock ownership and restoration."
    led.setdefault("step2a", {}).update({
        "authoritative_main_sha": PRODUCT_MAIN_SHA,
        "one_authoritative_proof_chain": True,
        "github_actions_fallback_authorized": False,
    })
    led.setdefault("tdd", {}).update({
        "route_pointer_lock_candidate_sha": CANDIDATE_SHA,
        "route_pointer_lock_premerge_proof_id": PREMERGE_PROOF_ID,
        "route_pointer_lock_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "green_terminal_verification_claimed": True,
    })
    led.setdefault("public_proof", {}).update({
        "status": "GREEN",
        "postmerge_product_main_sha": PRODUCT_MAIN_SHA,
        "handoff_cert_day": HANDOFF_CERT_DAY,
        "viewports": [390, 430, 768, 1440],
        "current_phoenix_day_proof_separate": True,
        "exact_event_identity_required": True,
        "horizontal_overflow_allowed": False,
        "data_limited_visible_allowed": False,
        "page1_auto_event_before_tap": False,
        "terminal_receipt_digest": receipt["digest"],
        "terminal_receipt_path": terminal.TERMINAL_RECEIPT_PATH,
    })
    led.setdefault("runless", {}).update({
        "premerge_proof_request_status": "MERGE_AUTHORIZED",
        "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "premerge_candidate_sha": CANDIDATE_SHA,
        "postmerge_public_proof_status": "GREEN",
        "postmerge_product_main_sha": PRODUCT_MAIN_SHA,
        "github_actions_fallback": 0,
    })
    led["freeze_token"] = terminal.FREEZE_TOKEN
    led["green_plus_frozen_claimed"] = True
    led["step9_started"] = False
    led["next_legal_action"] = "NONE_TERMINAL"
    led["terminal"] = {
        "status": "GREEN_PLUS_FROZEN",
        "product_main_sha": PRODUCT_MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "terminal_receipt_digest": receipt["digest"],
        "terminal_receipt_path": terminal.TERMINAL_RECEIPT_PATH,
        "public_attempt": public["attempt"],
        "required_widths": [390, 430, 768, 1440],
        "page1_auto_event_before_tap": False,
        "route_pointer_lock": True,
        "product_freeze_revision": frozen["revision"],
        "product_freeze_state_hash": frozen["state_hash"],
        "github_actions_fallback": 0,
        "completed_at": terminal._now(),
    }
    write = client.update_content(
        terminal.LEDGER_PATH,
        terminal._text(led),
        "main",
        "ledger: close CFB Game Total Step8 route-pointer repair GREEN + FROZEN",
        raw["sha"],
    )
    final_main = str(((write or {}).get("commit") or {}).get("sha") or "")
    if len(final_main) != 40 or client.branch_sha("main") != final_main:
        raise terminal.TerminalFreezeFailure("LEDGER_MAIN_READBACK_FAILED")
    return final_main


_original_execute = terminal.execute


def _execute_r5(app):
    client = app.state.github_client
    _merged_candidate_is_exact(client)
    handoff = _release_merged_premerge_lease(client)
    reconciliation = _reconcile_merged_route_thaw(client)
    result = _original_execute(app)
    result["premerge_lease_handoff"] = handoff
    result["merged_thaw_reconciliation"] = reconciliation
    return result


terminal._ensure_authority = _verified_premerge_authority
terminal._cert_script = _jump_route_cert_script
terminal._public_once = _public_once_r5
terminal._public = _public_r5
terminal._ledger = _ledger_r5
terminal.execute = _execute_r5
install_startup = terminal.install_startup
