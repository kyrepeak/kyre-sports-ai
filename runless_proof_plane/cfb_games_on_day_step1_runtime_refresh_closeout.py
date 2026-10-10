from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import time
from copy import deepcopy

from devsystem.api2_frozen_registry_lifecycle_v1 import plan_baseline_forward_port
from devsystem.frozen_artifact_registry_v1 import (
    _hash as registry_hash,
    _payload_without_hash,
    validate_registry,
)
from devsystem.runless_terminal_proof_receipt_v1 import (
    build_runless_receipt,
    validate_runless_receipt,
)
from devsystem.scope_aware_execution_lease_v1 import (
    release_scope,
    validate_state as validate_scope_lease_state,
)

from .gate import publish_gate
from .postmerge_reuse import evaluate_postmerge_reuse
from .registry import GithubRegistryBackend, REGISTRY_PATH

TASK_ID = "cfb-game-total-games-on-day-step1-runtime-refresh-r1"
WORKSTREAM = "cfb-game-total-games-on-day-v1"
SOURCE_MAIN_SHA = "60da7cbd5cf05413f2c9d8ce3e8921adb2f58648"
SOURCE_CANDIDATE_SHA = "b4ff5f9271e5e3f65dc8446ef62495ed1240502c"
MAIN_SHA = "f15fe559fdaab801deb77c43c6451bc811159fed"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-games-on-day-step1-runtime-refresh-r1.json"
PREMERGE_PROOF_ID = "cfb-game-total-games-on-day-step1-runtime-refresh-r1-b4ff5f9271e5e3f6-586b0fc06eef37de"
PREMERGE_DIGEST = "6b33640eb7a9adac7183c801ade005bc2c5817ad97f04533f06a9b8a3c96d507"
PREMERGE_CHECK_ID = 114151275171
MERGED_PROOF_ID = "cfb-game-total-games-on-day-step1-runtime-refresh-r1-f15fe559fdaab801-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_GAMES_ON_DAY_STEP1_CARD_LAYOUT_V1_FROZEN"
THAW_ID = "THAW-CFB-GT-GAMES-ON-DAY-STEP1-RUNTIME-REFRESH-R1"
LEASE_ID = "SCOPE-LEASE-AE8CAF232C64417062797456"
LEASE_OWNER = "api2-cfb-games-on-day-step1-runtime-refresh"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
RECEIPT_REF = "runless-proof-receipts"
RECEIPT_BASE = "devsystem/runless_proof_receipts"
FROZEN_PATH = "requirements.txt"
FROM_BLOB = "2904ed539d5a2e8a195675b96b756fb6ba6a3c74"
TO_BLOB = "1022d95a71b3c04aa5310b5057de74978e4cffa4"
PRODUCTION_URL = "https://pickvault.streamlit.app"
PRODUCTION_EVENT_ID = "401856824"
PRODUCTION_DATE = "2026-10-10"
FREEZE_PATHS = (
    "cfb_game_total_games_on_day_step1_layout_v1.py",
    "kyre_remaining_pages_theme_v1.py",
    "tests/test_cfb_game_total_games_on_day_step1_layout_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-games-on-day-step1-card-layout-v1.json",
    "devsystem/task_ledgers/cfb-game-total-games-on-day-step1-card-layout-v1.json",
    "requirements.txt",
    "tests/test_cfb_game_total_games_on_day_step1_runtime_refresh_v1.py",
    "devsystem/runless_proof_plans/cfb-game-total-games-on-day-step1-runtime-refresh-r1.json",
    "devsystem/task_ledgers/cfb-game-total-games-on-day-step1-runtime-refresh-r1.json",
)


class RuntimeRefreshCloseoutFailure(RuntimeError):
    pass


def _decode_json(raw: dict | None, label: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeRefreshCloseoutFailure(label + "_READ_FAILED")
    try:
        return json.loads(base64.b64decode(raw["content"]).decode())
    except Exception as exc:
        raise RuntimeRefreshCloseoutFailure(label + "_DECODE_FAILED") from exc


def _json_text(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


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
        "active_thaws": sorted(str(g.get("thaw_id") or "") for g in registry.get("active_thaws", [])),
    }


def _verify_merge(client) -> dict[str, str]:
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeRefreshCloseoutFailure("CLOSEOUT_MAIN_DRIFT")
    commit = client.commit(MAIN_SHA)
    parents = {str(item.get("sha") or "") for item in commit.get("parents", [])}
    if SOURCE_MAIN_SHA not in parents or SOURCE_CANDIDATE_SHA not in parents:
        raise RuntimeRefreshCloseoutFailure("CLOSEOUT_MERGE_LINEAGE_DRIFT")
    tree = client.tree_blobs(MAIN_SHA)
    if str(tree.get(FROZEN_PATH) or "") != TO_BLOB:
        raise RuntimeRefreshCloseoutFailure("CLOSEOUT_REQUIREMENTS_BLOB_DRIFT")
    return tree


def _load_premerge_receipt(client) -> dict:
    raw = client.content(f"{RECEIPT_BASE}/{PREMERGE_PROOF_ID}.json", ref=RECEIPT_REF)
    receipt = _decode_json(raw, "PREMERGE_RECEIPT")
    validate_runless_receipt(receipt)
    if receipt.get("proof_id") != PREMERGE_PROOF_ID:
        raise RuntimeRefreshCloseoutFailure("PREMERGE_PROOF_ID_DRIFT")
    if receipt.get("candidate_sha") != SOURCE_CANDIDATE_SHA:
        raise RuntimeRefreshCloseoutFailure("PREMERGE_CANDIDATE_DRIFT")
    if receipt.get("digest") != PREMERGE_DIGEST or receipt.get("failure_class") != "NONE":
        raise RuntimeRefreshCloseoutFailure("PREMERGE_RECEIPT_NOT_GREEN")
    return receipt


def _public_mobile_proof_subprocess() -> dict:
    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    if install.returncode != 0:
        raise RuntimeRefreshCloseoutFailure("PLAYWRIGHT_CHROMIUM_INSTALL_FAILED:" + install.stdout[-1600:])

    route = (
        PRODUCTION_URL.rstrip("/")
        + "/?ks_sport=College+Football&ks_cfb_market=Game+Total"
        + f"&ks_cfb_game_total_date={PRODUCTION_DATE}&ks_cfb_game_total_event_id={PRODUCTION_EVENT_ID}"
    )
    script = r'''
import json, time
from playwright.sync_api import sync_playwright
from devsystem import browser_qa_v1 as browser_qa

route = __ROUTE__
deadline = time.monotonic() + 420.0
attempts = 0
last = ""
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
    try:
        while time.monotonic() < deadline:
            attempts += 1
            page = browser.new_page(viewport={"width":390,"height":844})
            try:
                page.goto(route, wait_until="domcontentloaded", timeout=120000)
                frame, scans = browser_qa._find_app_frame(page)
                body = frame.locator("body").inner_text(timeout=30000)
                marker = frame.locator('style[data-kyre-cfb-games-on-day-step1-layout="v1"]')
                scroller = frame.locator(".gt163-game-scroller").first
                cards = frame.locator(".gt163-game-link,.gt163-game-disabled")
                selected = frame.locator(".gt163-game-link.selected")
                if marker.count() < 1 or scroller.count() < 1 or cards.count() < 1:
                    last = json.dumps({"marker":marker.count(),"scroller":scroller.count(),"cards":cards.count(),"body_has_games":"GAMES ON THIS DAY" in body.upper()})
                else:
                    styles = scroller.evaluate("el => { const s=getComputedStyle(el); return {display:s.display,gridTemplateColumns:s.gridTemplateColumns,overflowX:s.overflowX,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth}; }")
                    section_overflow = scroller.evaluate("el => el.scrollWidth > el.clientWidth + 3")
                    document_overflow = frame.evaluate("() => Math.max(document.documentElement.scrollWidth,document.body.scrollWidth) > document.documentElement.clientWidth + 3")
                    first = cards.first.bounding_box(); outer = scroller.bounding_box()
                    full_width = bool(first and outer and first["width"] >= outer["width"] - 4)
                    runtime_error = str(browser_qa._body_has_forbidden_error(body) or "")
                    if (
                        not runtime_error
                        and styles.get("display") == "grid"
                        and styles.get("overflowX") == "visible"
                        and not section_overflow
                        and not document_overflow
                        and full_width
                        and selected.count() == 1
                    ):
                        print("CFB_GAMES_ON_DAY_STEP1_RUNTIME_REFRESH_PUBLIC_PROOF=" + json.dumps({
                            "status":"GREEN","url":route,"page_url":page.url,"frame_url":frame.url,
                            "viewport":{"width":390,"height":844},"attempts":attempts,
                            "marker_count":marker.count(),"card_count":cards.count(),
                            "selected_card_count":selected.count(),"display":styles.get("display"),
                            "grid_template_columns":styles.get("gridTemplateColumns"),
                            "overflow_x":styles.get("overflowX"),"first_card_full_width":True,
                            "section_horizontal_overflow":False,"document_horizontal_overflow":False,
                            "runtime_error":"","frame_scan":scans,
                        }, sort_keys=True))
                        raise SystemExit(0)
                    last = json.dumps({"styles":styles,"section_overflow":section_overflow,"document_overflow":document_overflow,"full_width":full_width,"selected":selected.count(),"runtime_error":runtime_error})
            except SystemExit:
                raise
            except Exception as exc:
                last = f"{type(exc).__name__}:{str(exc)[:900]}"
            finally:
                page.close()
            time.sleep(10)
    finally:
        browser.close()
raise RuntimeError("PUBLIC_MOBILE_PROOF_TIMEOUT:" + last[:1500])
'''.replace("__ROUTE__", repr(route))
    completed = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=560,
        check=False,
    )
    marker = "CFB_GAMES_ON_DAY_STEP1_RUNTIME_REFRESH_PUBLIC_PROOF="
    line = next((row[len(marker):] for row in reversed(completed.stdout.splitlines()) if row.startswith(marker)), "")
    if completed.returncode != 0 or not line:
        raise RuntimeRefreshCloseoutFailure("PUBLIC_PROOF_SUBPROCESS_FAILED:" + completed.stdout[-2600:])
    payload = json.loads(line)
    if payload.get("status") != "GREEN":
        raise RuntimeRefreshCloseoutFailure("PUBLIC_PROOF_NOT_GREEN")
    return payload


def _ensure_merged_receipt_and_gate(client, *, tree: dict[str, str], premerge: dict, registry: dict) -> dict:
    candidate_plan = _decode_json(client.content(PLAN_PATH, ref=SOURCE_CANDIDATE_SHA), "CANDIDATE_PLAN")
    merged_plan = _decode_json(client.content(PLAN_PATH, ref=MAIN_SHA), "MERGED_PLAN")
    candidate_tree = client.tree_blobs(SOURCE_CANDIDATE_SHA)
    candidate_artifacts = {path: str(candidate_tree.get(path) or "") for path in premerge["artifact_map"]}
    candidate_dependencies = {path: str(candidate_tree.get(path) or "") for path in premerge["dependency_map"]}
    merged_artifacts = {path: str(tree.get(path) or "") for path in premerge["artifact_map"]}
    merged_dependencies = {path: str(tree.get(path) or "") for path in premerge["dependency_map"]}
    if candidate_artifacts != dict(premerge.get("artifact_map") or {}):
        raise RuntimeRefreshCloseoutFailure("CANDIDATE_ARTIFACT_RECEIPT_DRIFT")
    if candidate_dependencies != dict(premerge.get("dependency_map") or {}):
        raise RuntimeRefreshCloseoutFailure("CANDIDATE_DEPENDENCY_RECEIPT_DRIFT")

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
        raise RuntimeRefreshCloseoutFailure("POSTMERGE_REUSE_REJECTED:" + ",".join(reuse.get("reasons") or []))
    if reuse.get("static_evidence_reexecuted") is not False or reuse.get("github_actions_enabled") is not False:
        raise RuntimeRefreshCloseoutFailure("POSTMERGE_REUSE_POLICY_DRIFT")

    path = f"{RECEIPT_BASE}/{MERGED_PROOF_ID}.json"
    existing = client.content(path, ref=RECEIPT_REF, allow_404=True)
    if existing:
        merged = _decode_json(existing, "MERGED_RECEIPT")
        validate_runless_receipt(merged)
    else:
        merged = build_runless_receipt(
            proof_id=MERGED_PROOF_ID,
            task_id=TASK_ID,
            project="API2",
            workstream=WORKSTREAM,
            step="games-on-this-day-step1-runtime-refresh-closeout",
            candidate_sha=MAIN_SHA,
            artifact_map=merged_artifacts,
            dependency_map=merged_dependencies,
            registry_before=_registry_summary(registry),
            registry_after=_registry_summary(registry),
            evidence_digests=list(premerge.get("evidence_digests") or []),
            failure_class="NONE",
            prior_digest=PREMERGE_DIGEST,
            proof_fingerprint=str(premerge.get("proof_fingerprint") or ""),
            reused_from_proof_id=PREMERGE_PROOF_ID,
            reused_from_receipt_digest=PREMERGE_DIGEST,
            reuse_content_fingerprint=str(reuse.get("content_fingerprint") or ""),
            static_evidence_reexecuted=False,
            github_actions_enabled=False,
        )
        client.put_content(path, _json_text(merged), RECEIPT_REF, "runless: persist CFB Games on This Day Step 1 refresh merged receipt")
    if merged.get("candidate_sha") != MAIN_SHA or merged.get("prior_digest") != PREMERGE_DIGEST:
        raise RuntimeRefreshCloseoutFailure("MERGED_RECEIPT_IDENTITY_DRIFT")

    runs = client.request("GET", f"/commits/{MAIN_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100") or {}
    expected_summary = "receipt=" + str(merged["digest"])
    gate_published = True
    for run in runs.get("check_runs", []):
        output = run.get("output") or {}
        if run.get("head_sha") == MAIN_SHA and run.get("status") == "completed" and run.get("conclusion") == "success" and output.get("summary") == expected_summary:
            gate_published = False
            break
    if gate_published:
        publish_gate(client, MAIN_SHA, "success", merged)
    return {"receipt": merged, "reuse": reuse, "gate_published": gate_published}


def _read_registry_converged(backend: GithubRegistryBackend, *, expected_source: str, expected_token: str | None = None) -> dict:
    last = None
    for _ in range(6):
        last = backend.read_registry()
        validate_registry(last)
        source_ok = str(last.get("source_main_sha") or "") == expected_source
        token_ok = expected_token is None or (last.get("entries") or {}).get(expected_token) is not None
        if source_ok and token_ok:
            return last
        time.sleep(0.75)
    raise RuntimeRefreshCloseoutFailure("REGISTRY_READBACK_DID_NOT_CONVERGE:" + str((last or {}).get("source_main_sha") or ""))


def _atomic_forward_port_and_freeze(client, *, tree: dict[str, str]) -> dict:
    backend = GithubRegistryBackend(client)
    registry = backend.read_registry()
    validate_registry(registry)

    existing_entry = (registry.get("entries") or {}).get(FREEZE_TOKEN)
    if str(registry.get("source_main_sha") or "") == MAIN_SHA and existing_entry:
        if existing_entry.get("source_main_sha") != MAIN_SHA:
            raise RuntimeRefreshCloseoutFailure("EXISTING_FREEZE_MAIN_DRIFT")
        return {
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "freeze_token": FREEZE_TOKEN,
            "artifact_count": len(existing_entry.get("artifacts") or {}),
            "retired_thaw": THAW_ID,
            "already_frozen": True,
        }

    if str(registry.get("source_main_sha") or "") != SOURCE_MAIN_SHA:
        raise RuntimeRefreshCloseoutFailure("REGISTRY_SOURCE_MAIN_DRIFT")
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeRefreshCloseoutFailure("MAIN_MOVED_BEFORE_FREEZE")

    thaw_ids_before = [str(g.get("thaw_id") or "") for g in registry.get("active_thaws", [])]
    if THAW_ID not in thaw_ids_before:
        raise RuntimeRefreshCloseoutFailure("EXPECTED_REFRESH_THAW_MISSING")
    unrelated_before = [item for item in deepcopy(registry.get("active_thaws", [])) if item.get("thaw_id") != THAW_ID]

    plan = plan_baseline_forward_port(
        registry,
        updates={FROZEN_PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
        source_main_sha=MAIN_SHA,
    )
    updated = deepcopy(plan["registry"])
    if THAW_ID not in plan.get("retired_empty_thaw_grants", []):
        raise RuntimeRefreshCloseoutFailure("REFRESH_THAW_NOT_RETIRED")
    if updated.get("active_thaws", []) != unrelated_before:
        raise RuntimeRefreshCloseoutFailure("UNRELATED_THAW_DRIFT")

    freeze_artifacts = {path: str(tree.get(path) or "") for path in FREEZE_PATHS}
    if any(not blob for blob in freeze_artifacts.values()):
        raise RuntimeRefreshCloseoutFailure("FREEZE_ARTIFACT_MISSING")
    exact_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(freeze_artifacts.items())),
    }
    collision = (updated.get("entries") or {}).get(FREEZE_TOKEN)
    if collision is not None and collision != exact_entry:
        raise RuntimeRefreshCloseoutFailure("FREEZE_TOKEN_COLLISION")
    updated["entries"][FREEZE_TOKEN] = exact_entry
    updated.pop("state_hash", None)
    updated["state_hash"] = registry_hash(_payload_without_hash(updated))
    validate_registry(updated)

    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeRefreshCloseoutFailure("MAIN_MOVED_DURING_FREEZE")
    client.update_content(
        REGISTRY_PATH,
        _json_text(updated),
        backend.branch,
        "registry: freeze CFB Games on This Day Step 1 after runtime refresh",
        backend._blob_sha,
    )
    readback = _read_registry_converged(backend, expected_source=MAIN_SHA, expected_token=FREEZE_TOKEN)
    if (readback.get("entries") or {}).get(FREEZE_TOKEN) != exact_entry:
        raise RuntimeRefreshCloseoutFailure("FREEZE_READBACK_MISMATCH")
    if any(g.get("thaw_id") == THAW_ID for g in readback.get("active_thaws", [])):
        raise RuntimeRefreshCloseoutFailure("REFRESH_THAW_RETIRE_READBACK_MISMATCH")
    if readback.get("active_thaws", []) != unrelated_before:
        raise RuntimeRefreshCloseoutFailure("UNRELATED_THAW_READBACK_DRIFT")
    return {
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "freeze_token": FREEZE_TOKEN,
        "artifact_count": len(freeze_artifacts),
        "updated_prior_entries": len(plan.get("updated_entries") or []),
        "retired_thaw": THAW_ID,
        "unrelated_thaws_preserved": len(unrelated_before),
        "already_frozen": False,
    }


def _release_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    state = validate_scope_lease_state(_decode_json(raw, "LEASE"))
    matches = [h for h in state.get("holders", []) if h.get("lease_id") == LEASE_ID and h.get("owner_id") == LEASE_OWNER]
    if not matches:
        return {"released": False, "already_absent": True}
    if len(matches) != 1:
        raise RuntimeRefreshCloseoutFailure("LEASE_IDENTITY_DRIFT")
    released = release_scope(
        state,
        owner_id=LEASE_OWNER,
        lease_id=LEASE_ID,
        expected_revision=int(state["revision"]),
        expected_state_hash=str(state["state_hash"]),
    )
    if released["result"].get("allowed") is not True:
        raise RuntimeRefreshCloseoutFailure("LEASE_RELEASE_BLOCKED:" + str(released["result"].get("decision") or "UNKNOWN"))
    client.update_content(
        LEASE_PATH,
        _json_text(released["state"]),
        LEASE_BRANCH,
        "lease: release CFB Games on This Day Step 1 final scope",
        raw["sha"],
    )
    last = None
    for _ in range(6):
        last = validate_scope_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "LEASE_READBACK"))
        if not any(h.get("lease_id") == LEASE_ID for h in last.get("holders", [])):
            return {"released": True, "state_hash": str(last["state_hash"]), "remaining_holders": len(last.get("holders", []))}
        time.sleep(0.75)
    raise RuntimeRefreshCloseoutFailure("LEASE_RELEASE_READBACK_MISMATCH")


def execute(app):
    client = app.state.github_client
    tree = _verify_merge(client)
    premerge = _load_premerge_receipt(client)
    public = _public_mobile_proof_subprocess()
    registry = GithubRegistryBackend(client).read_registry()
    merged = _ensure_merged_receipt_and_gate(client, tree=tree, premerge=premerge, registry=registry)
    frozen = _atomic_forward_port_and_freeze(client, tree=tree)
    lease = _release_lease(client)
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeRefreshCloseoutFailure("MAIN_MOVED_AFTER_CLOSEOUT")
    return {
        "status": "GREEN",
        "decision": "CFB_GAMES_ON_DAY_STEP1_GREEN_FROZEN",
        "main_sha": MAIN_SHA,
        "source_candidate_sha": SOURCE_CANDIDATE_SHA,
        "premerge_receipt_digest": PREMERGE_DIGEST,
        "merged_receipt_digest": str(merged["receipt"]["digest"]),
        "public_mobile_proof": public,
        "public_mobile_proof_digest": _digest(public),
        "freeze": frozen,
        "lease": lease,
        "static_evidence_reexecuted": False,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step1_runtime_refresh_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step1_runtime_refresh_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step1_runtime_refresh_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:3200],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP1_RUNTIME_REFRESH_CLOSEOUT="
            + json.dumps(app.state.cfb_games_on_day_step1_runtime_refresh_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
