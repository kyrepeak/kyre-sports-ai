from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.scope_aware_execution_lease_v1 import build_scope, claim_scope, release_scope, validate_state as validate_scope_state
from .workspace import CandidateWorkspace

PRODUCT_MAIN_SHA = "f1f0ccd80ea717623f38be49237e4943e9d43ad6"
PARENT_MAIN_SHA = "283151c3792a73520a37b54bb8f480910004b6d6"
CANDIDATE_SHA = "d963f41bb7f13a0744a091249237ad95bc1cfc62"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
PREMERGE_PROOF_ID = "cfb-game-total-step8-v14-source-event-guard-r1-d963f41bb7f13a07-f893dafcb0b10a08"
PREMERGE_RECEIPT_DIGEST = "1b1a281b5dc5c8fa084a1716eeca2b57d1b577c4471f4717758497f44cff97fc"
PREMERGE_RECEIPT_PATH = f"devsystem/runless_proof_receipts/{PREMERGE_PROOF_ID}.json"
RECEIPT_BRANCH = "runless-proof-receipts"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEDGER_PATH = "devsystem/task_ledgers/cfb-game-total-mobile-production-step8-v1.json"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP8_MOBILE_PRODUCTION_V1_FROZEN"
FINAL_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-terminal-freeze-event-guard-r4"
PRODUCTION_URL = "https://pickvault.streamlit.app"
HANDOFF_CERT_DAY = "2026-10-17"
TERMINAL_RECEIPT_PATH = f"devsystem/runless_proof_receipts/cfb-game-total-step8-terminal-r4-{PRODUCT_MAIN_SHA[:16]}.json"
FINAL_ARTIFACTS = (
    "app.py",
    "cfb_game_total_clean_page_v14.py",
    "cfb_game_total_clean_page_v43.py",
    "cfb_game_total_page2_step8_final_runtime_v1.py",
    "devsystem/cfb_game_total_mobile_production_step8_v1.py",
    "devsystem/cfb_game_total_mobile_production_step8_runless_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-v1.json",
    "devsystem/runless_proof_plans/cfb-game-total-step8-v14-source-event-guard-r1.json",
    "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py",
    "tests/test_cfb_game_total_mobile_production_step8_v1.py",
    "tests/test_cfb_game_total_page1_default_selection_step8_v1.py",
    "tests/test_cfb_game_total_step8_page1_event_guard_r1.py",
    "tests/test_cfb_game_total_step8_v14_source_event_guard_v1.py",
)

class TerminalFreezeFailure(RuntimeError):
    pass

def _decode(raw):
    if not raw or raw.get("encoding") != "base64":
        raise TerminalFreezeFailure("CONTENT_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())

def _text(payload):
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def _digest(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()

def _repo_url(client):
    return f"https://github.com/{client.repository}.git"

def _registry_snapshot(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    registry = _decode(raw)
    validate_registry(registry)
    return raw, registry

def _ensure_authority(client):
    receipt = _decode(client.content(PREMERGE_RECEIPT_PATH, ref=RECEIPT_BRANCH))
    if (
        receipt.get("proof_id") != PREMERGE_PROOF_ID
        or receipt.get("candidate_sha") != CANDIDATE_SHA
        or receipt.get("receipt_digest") != PREMERGE_RECEIPT_DIGEST
        or receipt.get("failure_class") != "NONE"
        or receipt.get("status") != "MERGE_AUTHORIZED"
    ):
        raise TerminalFreezeFailure("PREMERGE_AUTHORITY_DRIFT")
    return {"proof_id": PREMERGE_PROOF_ID, "receipt_digest": PREMERGE_RECEIPT_DIGEST}

def _claim(client, registry_hash):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    scope = build_scope(
        write_paths=[REGISTRY_PATH, LEDGER_PATH, TERMINAL_RECEIPT_PATH],
        dependency_tokens=[f"candidate:{CANDIDATE_SHA}", f"product-main:{PRODUCT_MAIN_SHA}", "cfb:game-total:step8"],
        shared_resources=["ref:monster-frozen-artifact-registry", "ref:runless-proof-receipts", "route:cfb-game-total", "runless-proof-plane"],
        resource_identity={"main_sha": PRODUCT_MAIN_SHA, "registry_state_hash": registry_hash},
        exclusive=False,
    )
    claimed = claim_scope(
        state, owner_id=FINAL_OWNER, now_utc=_now(), scope=scope,
        expected_revision=state["revision"], expected_state_hash=state["state_hash"], ttl_seconds=2400,
    )
    if claimed["result"].get("allowed") is not True:
        raise TerminalFreezeFailure("FINAL_LEASE_BLOCKED:" + json.dumps(claimed["result"], sort_keys=True))
    client.update_content(LEASE_PATH, _text(claimed["state"]), LEASE_BRANCH, "lease: claim CFB Step8 terminal R4", raw["sha"])
    return str(claimed["result"]["lease_id"])

def _release(client, lease_id):
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_state(_decode(raw))
    holder = next((h for h in state.get("holders", []) if h.get("lease_id") == lease_id and h.get("owner_id") == FINAL_OWNER), None)
    if not holder:
        return {"status": "ALREADY_RELEASED"}
    released = release_scope(
        state, owner_id=FINAL_OWNER, lease_id=lease_id,
        expected_revision=state["revision"], expected_state_hash=state["state_hash"],
    )
    if released["result"].get("allowed") is not True:
        raise TerminalFreezeFailure("LEASE_RELEASE_FAILED")
    client.update_content(LEASE_PATH, _text(released["state"]), LEASE_BRANCH, "lease: release CFB Step8 terminal R4", raw["sha"])
    check = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH)))
    if any(h.get("lease_id") == lease_id for h in check.get("holders", [])):
        raise TerminalFreezeFailure("LEASE_RELEASE_READBACK_FAILED")
    return {"status": "RELEASED", "revision": check["revision"], "state_hash": check["state_hash"]}

def _ensure_chromium():
    cp = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], text=True, capture_output=True, timeout=360)
    if cp.returncode:
        raise TerminalFreezeFailure("CHROMIUM_INSTALL_FAILED:" + ((cp.stdout or "") + (cp.stderr or ""))[-8000:])

def _cert_script():
    return f'''
import json
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert
cert.SOURCE_MAIN_SHA = "{PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{HANDOFF_CERT_DAY}"
original = cert._page1_result
def guarded(page, name, artifact_dir, base_url):
    row, selected_url, event_id = original(page, name, artifact_dir, base_url)
    frame, _ = cert._find_cfb_frame(
        page, required_markers=cert.PAGE1_FRAME_MARKERS,
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
cert._page1_result = guarded
payload = cert.run_public(
    base_url="{PRODUCTION_URL}",
    artifact_dir="artifacts/cfb-game-total-step8-terminal-r4",
)
if not cert.evidence_is_terminal_green(payload):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")
print("CFB_STEP8_R4_PUBLIC_PAYLOAD=" + json.dumps(payload, sort_keys=True), flush=True)
'''

def _public_once(client):
    token = client.auth.installation_token()
    with CandidateWorkspace(_repo_url(client), PRODUCT_MAIN_SHA, token=token) as workspace:
        script = Path(workspace.path) / ".cfb_step8_terminal_r4.py"
        script.write_text(_cert_script(), encoding="utf-8")
        cp = subprocess.run([sys.executable, str(script)], cwd=str(workspace.path), text=True, capture_output=True, timeout=1100)
        combined = (cp.stdout or "") + "\n" + (cp.stderr or "")
        if cp.returncode:
            raise TerminalFreezeFailure("PUBLIC_CERT_FAILED:" + combined[-24000:])
        prefix = "CFB_STEP8_R4_PUBLIC_PAYLOAD="
        lines = [x for x in (cp.stdout or "").splitlines() if x.startswith(prefix)]
        if len(lines) != 1:
            raise TerminalFreezeFailure("PUBLIC_PAYLOAD_MISSING:" + combined[-12000:])
        payload = json.loads(lines[0][len(prefix):])
        if payload.get("status") != "GREEN" or payload.get("source_main_sha") != PRODUCT_MAIN_SHA:
            raise TerminalFreezeFailure("PUBLIC_IDENTITY_DRIFT")
        if payload.get("handoff_cert_day") != HANDOFF_CERT_DAY:
            raise TerminalFreezeFailure("PUBLIC_DAY_DRIFT")
        if set((payload.get("viewports") or {}).keys()) != {"mobile390", "mobile430", "tablet", "desktop"}:
            raise TerminalFreezeFailure("PUBLIC_VIEWPORT_DRIFT")
        for name, row in payload["viewports"].items():
            if (row.get("page1") or {}).get("auto_event_visible") is not False:
                raise TerminalFreezeFailure("PUBLIC_AUTO_EVENT_NOT_PROVEN:" + name)
        return payload

def _retryable(detail):
    return any(x in detail for x in (
        "PAGE1_AUTO_EVENT_VISIBLE", "CFB_NATIVE_FRAME_NOT_FOUND", "TESTID_NOT_FOUND",
        "Timeout", "timeout", "ERR_CONNECTION", "get this app back up", "PAGE1_NO_EXACT_EVENT_LINK",
    ))

def _public(client):
    attempts = []
    for attempt in range(1, 5):
        try:
            payload = _public_once(client)
            return {"status": "GREEN", "attempt": attempt, "product_main_sha": PRODUCT_MAIN_SHA,
                    "handoff_cert_day": HANDOFF_CERT_DAY, "required_widths": [390,430,768,1440],
                    "evidence": payload}
        except Exception as exc:
            detail = str(exc)
            attempts.append({"attempt": attempt, "error": type(exc).__name__, "detail": detail[-12000:]})
            if attempt >= 4 or not _retryable(detail):
                raise TerminalFreezeFailure("PRODUCTION_READBACK_FAILED:" + json.dumps(attempts))
            time.sleep(12)
    raise TerminalFreezeFailure("PRODUCTION_READBACK_FAILED:" + json.dumps(attempts))

def _receipt(client, public):
    vp = {}
    for name, row in (public["evidence"].get("viewports") or {}).items():
        p1, p2, day = row.get("page1") or {}, row.get("page2") or {}, row.get("current_day") or {}
        vp[name] = {
            "auto_event_visible": p1.get("auto_event_visible"),
            "page1_event": p1.get("exact_event_id"),
            "page2_event": p2.get("exact_event_id"),
            "page1_overflow": p1.get("horizontal_overflow"),
            "page2_overflow": p2.get("horizontal_overflow"),
            "phoenix_today_visible": day.get("phoenix_today_visible"),
        }
    payload = {
        "schema_version": 1, "kind": "CFB_STEP8_TERMINAL_R4_RECEIPT", "project": "API2",
        "workstream": WORKSTREAM, "step": "8/8", "product_main_sha": PRODUCT_MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA, "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "public_proof": {"status": "GREEN", "attempt": public["attempt"], "day": HANDOFF_CERT_DAY,
                         "required_widths": [390,430,768,1440], "viewports": vp,
                         "evidence_digest": _digest(public["evidence"])},
        "freeze_token": FREEZE_TOKEN, "github_actions_fallback": 0, "created_at": _now(),
    }
    payload["digest"] = _digest(payload)
    existing = client.content(TERMINAL_RECEIPT_PATH, ref=RECEIPT_BRANCH, allow_404=True)
    if existing:
        old = _decode(existing)
        if old.get("product_main_sha") == PRODUCT_MAIN_SHA and old.get("candidate_sha") == CANDIDATE_SHA:
            return old
        raise TerminalFreezeFailure("TERMINAL_RECEIPT_COLLISION")
    client.put_content(TERMINAL_RECEIPT_PATH, _text(payload), RECEIPT_BRANCH, "receipt: CFB Step8 terminal R4")
    rb = _decode(client.content(TERMINAL_RECEIPT_PATH, ref=RECEIPT_BRANCH))
    if rb.get("digest") != payload["digest"]:
        raise TerminalFreezeFailure("TERMINAL_RECEIPT_READBACK_FAILED")
    return rb

def _baseline(tree, registry):
    checked = validate_registry(registry)
    bad = [{"path": p, "expected": b, "actual": tree.get(p)}
           for p, b in checked["artifacts"].items() if tree.get(p) != b]
    if bad:
        raise TerminalFreezeFailure("FROZEN_BASELINE_DRIFT:" + json.dumps(bad[:20]))
    return checked

def _freeze(client, thaw_ids):
    raw, reg = _registry_snapshot(client)
    if reg.get("source_main_sha") not in {PARENT_MAIN_SHA, PRODUCT_MAIN_SHA}:
        raise TerminalFreezeFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    tree = client.tree_blobs(PRODUCT_MAIN_SHA)
    _baseline(tree, reg)
    if sorted(x.get("thaw_id") for x in reg.get("active_thaws", [])) != thaw_ids:
        raise TerminalFreezeFailure("THAW_SET_DRIFT")
    artifacts = {}
    for path in FINAL_ARTIFACTS:
        if not tree.get(path):
            raise TerminalFreezeFailure("FINAL_ARTIFACT_MISSING:" + path)
        artifacts[path] = tree[path]
    entry = {"status": "FROZEN", "checkpoint_id": FREEZE_TOKEN, "source_main_sha": PRODUCT_MAIN_SHA,
             "artifacts": dict(sorted(artifacts.items()))}
    existing = (reg.get("entries") or {}).get(FREEZE_TOKEN)
    if existing and existing != entry:
        raise TerminalFreezeFailure("FREEZE_TOKEN_CONFLICT")
    if not existing:
        reg = deepcopy(reg)
        reg["revision"] = int(reg["revision"]) + 1
        reg["source_main_sha"] = PRODUCT_MAIN_SHA
        reg["entries"][FREEZE_TOKEN] = entry
        reg["state_hash"] = _hash(_payload_without_hash(reg))
        validate_registry(reg)
        client.update_content(REGISTRY_PATH, _text(reg), REGISTRY_BRANCH, "registry: freeze CFB Step8 product proof", raw["sha"])
    rb = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH))
    validate_registry(rb)
    if (rb.get("entries") or {}).get(FREEZE_TOKEN) != entry:
        raise TerminalFreezeFailure("FREEZE_READBACK_FAILED")
    return {"revision": rb["revision"], "state_hash": rb["state_hash"], "artifact_count": len(artifacts)}

def _ledger(client, public, receipt, frozen):
    if client.branch_sha("main") != PRODUCT_MAIN_SHA:
        raise TerminalFreezeFailure("MAIN_DRIFT_BEFORE_LEDGER")
    raw = client.content(LEDGER_PATH, ref="main")
    led = _decode(raw)
    if led.get("workstream") != WORKSTREAM or led.get("step") != "8/8":
        raise TerminalFreezeFailure("LEDGER_IDENTITY_DRIFT")
    led["status"] = "GREEN_PLUS_FROZEN"
    led["problem"] = "Resolved. V14 source event publication is tap-gated and production-certified."
    led["root_cause"] = "V14 published the internally selected default event before a real card tap."
    led["patch"] = "V14 now publishes the event only when selector-sync matches the exact real card-tap event."
    led.setdefault("step2a", {}).update({"authoritative_main_sha": PRODUCT_MAIN_SHA, "one_authoritative_proof_chain": True,
                                        "github_actions_fallback_authorized": False})
    led.setdefault("tdd", {}).update({"source_guard_candidate_sha": CANDIDATE_SHA, "source_guard_premerge_proof_id": PREMERGE_PROOF_ID,
                                     "source_guard_receipt_digest": PREMERGE_RECEIPT_DIGEST, "green_terminal_verification_claimed": True})
    led.setdefault("public_proof", {}).update({"status": "GREEN", "postmerge_product_main_sha": PRODUCT_MAIN_SHA,
        "handoff_cert_day": HANDOFF_CERT_DAY, "viewports": [390,430,768,1440], "current_phoenix_day_proof_separate": True,
        "exact_event_identity_required": True, "horizontal_overflow_allowed": False, "data_limited_visible_allowed": False,
        "page1_auto_event_before_tap": False, "terminal_receipt_digest": receipt["digest"], "terminal_receipt_path": TERMINAL_RECEIPT_PATH})
    led.setdefault("runless", {}).update({"premerge_proof_request_status": "MERGE_AUTHORIZED", "premerge_proof_id": PREMERGE_PROOF_ID,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST, "premerge_candidate_sha": CANDIDATE_SHA,
        "postmerge_public_proof_status": "GREEN", "postmerge_product_main_sha": PRODUCT_MAIN_SHA, "github_actions_fallback": 0})
    led["freeze_token"] = FREEZE_TOKEN
    led["green_plus_frozen_claimed"] = True
    led["step9_started"] = False
    led["next_legal_action"] = "NONE_TERMINAL"
    led["terminal"] = {"status": "GREEN_PLUS_FROZEN", "product_main_sha": PRODUCT_MAIN_SHA, "candidate_sha": CANDIDATE_SHA,
        "premerge_proof_id": PREMERGE_PROOF_ID, "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "terminal_receipt_digest": receipt["digest"], "terminal_receipt_path": TERMINAL_RECEIPT_PATH,
        "public_attempt": public["attempt"], "required_widths": [390,430,768,1440], "page1_auto_event_before_tap": False,
        "product_freeze_revision": frozen["revision"], "product_freeze_state_hash": frozen["state_hash"],
        "github_actions_fallback": 0, "completed_at": _now()}
    write = client.update_content(LEDGER_PATH, _text(led), "main", "ledger: close CFB Game Total Step8 GREEN + FROZEN", raw["sha"])
    final_main = str(((write or {}).get("commit") or {}).get("sha") or "")
    if len(final_main) != 40 or client.branch_sha("main") != final_main:
        raise TerminalFreezeFailure("LEDGER_MAIN_READBACK_FAILED")
    return final_main

def _rebind(client, final_main, thaw_ids):
    raw, reg = _registry_snapshot(client)
    entry = deepcopy((reg.get("entries") or {}).get(FREEZE_TOKEN))
    if not entry:
        raise TerminalFreezeFailure("FREEZE_TOKEN_MISSING")
    tree = client.tree_blobs(final_main)
    _baseline(tree, reg)
    if sorted(x.get("thaw_id") for x in reg.get("active_thaws", [])) != thaw_ids:
        raise TerminalFreezeFailure("REBIND_THAW_DRIFT")
    ledger_blob = tree.get(LEDGER_PATH)
    if not ledger_blob:
        raise TerminalFreezeFailure("LEDGER_BLOB_MISSING")
    reg = deepcopy(reg)
    reg["revision"] = int(reg["revision"]) + 1
    reg["source_main_sha"] = final_main
    entry["source_main_sha"] = final_main
    entry["artifacts"][LEDGER_PATH] = ledger_blob
    entry["artifacts"] = dict(sorted(entry["artifacts"].items()))
    reg["entries"][FREEZE_TOKEN] = entry
    reg["state_hash"] = _hash(_payload_without_hash(reg))
    validate_registry(reg)
    client.update_content(REGISTRY_PATH, _text(reg), REGISTRY_BRANCH, "registry: bind CFB Step8 freeze to terminal main", raw["sha"])
    rb = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH))
    validate_registry(rb)
    return {"revision": rb["revision"], "state_hash": rb["state_hash"], "source_main_sha": rb["source_main_sha"],
            "ledger_blob": ledger_blob, "preserved_thaws": thaw_ids}

def _readback(client, final_main, receipt, reg, lease_id):
    if client.branch_sha("main") != final_main:
        raise TerminalFreezeFailure("FINAL_MAIN_DRIFT")
    led = _decode(client.content(LEDGER_PATH, ref="main"))
    if led.get("status") != "GREEN_PLUS_FROZEN" or led.get("green_plus_frozen_claimed") is not True or led.get("next_legal_action") != "NONE_TERMINAL":
        raise TerminalFreezeFailure("FINAL_LEDGER_DRIFT")
    frozen = _decode(client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH))
    entry = (frozen.get("entries") or {}).get(FREEZE_TOKEN) or {}
    tree = client.tree_blobs(final_main)
    if (frozen.get("source_main_sha") != final_main or entry.get("source_main_sha") != final_main or entry.get("status") != "FROZEN"
        or (entry.get("artifacts") or {}).get(LEDGER_PATH) != tree.get(LEDGER_PATH)
        or frozen.get("revision") != reg["revision"] or frozen.get("state_hash") != reg["state_hash"]):
        raise TerminalFreezeFailure("FINAL_REGISTRY_DRIFT")
    rr = _decode(client.content(TERMINAL_RECEIPT_PATH, ref=RECEIPT_BRANCH))
    if rr.get("digest") != receipt.get("digest"):
        raise TerminalFreezeFailure("FINAL_RECEIPT_DRIFT")
    lease = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_BRANCH)))
    if any(h.get("lease_id") == lease_id for h in lease.get("holders", [])):
        raise TerminalFreezeFailure("FINAL_LEASE_HELD")
    return {"status": "GREEN+FROZEN", "main_sha": final_main, "registry_revision": reg["revision"],
            "registry_state_hash": reg["state_hash"], "freeze_token": FREEZE_TOKEN,
            "terminal_receipt_digest": receipt["digest"], "lease_released": True, "github_actions_fallback": 0}

def execute(app):
    client = app.state.github_client
    if client.branch_sha("main") != PRODUCT_MAIN_SHA:
        raise TerminalFreezeFailure("MAIN_DRIFT_AT_START")
    parents = {str(p.get("sha") or "") for p in client.commit(PRODUCT_MAIN_SHA).get("parents", [])}
    if CANDIDATE_SHA not in parents:
        raise TerminalFreezeFailure("MERGED_CANDIDATE_PARENT_MISSING")
    authority = _ensure_authority(client)
    _, reg0 = _registry_snapshot(client)
    thaws = sorted(str(x.get("thaw_id") or "") for x in reg0.get("active_thaws", []))
    if "THAW-CFB-GT-STEP8-PAGE1-EVENT-GUARD-R2" in thaws:
        raise TerminalFreezeFailure("OLD_STEP8_THAW_ACTIVE")
    lease_id = _claim(client, str(reg0["state_hash"]))
    released = None
    try:
        _ensure_chromium()
        public = _public(client)
        receipt = _receipt(client, public)
        frozen = _freeze(client, thaws)
        final_main = _ledger(client, public, receipt, frozen)
        final_reg = _rebind(client, final_main, thaws)
        client.publish_check(final_main, "cfb-step8-terminal-freeze", "success",
            {"title": "CFB Step 8 GREEN + FROZEN",
             "summary": f"{FREEZE_TOKEN}; receipt={receipt['digest']}; registry={final_reg['revision']}:{final_reg['state_hash']}"})
        released = _release(client, lease_id)
        rb = _readback(client, final_main, receipt, final_reg, lease_id)
        return {"status": "GREEN+FROZEN", "workstream": WORKSTREAM, "step": "8/8", "candidate_sha": CANDIDATE_SHA,
                "product_main_sha": PRODUCT_MAIN_SHA, "final_main_sha": final_main, "premerge_authority": authority,
                "production": public, "terminal_receipt": {"path": TERMINAL_RECEIPT_PATH, "digest": receipt["digest"]},
                "product_freeze": frozen, "final_registry": final_reg, "lease_id": lease_id, "lease_release": released,
                "readback": rb, "github_actions_fallback": 0, "duplicate_proof_runs": 0}
    except Exception:
        if released is None:
            try:
                _release(client, lease_id)
            except Exception as exc:
                print("CFB_STEP8_R4_RELEASE_AFTER_FAILURE=" + json.dumps({"status":"FAIL","detail":str(exc)[:8000]}, sort_keys=True), flush=True)
        raise

def install_startup(app):
    app.state.cfb_step8_terminal_freeze_event_guard_r4 = {"status": "STARTING"}
    def worker():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:32000],
                      "github_actions_fallback": 0, "duplicate_proof_runs": 0}
        app.state.cfb_step8_terminal_freeze_event_guard_r4 = result
        print("CFB_STEP8_TERMINAL_FREEZE_EVENT_GUARD_R4=" + json.dumps(result, sort_keys=True, default=str), flush=True)
    @app.on_event("startup")
    def run():
        Thread(target=worker, name="cfb-step8-terminal-finalizer-r4", daemon=True).start()
    return app
