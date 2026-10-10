from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

from devsystem.frozen_artifact_registry_v1 import validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import (
    _hash as _lease_hash,
    release_scope,
    validate_state as validate_lease_state,
)

from .gate import publish_gate
from .receipts import GithubReceiptBackend, ReceiptStore
from .registry import GithubRegistryBackend, _state_hash
from .workspace import CandidateWorkspace

TASK_ID = "cfb-game-total-page2-step8-final-responsive-live-data"
WORKSTREAM = "cfb-game-total-page2-v1"
MAIN_SHA = "77934437d905295b7a21f324a3755999241c6b72"
PREMERGE_SHA = "09a5efc543e5f8c57f3ac6686bd34e5932ba3685"
PREMERGE_RECEIPT_DIGEST = "2de7bc5f80c6990fdf6692345e55b41faea6eed2a442dc8e4e8476beceb4113c"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP8_FINAL_RESPONSIVE_LIVE_DATA_FROZEN"
OWNER_ID = "api2-cfb-game-total-page2-step8-final-responsive-live-data"
LEASE_ID = "SCOPE-LEASE-49C270AAD437F764D45964F1"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
STEP8_THAW_ID = "THAW-CFB-GT-PAGE2-STEP8-APP-R1"
OLD_APP_BLOB = "b649282cd6fc771c6621cc09a655414f9422791a"
NEW_APP_BLOB = "426a53efd90b6e15149f78d1cb61acfb1e1195c3"
PRODUCTION_URL = "https://pickvault.streamlit.app"

ARTIFACT_MAP = {
    "app.py": "426a53efd90b6e15149f78d1cb61acfb1e1195c3",
    "cfb_game_total_page2_step8_final_runtime_v1.py": "7033e96c9216dceec78ad4030ceaaf87567e6e13",
    "devsystem/cfb_game_total_page2_step8_live_cert_v1.py": "ec6ab14a27736c77a49f0c7c012db6829e7d8eed",
    "devsystem/execution_plans/cfb-game-total-page2-step8-final-responsive-live-data.json": "e1b3bb8bbca106e3520af8fa585871fd89398eec",
    "devsystem/runless_proof_plans/cfb-game-total-page2-step8-final-responsive-live-data.json": "22c7bb6e7731cf72e5e24ec36645bd0cd72b9451",
    "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py": "fff6cd3aa44f25fe9ff78efdb1c837b548172167",
    "tests/test_cfb_game_total_page2_step8_final_v1.py": "5c1af30e206cca63794efb9a19ec8b0730db9b80",
}

DEPENDENCY_PATHS = (
    "cfb_game_total_clean_page_v38.py",
    "cfb_game_total_page2_step2_matchup_hero_phx_v1.py",
    "cfb_game_total_page2_step3_integrated_flow_v1.py",
    "cfb_game_total_page2_step4_outlook_summary_v1.py",
    "cfb_game_total_page2_step5_team_snapshot_key_drivers_v1.py",
    "cfb_game_total_page2_step6_trends_scoring_breakdown_v1.py",
    "cfb_game_total_page2_step7_line_lab_best_bet_v1.py",
    "streamlit_memory_lazy_router_v190.py",
)


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _decode_json(raw: dict, error: str) -> dict:
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(error)
    try:
        return json.loads(base64.b64decode(raw["content"]).decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(error) from exc


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assert_main_and_artifacts(client) -> dict[str, str]:
    observed_main = client.branch_sha("main")
    if observed_main != MAIN_SHA:
        raise RuntimeError(f"PAGE2_STEP8_MAIN_DRIFT:{observed_main}")
    tree = client.tree_blobs(MAIN_SHA)
    for path, expected_blob in ARTIFACT_MAP.items():
        observed = tree.get(path)
        if observed != expected_blob:
            raise RuntimeError(f"PAGE2_STEP8_ARTIFACT_DRIFT:{path}:{observed}:{expected_blob}")
    for path in DEPENDENCY_PATHS:
        if path not in tree:
            raise RuntimeError(f"PAGE2_STEP8_DEPENDENCY_MISSING:{path}")
    return tree


def _run_live_cert(app) -> dict:
    client = app.state.github_client
    settings = app.state.settings
    token = client.auth.installation_token()
    repository_url = f"https://x-access-token@github.com/{settings.repository}.git"
    with CandidateWorkspace(repository_url, MAIN_SHA, token=token) as workspace:
        artifact_dir = workspace.path / "artifacts" / "cfb-game-total-page2-step8"
        code = (
            "from devsystem import cfb_game_total_page2_step8_live_cert_v1 as cert; "
            f"cert.EXPECTED_MAIN_SHA={MAIN_SHA!r}; "
            f"cert.run(base_url={PRODUCTION_URL!r}, artifact_dir={str(artifact_dir)!r})"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=workspace.path,
            text=True,
            capture_output=True,
            timeout=540,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "")[-5000:]
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_FAILED:" + detail)
        evidence_path = artifact_dir / "cfb_game_total_page2_step8_live_cert.json"
        if not evidence_path.exists():
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_EVIDENCE_MISSING")
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence.get("status") != "GREEN" or evidence.get("source_main_sha") != MAIN_SHA:
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_IDENTITY_MISMATCH")
        viewports = evidence.get("viewports") or {}
        if set(viewports) != {"mobile390", "mobile430", "tablet", "desktop"}:
            raise RuntimeError("PAGE2_STEP8_LIVE_CERT_VIEWPORT_MISMATCH")
        return evidence


def _freeze_and_reconcile(client) -> tuple[dict, dict, int]:
    backend = GithubRegistryBackend(client)
    before = backend.read_registry()
    before_snapshot = {"revision": int(before["revision"]), "state_hash": str(before["state_hash"])}

    existing_token = (before.get("entries") or {}).get(FREEZE_TOKEN)
    step8_thaw = next((g for g in before.get("active_thaws", []) if g.get("thaw_id") == STEP8_THAW_ID), None)

    already_frozen = (
        existing_token is not None
        and existing_token.get("status") == "FROZEN"
        and existing_token.get("source_main_sha") == MAIN_SHA
        and existing_token.get("artifacts") == ARTIFACT_MAP
        and step8_thaw is None
        and before.get("source_main_sha") == MAIN_SHA
    )
    if already_frozen:
        for entry in (before.get("entries") or {}).values():
            blob = (entry.get("artifacts") or {}).get("app.py")
            if blob is not None and blob != NEW_APP_BLOB:
                raise RuntimeError("PAGE2_STEP8_APP_BASELINE_NOT_RECONCILED")
        return before_snapshot, {"revision": int(before["revision"]), "state_hash": str(before["state_hash"])}, 0

    if not step8_thaw:
        raise RuntimeError("PAGE2_STEP8_EXACT_THAW_MISSING")
    expected_pair = {"from_blob": OLD_APP_BLOB, "to_blob": NEW_APP_BLOB}
    if (
        step8_thaw.get("status") != "ACTIVE"
        or step8_thaw.get("target_head_sha") != PREMERGE_SHA
        or (step8_thaw.get("files") or {}).get("app.py") != expected_pair
        or len(step8_thaw.get("files") or {}) != 1
    ):
        raise RuntimeError("PAGE2_STEP8_EXACT_THAW_DRIFT")

    updated = deepcopy(before)
    updated["revision"] = int(before["revision"]) + 1
    updated["source_main_sha"] = MAIN_SHA

    reconciled = 0
    for checkpoint, entry in updated["entries"].items():
        artifacts = entry.get("artifacts") or {}
        if "app.py" not in artifacts:
            continue
        blob = artifacts["app.py"]
        if blob == OLD_APP_BLOB:
            artifacts["app.py"] = NEW_APP_BLOB
            reconciled += 1
        elif blob != NEW_APP_BLOB:
            raise RuntimeError(f"PAGE2_STEP8_APP_BASELINE_CONFLICT:{checkpoint}:{blob}")

    updated["active_thaws"] = [
        deepcopy(g) for g in before.get("active_thaws", []) if g.get("thaw_id") != STEP8_THAW_ID
    ]
    if any("app.py" in (g.get("files") or {}) for g in updated["active_thaws"]):
        raise RuntimeError("PAGE2_STEP8_REMAINING_APP_THAW_CONFLICT")

    current = updated["entries"].get(FREEZE_TOKEN)
    expected_entry = {
        "status": "FROZEN",
        "checkpoint_id": FREEZE_TOKEN,
        "source_main_sha": MAIN_SHA,
        "artifacts": dict(sorted(ARTIFACT_MAP.items())),
    }
    if current is None:
        updated["entries"][FREEZE_TOKEN] = expected_entry
    elif current != expected_entry:
        raise RuntimeError("PAGE2_STEP8_FREEZE_TOKEN_CONFLICT")

    updated["state_hash"] = _state_hash(updated)
    validate_registry(updated)
    if not backend._blob_sha:
        raise RuntimeError("PAGE2_STEP8_REGISTRY_BLOB_MISSING")
    client.update_content(
        backend.path,
        json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        backend.branch,
        f"registry: freeze {FREEZE_TOKEN} and reconcile app baseline",
        backend._blob_sha,
    )
    after = backend.read_registry()
    entry = (after.get("entries") or {}).get(FREEZE_TOKEN)
    if entry != expected_entry or after.get("source_main_sha") != MAIN_SHA:
        raise RuntimeError("PAGE2_STEP8_REGISTRY_READBACK_MISMATCH")
    if any(g.get("thaw_id") == STEP8_THAW_ID for g in after.get("active_thaws", [])):
        raise RuntimeError("PAGE2_STEP8_THAW_RELEASE_READBACK_MISMATCH")
    for checkpoint, old_entry in after["entries"].items():
        blob = (old_entry.get("artifacts") or {}).get("app.py")
        if blob is not None and blob != NEW_APP_BLOB:
            raise RuntimeError(f"PAGE2_STEP8_APP_READBACK_CONFLICT:{checkpoint}:{blob}")
    return before_snapshot, {"revision": int(after["revision"]), "state_hash": str(after["state_hash"])}, reconciled


def _publish_merged_main_gate(app, tree: dict[str, str], registry_before: dict, registry_after: dict, live_evidence: dict) -> dict:
    client = app.state.github_client
    settings = app.state.settings
    dependency_map = {path: tree[path] for path in DEPENDENCY_PATHS}
    proof_id = f"cfb-game-total-page2-step8-postmerge-{MAIN_SHA[:16]}"
    live_digest = _digest(live_evidence)
    receipt = build_runless_receipt(
        proof_id=proof_id,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="8/8-postmerge-live-freeze",
        candidate_sha=MAIN_SHA,
        artifact_map=dict(sorted(ARTIFACT_MAP.items())),
        dependency_map=dependency_map,
        registry_before=registry_before,
        registry_after=registry_after,
        evidence_digests=[PREMERGE_RECEIPT_DIGEST, live_digest, registry_after["state_hash"]],
        failure_class="NONE",
        deployment_identity=settings.deployment_identity,
        prior_digest=PREMERGE_RECEIPT_DIGEST,
        premerge_candidate_sha=PREMERGE_SHA,
        github_actions_fallback=0,
        freeze_token=FREEZE_TOKEN,
    )
    store = ReceiptStore(
        GithubReceiptBackend(client, MAIN_SHA, settings.receipt_ref, settings.receipt_path),
        settings.receipt_ref,
        settings.receipt_path,
    )
    receipt_path = f"{store.base_path}/{proof_id}.json"
    if store.backend.exists(receipt_path, store.ref):
        stored = store.get(proof_id)
        if stored.get("digest") != receipt.get("digest"):
            raise RuntimeError("PAGE2_STEP8_POSTMERGE_RECEIPT_CONFLICT")
        receipt = stored
    else:
        store.put(receipt)
    publish_gate(client, MAIN_SHA, "success", receipt, settings.gate_name)
    return {"receipt": receipt, "live_digest": live_digest}


def _release_step8_lease(client) -> dict:
    raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    current = validate_lease_state(_decode_json(raw, "PAGE2_STEP8_LEASE_READ_FAILED"))
    holder = next(
        (h for h in current.get("holders", []) if h.get("owner_id") == OWNER_ID and h.get("lease_id") == LEASE_ID),
        None,
    )
    if holder is not None:
        outcome = release_scope(
            current,
            owner_id=OWNER_ID,
            lease_id=LEASE_ID,
            expected_revision=int(current["revision"]),
            expected_state_hash=str(current["state_hash"]),
        )
        if outcome["result"].get("decision") != "SCOPE_LEASE_RELEASED" or outcome["result"].get("allowed") is not True:
            raise RuntimeError("PAGE2_STEP8_LEASE_RELEASE_FAILED:" + str(outcome["result"].get("decision")))
        updated = outcome["state"]
        decision = "SCOPE_LEASE_RELEASED"
    else:
        updated = deepcopy(current)
        decision = "SCOPE_LEASE_ALREADY_RELEASED"

    now = datetime.now(timezone.utc)
    kept = [h for h in updated.get("holders", []) if now < _utc(h["expires_at_utc"])]
    expired_pruned = len(updated.get("holders", [])) - len(kept)
    state_changed = holder is not None or expired_pruned > 0
    if expired_pruned:
        updated["holders"] = kept
        updated.pop("state_hash", None)
        updated["state_hash"] = _lease_hash(updated)
        updated = validate_lease_state(updated)

    if state_changed:
        client.update_content(
            LEASE_PATH,
            json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            LEASE_BRANCH,
            f"lease: release {LEASE_ID} and prune expired holders",
            raw["sha"],
        )

    readback_raw = client.content(LEASE_PATH, ref=LEASE_BRANCH)
    readback = validate_lease_state(_decode_json(readback_raw, "PAGE2_STEP8_LEASE_READBACK_FAILED"))
    if any(h.get("lease_id") == LEASE_ID for h in readback.get("holders", [])):
        raise RuntimeError("PAGE2_STEP8_LEASE_READBACK_MISMATCH")
    live_holders = [h for h in readback.get("holders", []) if now < _utc(h["expires_at_utc"])]
    return {
        "decision": decision,
        "allowed": True,
        "revision": int(readback["revision"]),
        "state_hash": str(readback["state_hash"]),
        "remaining_holders": len(readback.get("holders", [])),
        "remaining_live_holders": len(live_holders),
        "expired_pruned": expired_pruned,
    }


def execute(app) -> dict:
    client = app.state.github_client
    tree = _assert_main_and_artifacts(client)
    live = _run_live_cert(app)
    registry_before, registry_after, reconciled_app_entries = _freeze_and_reconcile(client)
    published = _publish_merged_main_gate(app, tree, registry_before, registry_after, live)
    lease = _release_step8_lease(client)
    event_ids = sorted({str((row or {}).get("exact_event_id") or "") for row in (live.get("viewports") or {}).values()})
    return {
        "status": "GREEN_FROZEN",
        "step": "8/8",
        "main_sha": MAIN_SHA,
        "premerge_candidate_sha": PREMERGE_SHA,
        "premerge_receipt_digest": PREMERGE_RECEIPT_DIGEST,
        "merged_main_receipt_digest": published["receipt"]["digest"],
        "live_evidence_digest": published["live_digest"],
        "live_event_ids": event_ids,
        "live_viewports_green": sorted((live.get("viewports") or {}).keys()),
        "freeze_token": FREEZE_TOKEN,
        "registry_revision": registry_after["revision"],
        "registry_hash": registry_after["state_hash"],
        "reconciled_app_entries": reconciled_app_entries,
        "step8_thaw_released": True,
        "lease_released": lease.get("allowed") is True,
        "lease_decision": lease.get("decision"),
        "lease_revision": lease.get("revision"),
        "lease_hash": lease.get("state_hash"),
        "remaining_lease_holders": lease.get("remaining_holders"),
        "remaining_live_lease_holders": lease.get("remaining_live_holders"),
        "expired_lease_holders_pruned": lease.get("expired_pruned"),
        "github_actions_enabled": False,
        "github_actions_fallback": 0,
        "page1_product_files_modified_after_merge": 0,
        "step2_through_step7_files_modified_after_merge": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step8_final = {"status": "NOT_RUN"}

    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:5000]}
        app.state.cfb_game_total_page2_step8_final = result
        print("CFB_GT_PAGE2_STEP8_FINAL=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _start_background_finalizer():
        Thread(target=_run, name="cfb-gt-page2-step8-finalizer", daemon=True).start()

    return app
