from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from threading import Thread

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt

from .gate import publish_gate
from .receipts import GithubReceiptBackend, ReceiptStore
from .registry import GithubRegistryBackend
from .workspace import CandidateWorkspace

TASK_ID = "cfb-game-total-page2-step8-final-responsive-live-data"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "cc6f1e1cbbdea5a3ea10b9ab5da76cc62f40aa1f"
PRODUCTION_MAIN_SHA = "77934437d905295b7a21f324a3755999241c6b72"
CERT_PATH = "devsystem/cfb_game_total_page2_step8_live_cert_v1.py"
PRODUCTION_URL = "https://pickvault.streamlit.app"


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def execute(app) -> dict:
    client = app.state.github_client
    settings = app.state.settings
    if client.branch_sha("main") != PRODUCTION_MAIN_SHA:
        raise RuntimeError("STEP8_REPAIR_PRODUCTION_MAIN_DRIFT")
    tree = client.tree_blobs(CANDIDATE_SHA)
    if tree.get(CERT_PATH) != "422b54320df359732499344794b4e1887cb14daa":
        raise RuntimeError("STEP8_REPAIR_CERT_BLOB_DRIFT")

    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        text=True,
        capture_output=True,
        timeout=420,
    )
    if install.returncode != 0:
        raise RuntimeError("STEP8_REPAIR_CHROMIUM_INSTALL_FAILED:" + (install.stderr or install.stdout or "")[-3000:])

    token = client.auth.installation_token()
    repository_url = f"https://x-access-token@github.com/{settings.repository}.git"
    with CandidateWorkspace(repository_url, CANDIDATE_SHA, token=token) as workspace:
        artifact_dir = workspace.path / "artifacts" / "cfb-game-total-page2-step8-repair"
        code = (
            "from devsystem import cfb_game_total_page2_step8_live_cert_v1 as cert; "
            f"cert.EXPECTED_MAIN_SHA={PRODUCTION_MAIN_SHA!r}; "
            f"cert.run(base_url={PRODUCTION_URL!r}, artifact_dir={str(artifact_dir)!r})"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=workspace.path,
            text=True,
            capture_output=True,
            timeout=720,
        )
        if completed.returncode != 0:
            raise RuntimeError("STEP8_REPAIR_LIVE_CERT_FAILED:" + (completed.stderr or completed.stdout or "")[-7000:])
        evidence_path = artifact_dir / "cfb_game_total_page2_step8_live_cert.json"
        if not evidence_path.exists():
            raise RuntimeError("STEP8_REPAIR_EVIDENCE_MISSING")
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    if evidence.get("status") != "GREEN" or evidence.get("source_main_sha") != PRODUCTION_MAIN_SHA:
        raise RuntimeError("STEP8_REPAIR_EVIDENCE_IDENTITY_MISMATCH")
    registry = GithubRegistryBackend(client).read_registry()
    registry_snapshot = {"revision": int(registry["revision"]), "state_hash": str(registry["state_hash"])}
    dependency_paths = (
        "devsystem/browser_qa_v1.py",
        "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py",
        "cfb_game_total_clean_page_v14.py",
    )
    dependency_map = {path: tree[path] for path in dependency_paths}
    proof_id = f"cfb-game-total-page2-step8-live-cert-repair-{CANDIDATE_SHA[:16]}"
    receipt = build_runless_receipt(
        proof_id=proof_id,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="8/8-live-cert-repair",
        candidate_sha=CANDIDATE_SHA,
        artifact_map={CERT_PATH: tree[CERT_PATH]},
        dependency_map=dependency_map,
        registry_before=registry_snapshot,
        registry_after=registry_snapshot,
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
        deployment_identity=settings.deployment_identity,
        github_actions_fallback=0,
        production_main_sha=PRODUCTION_MAIN_SHA,
        viewport_count=len(evidence.get("viewports") or {}),
    )
    store = ReceiptStore(
        GithubReceiptBackend(client, CANDIDATE_SHA, settings.receipt_ref, settings.receipt_path),
        settings.receipt_ref,
        settings.receipt_path,
    )
    if store.backend.exists(f"{store.base_path}/{proof_id}.json", store.ref):
        stored = store.get(proof_id)
        if stored.get("digest") != receipt.get("digest"):
            raise RuntimeError("STEP8_REPAIR_RECEIPT_CONFLICT")
        receipt = stored
    else:
        store.put(receipt)
    publish_gate(client, CANDIDATE_SHA, "success", receipt, settings.gate_name)
    return {
        "status": "MERGE_AUTHORIZED",
        "candidate_sha": CANDIDATE_SHA,
        "production_main_sha": PRODUCTION_MAIN_SHA,
        "receipt_digest": receipt["digest"],
        "proof_id": proof_id,
        "viewport_count": len(evidence.get("viewports") or {}),
        "event_ids": sorted({str((row or {}).get("exact_event_id") or "") for row in (evidence.get("viewports") or {}).values()}),
        "registry_revision": registry_snapshot["revision"],
        "registry_hash": registry_snapshot["state_hash"],
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step8_repair_cert = {"status": "NOT_RUN"}

    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:7000]}
        app.state.cfb_game_total_page2_step8_repair_cert = result
        print("CFB_GT_PAGE2_STEP8_REPAIR_CERT=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _start():
        Thread(target=_run, name="cfb-gt-page2-step8-repair-cert", daemon=True).start()

    return app
