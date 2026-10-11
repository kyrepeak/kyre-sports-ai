from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import time
from copy import deepcopy
from pathlib import Path

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt, validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import release_scope, validate_state as validate_scope_state

from .gate import publish_gate
from .postmerge_reuse import evaluate_postmerge_reuse
from .registry import GithubRegistryBackend, REGISTRY_PATH

WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
TASK_ID = "cfb-game-total-mobile-production-step8-v1"
SOURCE_MAIN_SHA = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
SOURCE_CANDIDATE_SHA = "a1fbecbb5d5dd96d71ad21d4961bf8407c80be9e"
MAIN_SHA = "1b0169a8a6e644ae6971685fb50b9bd96d510106"
PREMERGE_TASK_ID = "cfb-game-total-mobile-production-step8-premerge-v1"
PREMERGE_PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-premerge-v1.json"
PREMERGE_PROOF_ID = "cfb-game-total-mobile-production-step8-premerge-v1-a1fbecbb5d5dd96d-8137655df10b99a1"
PREMERGE_DIGEST = "a7fbe20d978c5c7646933aa2ad8806a799f4eaf76d7ba8a902039b1301055bdc"
PREMERGE_CHECK_ID = 114370827167
MERGED_PROOF_ID = "cfb-game-total-mobile-production-step8-v1-1b0169a8a6e644ae-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP8_MOBILE_PRODUCTION_V1_FROZEN"
THAW_ID = "THAW-CFB-GT-MOBILE-PRODUCTION-STEP8-R1"
FROZEN_PATH = "cfb_game_total_clean_page_v43.py"
FROM_BLOB = "ebb7bfa20489598a62891ec4e5e868fe350c8712"
TO_BLOB = "3a05f8f3f9d434a462da702d429e7db990c9b528"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"
PUBLIC_EVIDENCE_BASE = "devsystem/runless_public_evidence"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"
FREEZE_PATHS = (
    "cfb_game_total_clean_page_v43.py",
    "devsystem/cfb_game_total_mobile_production_step8_v1.py",
    "devsystem/cfb_game_total_mobile_production_step8_runless_v1.py",
    "devsystem/production_targets_v1.json",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-premerge-v1.json",
    "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-v1.json",
    "devsystem/task_ledgers/cfb-game-total-mobile-production-step8-v1.json",
    "tests/test_cfb_game_total_mobile_production_step8_v1.py",
    "tests/test_cfb_game_total_page1_default_selection_step8_v1.py",
)
UNRELATED_THAWS = {
    "THAW-CFB-GT-PAGE2-STEP7-REPAIR-R1",
    "THAW-CFB-GT-PAGE2-STEP7-REVIEW-RED-R1",
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
    "THAW-RUNLESS-TASK14-MANUAL-FALLBACK",
}


class Step8PostmergeFailure(RuntimeError):
    pass


def _beat(stage: str, detail: object = "") -> None:
    print("CFB_GAME_TOTAL_STEP8_FINAL_HEARTBEAT=" + json.dumps({"stage": stage, "detail": detail}, sort_keys=True, default=str), flush=True)


def _decode(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise Step8PostmergeFailure(label + "_READ_FAILED")
    return json.loads(base64.b64decode(raw["content"]).decode())


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _policy(plan: dict) -> dict:
    return {
        "task_id": str(plan.get("task_id") or ""),
        "workstream": str(plan.get("workstream") or ""),
        "commands": list(plan.get("commands") or []),
        "probes": list(plan.get("probes") or []),
        "timeout_seconds": int(plan.get("timeout_seconds") or 0),
        "live_ttl_seconds": int(plan.get("live_ttl_seconds") or 0),
        "freeze_token": str(plan.get("freeze_token") or ""),
    }


def _registry_summary(registry: dict) -> dict:
    return {
        "revision": int(registry["revision"]),
        "state_hash": str(registry["state_hash"]),
        "active_thaws": sorted(str(item.get("thaw_id") or "") for item in registry.get("active_thaws", [])),
    }


def _step2a(client) -> tuple[dict, dict, dict]:
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8PostmergeFailure("MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if parents != {SOURCE_MAIN_SHA, SOURCE_CANDIDATE_SHA}:
        raise Step8PostmergeFailure("MERGE_LINEAGE_DRIFT:" + json.dumps(sorted(parents)))
    merged_tree = client.tree_blobs(MAIN_SHA)
    if str(merged_tree.get(FROZEN_PATH) or "") != TO_BLOB:
        raise Step8PostmergeFailure("MERGED_V43_BLOB_DRIFT")
    missing = [path for path in FREEZE_PATHS if not merged_tree.get(path)]
    if missing:
        raise Step8PostmergeFailure("MERGED_ARTIFACT_MISSING:" + ",".join(missing))

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        if FREEZE_TOKEN in (registry.get("entries") or {}) and str(registry.get("source_main_sha") or "") == MAIN_SHA:
            return registry, merged_tree, {"already_frozen": True}
        raise Step8PostmergeFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    thaws = {str(row.get("thaw_id") or ""): row for row in registry.get("active_thaws", [])}
    if set(thaws) != UNRELATED_THAWS | {THAW_ID}:
        raise Step8PostmergeFailure("ACTIVE_THAW_SET_DRIFT:" + json.dumps(sorted(thaws)))
    expected = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": SOURCE_CANDIDATE_SHA,
        "files": {FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    if thaws.get(THAW_ID) != expected:
        raise Step8PostmergeFailure("STEP8_THAW_DRIFT")
    return registry, merged_tree, {"already_frozen": False}


def _premerge_receipt(client) -> dict:
    receipt = _decode(client.content(f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json", ref=RECEIPT_REF), "PREMERGE_RECEIPT")
    validate_runless_receipt(receipt)
    if str(receipt.get("proof_id") or "") != PREMERGE_PROOF_ID:
        raise Step8PostmergeFailure("PREMERGE_PROOF_ID_DRIFT")
    if str(receipt.get("candidate_sha") or "") != SOURCE_CANDIDATE_SHA:
        raise Step8PostmergeFailure("PREMERGE_CANDIDATE_DRIFT")
    if str(receipt.get("digest") or "") != PREMERGE_DIGEST:
        raise Step8PostmergeFailure("PREMERGE_DIGEST_DRIFT")
    if str(receipt.get("failure_class") or "") != "NONE":
        raise Step8PostmergeFailure("PREMERGE_NOT_GREEN")
    return receipt


def _reuse(client, premerge: dict, tree: dict) -> dict:
    candidate_plan = _decode(client.content(PREMERGE_PLAN_PATH, ref=SOURCE_CANDIDATE_SHA), "CANDIDATE_PLAN")
    merged_plan = _decode(client.content(PREMERGE_PLAN_PATH, ref=MAIN_SHA), "MERGED_PLAN")
    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE_SHA)
    candidate_artifacts = {path: str(candidate_tree.get(path) or "") for path in premerge.get("artifact_map", {})}
    candidate_dependencies = {path: str(candidate_tree.get(path) or "") for path in premerge.get("dependency_map", {})}
    if candidate_artifacts != dict(premerge.get("artifact_map") or {}):
        raise Step8PostmergeFailure("CANDIDATE_ARTIFACT_RECEIPT_DRIFT")
    if candidate_dependencies != dict(premerge.get("dependency_map") or {}):
        raise Step8PostmergeFailure("CANDIDATE_DEPENDENCY_RECEIPT_DRIFT")
    merged_artifacts = {path: str(tree.get(path) or "") for path in premerge.get("artifact_map", {})}
    merged_dependencies = {path: str(tree.get(path) or "") for path in premerge.get("dependency_map", {})}
    reuse = evaluate_postmerge_reuse(
        premerge_receipt=premerge,
        merged_main_sha=MAIN_SHA,
        merged_artifacts=merged_artifacts,
        merged_dependencies=merged_dependencies,
        candidate_policy=_policy(candidate_plan),
        merged_policy=_policy(merged_plan),
        candidate_is_ancestor=True,
        proof_run_id=PREMERGE_CHECK_ID,
    )
    if reuse.get("decision") != "REUSE_APPROVED" or reuse.get("reusable") is not True:
        raise Step8PostmergeFailure("REUSE_REJECTED:" + ",".join(reuse.get("reasons") or []))
    if reuse.get("static_evidence_reexecuted") is not False or reuse.get("github_actions_enabled") is not False:
        raise Step8PostmergeFailure("REUSE_POLICY_DRIFT")
    return reuse


def _clone_main() -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory(prefix="cfb-step8-postmerge-")
    root = Path(tmp.name) / "repo"
    clone = subprocess.run(["git", "clone", "--depth", "1", REPO, str(root)], text=True, capture_output=True, timeout=120)
    if clone.returncode != 0:
        tmp.cleanup()
        raise Step8PostmergeFailure("CLONE_FAILED:" + (clone.stderr or clone.stdout)[-3000:])
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != MAIN_SHA:
        tmp.cleanup()
        raise Step8PostmergeFailure(f"PUBLIC_CERT_CLONE_HEAD_DRIFT:{head}")
    return tmp, root


def _wait_streamlit_ready(root: Path) -> dict:
    install = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=root, text=True, capture_output=True, timeout=300)
    if install.returncode != 0:
        raise Step8PostmergeFailure("CHROMIUM_INSTALL_FAILED:" + ((install.stdout or "") + (install.stderr or ""))[-5000:])
    code = r'''
import json, time
from playwright.sync_api import sync_playwright
from devsystem import cfb_game_total_mobile_production_step8_v1 as m
result={"status":"TIMEOUT"}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage","--no-sandbox"])
    try:
        page=browser.new_page(viewport={"width":390,"height":844})
        for attempt in range(24):
            try:
                page.goto(m.page1_route(),wait_until="domcontentloaded",timeout=90000)
                frame, scans=m._find_cfb_frame(page,required_markers=m.PAGE1_FRAME_MARKERS,required_testids=(m.PHOENIX_DAY_TESTID,m.PAGE1_TESTID),timeout_seconds=12.0)
                result={"status":"READY","attempt":attempt+1,"url":page.url,"event":m._event_from_url(page.url)}
                break
            except Exception as exc:
                result={"status":"WAITING","attempt":attempt+1,"detail":str(exc)[-1600:]}
                time.sleep(10)
    finally:
        browser.close()
print("STEP8_STREAMLIT_READINESS="+json.dumps(result,sort_keys=True))
raise SystemExit(0 if result.get("status")=="READY" else 1)
'''
    proc = subprocess.run([sys.executable, "-c", code], cwd=root, text=True, capture_output=True, timeout=600)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    rows = [line for line in (proc.stdout or "").splitlines() if line.startswith("STEP8_STREAMLIT_READINESS=")]
    detail = json.loads(rows[-1].split("=", 1)[1]) if rows else {"status": "UNKNOWN", "detail": output[-4000:]}
    if proc.returncode != 0 or detail.get("status") != "READY":
        raise Step8PostmergeFailure("STREAMLIT_MERGED_CODE_NOT_READY:" + json.dumps(detail, sort_keys=True))
    return detail


def _public_cert(root: Path) -> tuple[dict, str]:
    proc = subprocess.run([sys.executable, "-m", "devsystem.cfb_game_total_mobile_production_step8_runless_v1"], cwd=root, text=True, capture_output=True, timeout=1500)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0 or "CFB_GAME_TOTAL_STEP8_PUBLIC_GREEN" not in output:
        raise Step8PostmergeFailure("PUBLIC_CERT_FAILED:" + output[-16000:])
    marker = "CFB_GAME_TOTAL_STEP8_PUBLIC_EVIDENCE="
    rows = [line for line in (proc.stdout or "").splitlines() if line.startswith(marker)]
    if not rows:
        raise Step8PostmergeFailure("PUBLIC_EVIDENCE_MISSING:" + output[-8000:])
    payload = json.loads(rows[-1][len(marker):])
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    if set((payload.get("viewports") or {}).keys()) != {"mobile390", "mobile430", "tablet", "desktop"}:
        raise Step8PostmergeFailure("PUBLIC_VIEWPORT_SET_DRIFT")
    return payload, digest


def _persist_public_evidence(client, payload: dict, digest: str) -> None:
    path = f"{PUBLIC_EVIDENCE_BASE}/{MERGED_PROOF_ID}.json"
    body = {"proof_id": MERGED_PROOF_ID, "main_sha": MAIN_SHA, "digest": digest, "evidence": payload}
    existing = client.content(path, ref=RECEIPT_REF, allow_404=True)
    if existing:
        current = _decode(existing, "PUBLIC_EVIDENCE")
        if current != body:
            raise Step8PostmergeFailure("PUBLIC_EVIDENCE_COLLISION")
        return
    client.put_content(path, _json_text(body), RECEIPT_REF, "runless: persist CFB Game Total Step 8 public production evidence")


def _merged_receipt(client, *, premerge: dict, registry: dict, tree: dict, reuse: dict, public_digest: str) -> dict:
    path = f"{RECEIPT_BASE}/{MERGED_PROOF_ID}.json"
    existing = client.content(path, ref=RECEIPT_REF, allow_404=True)
    if existing:
        receipt = _decode(existing, "MERGED_RECEIPT")
        validate_runless_receipt(receipt)
        if str(receipt.get("candidate_sha") or "") != MAIN_SHA or str(receipt.get("prior_digest") or "") != PREMERGE_DIGEST:
            raise Step8PostmergeFailure("MERGED_RECEIPT_DRIFT")
        if public_digest not in list(receipt.get("evidence_digests") or []):
            raise Step8PostmergeFailure("MERGED_RECEIPT_PUBLIC_EVIDENCE_DRIFT")
        return receipt
    artifact_map = {path: str(tree.get(path) or "") for path in FREEZE_PATHS}
    dependency_map = {path: str(tree.get(path) or "") for path in premerge.get("dependency_map", {})}
    evidence = list(premerge.get("evidence_digests") or []) + [public_digest]
    receipt = build_runless_receipt(
        proof_id=MERGED_PROOF_ID,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="8/8-mobile-production-final",
        candidate_sha=MAIN_SHA,
        artifact_map=artifact_map,
        dependency_map=dependency_map,
        registry_before=_registry_summary(registry),
        registry_after=_registry_summary(registry),
        evidence_digests=evidence,
        failure_class="NONE",
        prior_digest=PREMERGE_DIGEST,
        proof_fingerprint=str(premerge.get("proof_fingerprint") or ""),
        reused_from_proof_id=PREMERGE_PROOF_ID,
        reused_from_receipt_digest=PREMERGE_DIGEST,
        reuse_content_fingerprint=str(reuse.get("content_fingerprint") or ""),
        static_evidence_reexecuted=False,
        github_actions_enabled=False,
    )
    client.put_content(path, _json_text(receipt), RECEIPT_REF, "runless: persist CFB Game Total Step 8 merged-main receipt")
    return receipt


def _ensure_gate(client, receipt: dict) -> tuple[bool, int | None]:
    runs = client.request("GET", f"/commits/{MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100") or {}
    expected_summary = "receipt=" + str(receipt["digest"])
    for run in runs.get("check_runs", []):
        output = run.get("output") or {}
        if str(run.get("head_sha") or "") == MAIN_SHA and str(run.get("status") or "") == "completed" and str(run.get("conclusion") or "") == "success" and str(output.get("summary") or "") == expected_summary:
            return False, int(run.get("id"))
    published = publish_gate(client, MAIN_SHA, "success", receipt)
    check_id = published.get("id") if isinstance(published, dict) else None
    return True, int(check_id) if check_id else None


def _freeze_registry(client, registry: dict, tree: dict) -> dict:
    before_unrelated = [deepcopy(row) for row in registry.get("active_thaws", []) if str(row.get("thaw_id") or "") != THAW_ID]
    planned = plan_baseline_forward_port(
        registry,
        updates={FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
        source_main_sha=MAIN_SHA,
    )
    if planned.get("retired_empty_thaw_grants") != [THAW_ID]:
        raise Step8PostmergeFailure("STEP8_THAW_RETIREMENT_DRIFT:" + json.dumps(planned.get("retired_empty_thaw_grants")))
    result = deepcopy(planned["registry"])
    if [row for row in result.get("active_thaws", [])] != before_unrelated:
        raise Step8PostmergeFailure("UNRELATED_THAW_DRIFT")
    artifacts = {path: str(tree.get(path) or "") for path in FREEZE_PATHS}
    exact_entry = {"status": "FROZEN", "checkpoint_id": FREEZE_TOKEN, "source_main_sha": MAIN_SHA, "artifacts": dict(sorted(artifacts.items()))}
    existing = (result.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None and existing != exact_entry:
        raise Step8PostmergeFailure("FREEZE_TOKEN_COLLISION")
    result["entries"][FREEZE_TOKEN] = exact_entry
    result["state_hash"] = _hash(_payload_without_hash(result))
    validate_registry(result)

    backend = GithubRegistryBackend(client)
    current = backend.read_registry()
    if str(current.get("state_hash") or "") != str(registry.get("state_hash") or ""):
        raise Step8PostmergeFailure("REGISTRY_CHANGED_DURING_FINALIZATION")
    client.update_content(REGISTRY_PATH, _json_text(result), backend.branch, "registry: freeze CFB Game Total Step 8 mobile production", backend._blob_sha)
    readback = backend.read_registry()
    validate_registry(readback)
    if readback != result:
        raise Step8PostmergeFailure("REGISTRY_READBACK_MISMATCH")
    return {"revision": int(readback["revision"]), "state_hash": str(readback["state_hash"]), "active_thaws": sorted(str(row.get("thaw_id") or "") for row in readback.get("active_thaws", [])), "artifacts": artifacts}


def _release_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    state = validate_scope_state(_decode(raw, "LEASE"))
    owned = [row for row in state.get("holders", []) if row.get("owner_id") == LEASE_OWNER]
    if not owned:
        return {"released": False, "holders": 0, "revision": int(state["revision"]), "state_hash": str(state["state_hash"])}
    if len(owned) != 1:
        raise Step8PostmergeFailure("STEP8_LEASE_DUPLICATE")
    holder = owned[0]
    identity = (holder.get("scope") or {}).get("resource_identity") or {}
    if str(identity.get("candidate_sha") or "") != SOURCE_CANDIDATE_SHA:
        raise Step8PostmergeFailure("STEP8_LEASE_CANDIDATE_DRIFT")
    released = release_scope(state, owner_id=LEASE_OWNER, lease_id=str(holder["lease_id"]), expected_revision=int(state["revision"]), expected_state_hash=str(state["state_hash"]))
    if released["result"].get("allowed") is not True:
        raise Step8PostmergeFailure("STEP8_LEASE_RELEASE_BLOCKED")
    updated = released["state"]
    client.update_content(LEASE_PATH, _json_text(updated), LEASE_REF, "lease: release CFB Game Total Step 8 scope", raw["sha"])
    readback = validate_scope_state(_decode(client.content(LEASE_PATH, ref=LEASE_REF), "LEASE_READBACK"))
    remaining = [row for row in readback.get("holders", []) if row.get("owner_id") == LEASE_OWNER]
    if remaining:
        raise Step8PostmergeFailure("STEP8_LEASE_RELEASE_READBACK_FAILED")
    return {"released": True, "lease_id": str(holder["lease_id"]), "holders": 0, "revision": int(readback["revision"]), "state_hash": str(readback["state_hash"])}


def execute(app) -> dict:
    client = app.state.github_client
    _beat("step2a", MAIN_SHA)
    registry, tree, state = _step2a(client)
    if state.get("already_frozen"):
        lease = _release_lease(client)
        return {"status": "GREEN", "decision": "STEP8_ALREADY_GREEN_FROZEN", "main_sha": MAIN_SHA, "registry_revision": int(registry["revision"]), "registry_state_hash": str(registry["state_hash"]), "lease": lease, "github_actions_fallback": 0}

    premerge = _premerge_receipt(client)
    reuse = _reuse(client, premerge, tree)
    _beat("reuse-approved", {"static_evidence_reexecuted": reuse.get("static_evidence_reexecuted"), "decision": reuse.get("decision")})

    tmp, root = _clone_main()
    try:
        _beat("production-readiness", "waiting-for-merged-streamlit")
        readiness = _wait_streamlit_ready(root)
        _beat("production-ready", readiness)
        _beat("public-cert", [390, 430, 768, 1440])
        public, public_digest = _public_cert(root)
    finally:
        tmp.cleanup()
    _beat("public-green", {"digest": public_digest, "viewports": sorted((public.get("viewports") or {}).keys())})
    _persist_public_evidence(client, public, public_digest)

    receipt = _merged_receipt(client, premerge=premerge, registry=registry, tree=tree, reuse=reuse, public_digest=public_digest)
    gate_published, check_id = _ensure_gate(client, receipt)
    _beat("merged-gate", {"receipt": receipt.get("digest"), "check_id": check_id, "published": gate_published})

    frozen = _freeze_registry(client, registry, tree)
    _beat("registry-frozen", frozen)
    lease = _release_lease(client)
    _beat("lease-released", lease)

    return {
        "status": "GREEN",
        "decision": "STEP8_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "premerge_receipt": PREMERGE_DIGEST,
        "merged_receipt": str(receipt.get("digest") or ""),
        "public_evidence_digest": public_digest,
        "public_viewports": sorted((public.get("viewports") or {}).keys()),
        "runless_check_id": check_id,
        "gate_published": gate_published,
        "static_evidence_reexecuted": False,
        "registry": frozen,
        "lease": lease,
        "step8_thaw_retired": THAW_ID not in frozen["active_thaws"],
        "unrelated_thaws_preserved": set(frozen["active_thaws"]) == UNRELATED_THAWS,
        "freeze_token": FREEZE_TOKEN,
        "github_actions_fallback": 0,
        "step9_started": False,
    }


def install_startup(app):
    app.state.cfb_game_total_step8_postmerge_final = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _start():
        def worker():
            try:
                app.state.cfb_game_total_step8_postmerge_final = execute(app)
            except Exception as exc:
                app.state.cfb_game_total_step8_postmerge_final = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:16000]}
            print("CFB_GAME_TOTAL_STEP8_POSTMERGE_FINAL=" + json.dumps(app.state.cfb_game_total_step8_postmerge_final, sort_keys=True, default=str), flush=True)
        threading.Thread(target=worker, daemon=True, name="cfb-step8-postmerge-final").start()

    return app


__all__ = ["execute", "install_startup"]
