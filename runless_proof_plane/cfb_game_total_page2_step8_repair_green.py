from __future__ import annotations

import hashlib
import json
import subprocess
from threading import Thread

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt

from .gate import publish_gate
from .receipts import GithubReceiptBackend, ReceiptStore
from .registry import GithubRegistryBackend
from .workspace import CandidateWorkspace

TASK_ID = "cfb-game-total-page2-step8-final-responsive-live-data"
WORKSTREAM = "cfb-game-total-page2-v1"
CANDIDATE_SHA = "d80ae6267fddd8e5999833158c532be0278a6ed5"
BASE_MAIN_SHA = "77934437d905295b7a21f324a3755999241c6b72"
ARTIFACTS = {
    "devsystem/cfb_game_total_page2_step8_live_cert_v1.py": "422b54320df359732499344794b4e1887cb14daa",
    "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py": "154760d34b4f33aed1efafdf2b026262eb0e332b",
    "tests/test_cfb_game_total_page2_step8_final_v1.py": "9c71f1d2393e4e1cd950fdcc2f6722662c3240bf",
}


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def execute(app) -> dict:
    client = app.state.github_client
    settings = app.state.settings
    if client.branch_sha("main") != BASE_MAIN_SHA:
        raise RuntimeError("STEP8_REPAIR_BASE_MAIN_DRIFT")
    tree = client.tree_blobs(CANDIDATE_SHA)
    for path, expected in ARTIFACTS.items():
        if tree.get(path) != expected:
            raise RuntimeError(f"STEP8_REPAIR_ARTIFACT_DRIFT:{path}:{tree.get(path)}:{expected}")

    token = client.auth.installation_token()
    repository_url = f"https://x-access-token@github.com/{settings.repository}.git"
    evidence = []
    with CandidateWorkspace(repository_url, CANDIDATE_SHA, token=token) as workspace:
        commands = [
            ["python", "-m", "pytest", "-q", "tests/test_cfb_game_total_page2_step8_final_v1.py"],
            ["python", "-m", "py_compile", "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py", "devsystem/cfb_game_total_page2_step8_live_cert_v1.py"],
        ]
        for command in commands:
            completed = subprocess.run(command, cwd=workspace.path, text=True, capture_output=True, timeout=240)
            row = {
                "command": command,
                "returncode": completed.returncode,
                "stdout": (completed.stdout or "")[-5000:],
                "stderr": (completed.stderr or "")[-3000:],
            }
            evidence.append(row)
            if completed.returncode != 0:
                raise RuntimeError("STEP8_REPAIR_STATIC_PROOF_FAILED:" + json.dumps(row, default=str))

    registry = GithubRegistryBackend(client).read_registry()
    registry_snapshot = {"revision": int(registry["revision"]), "state_hash": str(registry["state_hash"])}
    dependency_paths = (
        "app.py",
        "cfb_game_total_page2_step8_final_runtime_v1.py",
        "cfb_game_total_page2_step2_matchup_hero_phx_v1.py",
        "cfb_game_total_page2_step3_integrated_flow_v1.py",
        "cfb_game_total_page2_step4_outlook_summary_v1.py",
        "cfb_game_total_page2_step5_team_snapshot_key_drivers_v1.py",
        "cfb_game_total_page2_step6_trends_scoring_breakdown_v1.py",
        "cfb_game_total_page2_step7_line_lab_best_bet_v1.py",
        "streamlit_memory_lazy_router_v181.py",
    )
    dependency_map = {path: tree[path] for path in dependency_paths}
    proof_id = f"cfb-game-total-page2-step8-repair-{CANDIDATE_SHA[:16]}"
    receipt = build_runless_receipt(
        proof_id=proof_id,
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="8/8-postmerge-route-repair-premerge",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=dict(sorted(ARTIFACTS.items())),
        dependency_map=dependency_map,
        registry_before=registry_snapshot,
        registry_after=registry_snapshot,
        evidence_digests=[_digest(row) for row in evidence],
        failure_class="NONE",
        deployment_identity=settings.deployment_identity,
        github_actions_fallback=0,
        base_main_sha=BASE_MAIN_SHA,
    )
    store = ReceiptStore(
        GithubReceiptBackend(client, CANDIDATE_SHA, settings.receipt_ref, settings.receipt_path),
        settings.receipt_ref,
        settings.receipt_path,
    )
    receipt_path = f"{store.base_path}/{proof_id}.json"
    if store.backend.exists(receipt_path, store.ref):
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
        "base_main_sha": BASE_MAIN_SHA,
        "proof_id": proof_id,
        "receipt_digest": receipt["digest"],
        "artifact_count": len(ARTIFACTS),
        "evidence_count": len(evidence),
        "registry_revision": registry_snapshot["revision"],
        "registry_hash": registry_snapshot["state_hash"],
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_game_total_page2_step8_repair_green = {"status": "NOT_RUN"}

    def _run():
        try:
            result = execute(app)
        except Exception as exc:
            result = {"status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:7000]}
        app.state.cfb_game_total_page2_step8_repair_green = result
        print("CFB_GT_PAGE2_STEP8_REPAIR_GREEN=" + json.dumps(result, sort_keys=True, default=str), flush=True)

    @app.on_event("startup")
    def _start():
        Thread(target=_run, name="cfb-gt-page2-step8-repair-green", daemon=True).start()

    return app
