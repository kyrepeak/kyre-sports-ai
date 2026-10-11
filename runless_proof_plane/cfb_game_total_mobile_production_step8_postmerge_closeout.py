from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from devsystem.frozen_artifact_registry_v1 import _hash, _payload_without_hash, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt, validate_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import release_scope, validate_state as validate_scope_state

from .gate import publish_gate
from .postmerge_reuse import evaluate_postmerge_reuse
from .registry import GithubRegistryBackend, REGISTRY_PATH

WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
TASK_ID = "cfb-game-total-mobile-production-step8-premerge-v1"
SOURCE_MAIN_SHA = "36e0d3ee8de1a72bdeeb5e007334df1e8c5a3adb"
SOURCE_CANDIDATE_SHA = "a1fbecbb5d5dd96d71ad21d4961bf8407c80be9e"
MAIN_SHA = "1b0169a8a6e644ae6971685fb50b9bd96d510106"
PREMERGE_PROOF_ID = "cfb-game-total-mobile-production-step8-premerge-v1-a1fbecbb5d5dd96d-8137655df10b99a1"
PREMERGE_DIGEST = "a7fbe20d978c5c7646933aa2ad8806a799f4eaf76d7ba8a902039b1301055bdc"
PREMERGE_CHECK_ID = 114361184050
MERGED_PROOF_ID = "cfb-game-total-mobile-production-step8-v1-1b0169a8a6e644ae-reused"
PREMERGE_PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-mobile-production-step8-premerge-v1.json"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP8_MOBILE_PRODUCTION_V1_FROZEN"
STEP6_FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP6_GAME_CARDS_V1_FROZEN"
THAW_ID = "THAW-CFB-GT-MOBILE-PRODUCTION-STEP8-R1"
FROZEN_PATH = "cfb_game_total_clean_page_v43.py"
FROM_BLOB = "ebb7bfa20489598a62891ec4e5e868fe350c8712"
TO_BLOB = "3a05f8f3f9d434a462da702d429e7db990c9b528"
EXPECTED_REGISTRY_REVISION = 269
EXPECTED_REGISTRY_HASH = "8165c8a50fd2c524b9d23ec512e64e3308f0addb43135d9a18a6ae8d5f89396c"
LEASE_REF = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"
PRODUCTION_URL = "https://pickvault.streamlit.app"
REPO = "https://github.com/kyrepeak/kyre-sports-ai.git"
OTHER_THAWS = {
    "THAW-CFB-GT-PAGE2-STEP7-REPAIR-R1",
    "THAW-CFB-GT-PAGE2-STEP7-REVIEW-RED-R1",
    "THAW-NBA-OU-STEP2-BOOTSTRAP-R3",
    "THAW-RUNLESS-TASK14-MANUAL-FALLBACK",
}


class Step8PostmergeCloseoutFailure(RuntimeError):
    pass


def _beat(stage: str, detail: object = "") -> None:
    print(
        "CFB_GAME_TOTAL_STEP8_FINAL_HEARTBEAT="
        + json.dumps({"stage": stage, "detail": detail}, sort_keys=True, default=str),
        flush=True,
    )


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise Step8PostmergeCloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise Step8PostmergeCloseoutFailure(label + "_DECODE_FAILED") from exc


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _summary(registry: dict) -> dict:
    return {
        "revision": int(registry["revision"]),
        "state_hash": str(registry["state_hash"]),
        "active_thaws": sorted(
            str(row.get("thaw_id") or "")
            for row in (registry.get("active_thaws") or [])
            if str(row.get("status") or "ACTIVE").upper() == "ACTIVE"
        ),
    }


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


def _assert_main_and_control_state(client) -> tuple[dict, dict, str]:
    if client.branch_sha("main") != MAIN_SHA:
        raise Step8PostmergeCloseoutFailure("MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(row.get("sha") or "") for row in (commit.get("parents") or [])}
    if parents != {SOURCE_MAIN_SHA, SOURCE_CANDIDATE_SHA}:
        raise Step8PostmergeCloseoutFailure("MERGE_LINEAGE_DRIFT")

    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)
    if int(registry.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise Step8PostmergeCloseoutFailure("REGISTRY_REVISION_DRIFT")
    if str(registry.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise Step8PostmergeCloseoutFailure("REGISTRY_HASH_DRIFT")
    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise Step8PostmergeCloseoutFailure("REGISTRY_SOURCE_MAIN_DRIFT")

    thaw_rows = list(registry.get("active_thaws") or [])
    step8 = [row for row in thaw_rows if row.get("thaw_id") == THAW_ID]
    expected_thaw = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": SOURCE_CANDIDATE_SHA,
        "files": {FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    if step8 != [expected_thaw]:
        raise Step8PostmergeCloseoutFailure("STEP8_THAW_DRIFT")
    unrelated = [row for row in thaw_rows if row.get("thaw_id") != THAW_ID]
    if {str(row.get("thaw_id") or "") for row in unrelated} != OTHER_THAWS:
        raise Step8PostmergeCloseoutFailure("UNRELATED_THAW_SET_DRIFT")

    lease_raw = client.content(LEASE_PATH, ref=LEASE_REF)
    lease = validate_scope_state(_decode_json(lease_raw, "LEASE"))
    owned = [row for row in lease.get("holders", []) if row.get("owner_id") == LEASE_OWNER]
    exact = [
        row for row in owned
        if (row.get("scope") or {}).get("resource_identity", {}).get("candidate_sha") == SOURCE_CANDIDATE_SHA
    ]
    if len(owned) != 1 or len(exact) != 1:
        raise Step8PostmergeCloseoutFailure("LEASE_IDENTITY_DRIFT")
    return registry, lease, str(exact[0]["lease_id"])


def _load_premerge(client) -> dict:
    receipt = _decode_json(
        client.content(f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json", ref=RECEIPT_REF),
        "PREMERGE_RECEIPT",
    )
    validate_runless_receipt(receipt)
    if str(receipt.get("proof_id") or "") != PREMERGE_PROOF_ID:
        raise Step8PostmergeCloseoutFailure("PREMERGE_PROOF_ID_DRIFT")
    if str(receipt.get("candidate_sha") or "") != SOURCE_CANDIDATE_SHA:
        raise Step8PostmergeCloseoutFailure("PREMERGE_CANDIDATE_DRIFT")
    if str(receipt.get("digest") or "") != PREMERGE_DIGEST:
        raise Step8PostmergeCloseoutFailure("PREMERGE_DIGEST_DRIFT")
    if str(receipt.get("failure_class") or "") != "NONE":
        raise Step8PostmergeCloseoutFailure("PREMERGE_NOT_GREEN")
    return receipt


def _ensure_chromium(root: Path) -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True,args=['--no-sandbox']); b.close(); p.stop(); print('READY')",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=45,
    )
    if probe.returncode == 0:
        _beat("chromium-ready", "cached")
        return
    _beat("chromium-install", "cache-miss")
    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=300,
    )
    if install.returncode != 0:
        raise Step8PostmergeCloseoutFailure(
            "CHROMIUM_INSTALL_FAILED:" + ((install.stdout or "") + (install.stderr or ""))[-5000:]
        )
    _beat("chromium-ready", "installed")


def _production_ready(root: Path) -> dict:
    from playwright.sync_api import sync_playwright

    phoenix_day = datetime.now(ZoneInfo("America/Phoenix")).date().isoformat()
    query = urlencode(
        {
            "ks_sport": "College Football",
            "ks_cfb_market": "Game Total",
            "ks_cfb_game_total_date": phoenix_day,
        }
    )
    url = f"{PRODUCTION_URL}/?{query}"
    deadline = time.monotonic() + 540
    attempt = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            while time.monotonic() < deadline:
                attempt += 1
                context = browser.new_context(viewport={"width": 390, "height": 1200})
                page = context.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(10000)
                    frames = []
                    ready = False
                    stale_event = False
                    for frame in page.frames:
                        try:
                            body = frame.locator("body").inner_text(timeout=3000)
                        except Exception:
                            body = ""
                        frames.append({"url": frame.url, "phoenix": "PHOENIX TIME" in body})
                        if "PHOENIX TIME" in body:
                            stale_event = "ks_cfb_game_total_event_id=" in frame.url
                            ready = not stale_event
                    _beat(
                        "production-readiness",
                        {"attempt": attempt, "ready": ready, "stale_event": stale_event, "phoenix_day": phoenix_day},
                    )
                    if ready:
                        return {"attempts": attempt, "phoenix_day": phoenix_day, "frames": frames}
                finally:
                    context.close()
                time.sleep(20)
        finally:
            browser.close()
    raise Step8PostmergeCloseoutFailure("PUBLIC_PRODUCTION_DID_NOT_CONVERGE_WITHIN_540_SECONDS")


def _run_public_cert(root: Path) -> dict:
    _beat("public-cert-start", "390/430/768/1440 sequential")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "devsystem.cfb_game_total_mobile_production_step8_v1",
            "--base-url",
            PRODUCTION_URL,
            "--artifact-dir",
            "artifacts/cfb-game-total-step8-postmerge",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=900,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise Step8PostmergeCloseoutFailure("PUBLIC_CERT_FAILED:" + output[-16000:])
    if "CFB_GAME_TOTAL_STEP8_PUBLIC_GREEN" not in output:
        raise Step8PostmergeCloseoutFailure("PUBLIC_GREEN_MARKER_MISSING:" + output[-12000:])
    marker = "CFB_GAME_TOTAL_STEP8_PUBLIC_EVIDENCE="
    rows = [line for line in (proc.stdout or "").splitlines() if line.startswith(marker)]
    if not rows:
        raise Step8PostmergeCloseoutFailure("PUBLIC_EVIDENCE_MISSING")
    evidence = json.loads(rows[-1][len(marker):])
    viewports = evidence.get("viewports") or {}
    if set(viewports) != {"mobile390", "mobile430", "tablet", "desktop"}:
        raise Step8PostmergeCloseoutFailure("PUBLIC_VIEWPORT_SET_DRIFT")
    for name, row in viewports.items():
        p1 = row.get("page1") or {}
        p2 = row.get("page2") or {}
        if p1.get("horizontal_overflow") is not False or p2.get("horizontal_overflow") is not False:
            raise Step8PostmergeCloseoutFailure("PUBLIC_OVERFLOW:" + name)
        if p2.get("all_required_visible") is not True:
            raise Step8PostmergeCloseoutFailure("PUBLIC_PAGE2_SURFACE_MISSING:" + name)
        if not p1.get("exact_event_id") or p1.get("exact_event_id") != p2.get("exact_event_id"):
            raise Step8PostmergeCloseoutFailure("PUBLIC_EVENT_IDENTITY_DRIFT:" + name)
    if int(evidence.get("github_actions_fallback") or 0) != 0:
        raise Step8PostmergeCloseoutFailure("ACTIONS_FALLBACK_ENABLED")
    _beat("public-cert-green", {"viewports": sorted(viewports), "phoenix_date": evidence.get("phoenix_date")})
    return evidence


def _public_evidence() -> dict:
    with tempfile.TemporaryDirectory(prefix="cfb-step8-final-") as tmp:
        root = Path(tmp) / "repo"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "main", REPO, str(root)],
            text=True,
            capture_output=True,
            timeout=120,
        )
        if clone.returncode != 0:
            raise Step8PostmergeCloseoutFailure("CLONE_FAILED:" + (clone.stderr or clone.stdout)[-4000:])
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != MAIN_SHA:
            raise Step8PostmergeCloseoutFailure("CLONED_MAIN_DRIFT:" + head)
        _beat("merged-main-clone-green", head)
        _ensure_chromium(root)
        readiness = _production_ready(root)
        evidence = _run_public_cert(root)
        evidence["production_readiness"] = readiness
        evidence["merged_main_sha"] = MAIN_SHA
        return evidence


def _build_final_registry(registry: dict, merged_tree: dict, premerge: dict) -> dict:
    updated = deepcopy(registry)
    step8_rows = [row for row in updated.get("active_thaws", []) if row.get("thaw_id") == THAW_ID]
    if len(step8_rows) != 1:
        raise Step8PostmergeCloseoutFailure("STEP8_THAW_RETIRE_COUNT_DRIFT")
    updated["active_thaws"] = [row for row in updated.get("active_thaws", []) if row.get("thaw_id") != THAW_ID]
    if {str(row.get("thaw_id") or "") for row in updated["active_thaws"]} != OTHER_THAWS:
        raise Step8PostmergeCloseoutFailure("UNRELATED_THAW_RETIRE_DRIFT")

    step6 = (updated.get("entries") or {}).get(STEP6_FREEZE_TOKEN)
    if not isinstance(step6, dict):
        raise Step8PostmergeCloseoutFailure("STEP6_FREEZE_ENTRY_MISSING")
    step6_artifacts = step6.get("artifacts") or {}
    if str(step6_artifacts.get(FROZEN_PATH) or "") != FROM_BLOB:
        raise Step8PostmergeCloseoutFailure("STEP6_V43_FROM_BLOB_DRIFT")
    step6_artifacts[FROZEN_PATH] = TO_BLOB

    freeze_artifacts = {path: str(merged_tree.get(path) or "") for path in premerge.get("artifact_map", {})}
    if any(not blob for blob in freeze_artifacts.values()):
        raise Step8PostmergeCloseoutFailure("FINAL_FREEZE_ARTIFACT_MISSING")
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }
    existing = (updated.get("entries") or {}).get(FREEZE_TOKEN)
    if existing is not None and existing != exact_entry:
        raise Step8PostmergeCloseoutFailure("FINAL_FREEZE_TOKEN_COLLISION")
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated["source_main_sha"] = MAIN_SHA
    updated["revision"] = int(registry["revision"]) + 1
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(_payload_without_hash(updated))
    validate_registry(updated)
    return updated


def _release_lease(client, expected_lease: dict, lease_id: str) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_REF)
    current = validate_scope_state(_decode_json(raw, "LEASE_RELEASE"))
    if current != expected_lease:
        raise Step8PostmergeCloseoutFailure("LEASE_CHANGED_DURING_FINALIZATION")
    released = release_scope(
        current,
        owner_id=LEASE_OWNER,
        lease_id=lease_id,
        expected_revision=int(current["revision"]),
        expected_state_hash=str(current["state_hash"]),
    )
    if released["result"].get("allowed") is not True:
        raise Step8PostmergeCloseoutFailure("LEASE_RELEASE_BLOCKED")
    state = released["state"]
    client.update_content(
        LEASE_PATH,
        _json_text(state),
        LEASE_REF,
        "lease: release CFB Game Total Step 8 after final production freeze",
        raw["sha"],
    )
    readback = validate_scope_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_REF), "LEASE_READBACK"))
    if [row for row in readback.get("holders", []) if row.get("owner_id") == LEASE_OWNER]:
        raise Step8PostmergeCloseoutFailure("LEASE_RELEASE_READBACK_FAILED")
    return readback


def _ensure_merged_receipt(client, *, premerge: dict, registry_before: dict, registry_after: dict, public: dict, reuse: dict, merged_tree: dict) -> dict:
    path = f"{RECEIPT_BASE}/{MERGED_PROOF_ID}.json"
    existing = client.content(path, ref=RECEIPT_REF, allow_404=True)
    if existing:
        receipt = _decode_json(existing, "MERGED_RECEIPT")
        validate_runless_receipt(receipt)
        return receipt
    public_digest = hashlib.sha256(
        json.dumps(public, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    receipt = build_runless_receipt(
        proof_id=MERGED_PROOF_ID,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="8/8",
        candidate_sha=MAIN_SHA,
        artifact_map={path: str(merged_tree.get(path) or "") for path in premerge["artifact_map"]},
        dependency_map={path: str(merged_tree.get(path) or "") for path in premerge["dependency_map"]},
        registry_before=_summary(registry_before),
        registry_after=_summary(registry_after),
        evidence_digests=list(premerge.get("evidence_digests") or []) + [public_digest],
        failure_class="NONE",
        prior_digest=PREMERGE_DIGEST,
        proof_fingerprint=str(premerge.get("proof_fingerprint") or ""),
        reused_from_proof_id=PREMERGE_PROOF_ID,
        reused_from_receipt_digest=PREMERGE_DIGEST,
        reuse_content_fingerprint=str(reuse.get("content_fingerprint") or ""),
        static_evidence_reexecuted=False,
        github_actions_enabled=False,
    )
    client.put_content(
        path,
        _json_text(receipt),
        RECEIPT_REF,
        "runless: persist CFB Game Total Step 8 merged-main final receipt",
    )
    return receipt


def _publish_and_verify_gate(client, receipt: dict) -> int:
    publish_gate(client, MAIN_SHA, "success", receipt)
    runs = client.request(
        "GET",
        f"/commits/{MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    expected = "receipt=" + str(receipt["digest"])
    for run in runs.get("check_runs", []):
        output = run.get("output") or {}
        if (
            run.get("head_sha") == MAIN_SHA
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and str(output.get("summary") or "") == expected
        ):
            return int(run["id"])
    raise Step8PostmergeCloseoutFailure("MERGED_GATE_READBACK_FAILED")


def execute(app) -> dict:
    client = app.state.github_client
    registry_before, lease_before, lease_id = _assert_main_and_control_state(client)
    premerge = _load_premerge(client)
    merged_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE_SHA)
    if {path: str(candidate_tree.get(path) or "") for path in premerge["artifact_map"]} != dict(premerge["artifact_map"]):
        raise Step8PostmergeCloseoutFailure("CANDIDATE_ARTIFACT_RECEIPT_DRIFT")
    if {path: str(candidate_tree.get(path) or "") for path in premerge["dependency_map"]} != dict(premerge["dependency_map"]):
        raise Step8PostmergeCloseoutFailure("CANDIDATE_DEPENDENCY_RECEIPT_DRIFT")
    merged_artifacts = {path: str(merged_tree.get(path) or "") for path in premerge["artifact_map"]}
    merged_dependencies = {path: str(merged_tree.get(path) or "") for path in premerge["dependency_map"]}
    candidate_plan = _decode_json(client.content(PREMERGE_PLAN_PATH, ref=SOURCE_CANDIDATE_SHA), "CANDIDATE_PLAN")
    merged_plan = _decode_json(client.content(PREMERGE_PLAN_PATH, ref=MAIN_SHA), "MERGED_PLAN")
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
        raise Step8PostmergeCloseoutFailure("POSTMERGE_REUSE_REJECTED:" + ",".join(reuse.get("reasons") or []))
    if reuse.get("static_evidence_reexecuted") is not False or reuse.get("github_actions_enabled") is not False:
        raise Step8PostmergeCloseoutFailure("POSTMERGE_REUSE_POLICY_DRIFT")
    _beat("receipt-reuse-green", {"proof": PREMERGE_PROOF_ID, "static_reexecuted": False})

    public = _public_evidence()
    final_registry = _build_final_registry(registry_before, merged_tree, premerge)
    backend = GithubRegistryBackend(client)
    client.update_content(
        REGISTRY_PATH,
        _json_text(final_registry),
        backend.branch,
        "registry: freeze CFB Game Total Step 8 mobile production final",
        backend._blob_sha,
    )
    registry_readback = backend.read_registry()
    validate_registry(registry_readback)
    if registry_readback != final_registry:
        raise Step8PostmergeCloseoutFailure("REGISTRY_READBACK_MISMATCH")
    _beat("registry-frozen", _summary(registry_readback))

    lease_readback = _release_lease(client, lease_before, lease_id)
    _beat("lease-released", {"lease_id": lease_id, "revision": lease_readback["revision"], "holders": len(lease_readback.get("holders", []))})

    receipt = _ensure_merged_receipt(
        client,
        premerge=premerge,
        registry_before=registry_before,
        registry_after=registry_readback,
        public=public,
        reuse=reuse,
        merged_tree=merged_tree,
    )
    gate_id = _publish_and_verify_gate(client, receipt)
    return {
        "status": "GREEN",
        "decision": "CFB_GAME_TOTAL_STEP8_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "candidate_sha": SOURCE_CANDIDATE_SHA,
        "freeze_token": FREEZE_TOKEN,
        "public_status": "PUBLIC_GREEN",
        "public_viewports": sorted((public.get("viewports") or {}).keys()),
        "registry_revision": int(registry_readback["revision"]),
        "registry_state_hash": str(registry_readback["state_hash"]),
        "active_thaws": sorted(str(row.get("thaw_id") or "") for row in registry_readback.get("active_thaws", [])),
        "step8_thaw_retired": all(row.get("thaw_id") != THAW_ID for row in registry_readback.get("active_thaws", [])),
        "lease_released": not any(row.get("owner_id") == LEASE_OWNER for row in lease_readback.get("holders", [])),
        "merged_receipt_digest": str(receipt["digest"]),
        "merged_gate_id": gate_id,
        "static_evidence_reexecuted": False,
        "github_actions_fallback": 0,
        "step9_started": False,
    }


def install_startup(app):
    app.state.cfb_game_total_step8_postmerge_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_step8_postmerge_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_step8_postmerge_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:16000],
            }
        print(
            "CFB_GAME_TOTAL_STEP8_POSTMERGE_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_step8_postmerge_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
