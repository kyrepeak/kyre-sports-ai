from __future__ import annotations

import base64
import hashlib
import json

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

MAIN_SHA = "51762ad9226b119626284655a90bd7ac7da80d5e"
BRANCH = "api2-wnba-data-step3-recent-form-h2h-r1"
CANDIDATE_SHA = "27fec905b022aaf819439c90496fb4d3b8c1452a"
PATH = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
TEST_PATH = "tests/test_wnba_data_step3_player_shell_handoff.py"
MAIN_BLOB = "deeb6a9de5270d2d3745c620129895b90ef2b688"
FROZEN_BLOB = "6aeb31c68c9e4637aa87d50a70e381e283fc08f7"
TO_BLOB = "7c5c8bee3299dae7faebc3d22953a2a1b9fa2dcc"
TEST_BLOB = "5195f99afdb638cae9f9068320610b3807ae781c"
THAW_ID = "THAW-API2-WNBA-DATA-STEP3-PLAYER-SHELL-HANDOFF-R1"
RED_PROOF_DEPLOY = "dep-db2t7h8g6u5c73c7cgq0"
GREEN_PROOF_DEPLOY = "dep-db2theflk1mc738moe9g"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")
EXPECTED_CHANGED = tuple(sorted((PATH, TEST_PATH)))


def _read_text(client, path: str, ref: str) -> tuple[str, str]:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_GATE_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_GATE_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_GATE_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_GATE_CANDIDATE_DRIFT")

    comparison = client.request("GET", f"/compare/{MAIN_SHA}...{CANDIDATE_SHA}") or {}
    changed = tuple(sorted(str(item.get("filename") or "") for item in comparison.get("files", [])))
    if changed != EXPECTED_CHANGED:
        raise RuntimeError("WNBA_DATA_STEP3_GATE_SCOPE_DRIFT:" + ",".join(changed))

    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != MAIN_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_GATE_MAIN_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != TO_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_GATE_RUNTIME_BLOB_DRIFT")
    if str(candidate_tree.get(TEST_PATH) or "") != TEST_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_GATE_TEST_BLOB_DRIFT")

    runtime, _ = _read_text(client, PATH, CANDIDATE_SHA)
    test, _ = _read_text(client, TEST_PATH, CANDIDATE_SHA)
    for token in (
        "def _emit_one_shot_wnba_pra_shell_handoff",
        "def _wrap_step7_player_open(delegate):",
        "final_transport._open_player_immediate = _wrap_step7_player_open(original_final_player_open)",
        "final_transport._open_player_immediate = original_final_player_open",
    ):
        if token not in runtime:
            raise RuntimeError("WNBA_DATA_STEP3_GATE_CALLBACK_HANDOFF_MISSING:" + token)
    for token in (
        "test_explicit_player_transition_emits_one_shot_wnba_pra_shell_handoff",
        "test_passive_deep_rerender_does_not_reinject_one_shot_jump",
        "test_step7_player_callback_keeps_handoff_after_render_restores_module",
    ):
        if token not in test:
            raise RuntimeError("WNBA_DATA_STEP3_GATE_REGRESSION_MISSING:" + token)

    registry = _registry(client)
    exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROZEN_BLOB, "to_blob": TO_BLOB}},
    }
    matches = [grant for grant in registry.get("active_thaws", []) if grant.get("thaw_id") == THAW_ID]
    if matches != [exact]:
        raise RuntimeError("WNBA_DATA_STEP3_GATE_EXACT_THAW_MISSING")
    for grant in registry.get("active_thaws", []):
        if grant.get("thaw_id") != THAW_ID and PATH in (grant.get("files") or {}):
            raise RuntimeError("WNBA_DATA_STEP3_GATE_CONFLICTING_THAW")

    artifacts = {PATH: TO_BLOB, TEST_PATH: TEST_BLOB}
    evidence = {
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "changed_files": list(changed),
        "artifacts": artifacts,
        "thaw_id": THAW_ID,
        "red_public_proof_deploy": RED_PROOF_DEPLOY,
        "red_result": "WNBA_STEP3_PUBLIC_PROOF_RC=1; Game Center GREEN, Player shell fell back to MLB",
        "green_callback_proof_deploy": GREEN_PROOF_DEPLOY,
        "green_result": "WNBA_STEP3_HANDOFF_GREEN_RC=0",
        "callback_object_persistence_regression": "GREEN",
        "passive_rerender_pushstate_regression": "PRESERVED",
        "projection_math_changed": False,
        "market_math_changed": False,
        "probability_changed": False,
        "qualification_changed": False,
        "ranking_changed": False,
        "sportsbook_changed": False,
        "other_sports_changed": 0,
    }
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step3-player-shell-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step3-recent-form-h2h",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step3",
        step="3/3-player-shell-current-main-candidate",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifacts,
        dependency_map={
            "base_main_sha": MAIN_SHA,
            "thaw_id": THAW_ID,
            "github_actions_fallback": False,
            "red_public_proof_deploy": RED_PROOF_DEPLOY,
            "green_callback_proof_deploy": GREEN_PROOF_DEPLOY,
        },
        registry_before={
            "revision": int(registry["revision"]),
            "state_hash": str(registry["state_hash"]),
            "active_thaw": THAW_ID,
        },
        registry_after={"mode": "candidate_gate_only", "registry_mutated": False},
        evidence_digests=[digest],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": int(check["id"]),
        "receipt": str(receipt["digest"]),
        "registry_revision": int(registry["revision"]),
        "registry_state_hash": str(registry["state_hash"]),
        "thaw_id": THAW_ID,
        "changed_files": list(changed),
    }


def install_startup(app):
    app.state.wnba_data_step3_player_shell_candidate_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_data_step3_player_shell_candidate_gate = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step3_player_shell_candidate_gate = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "WNBA_DATA_STEP3_PLAYER_SHELL_CANDIDATE_GATE="
            + json.dumps(app.state.wnba_data_step3_player_shell_candidate_gate, sort_keys=True),
            flush=True,
        )
    return app
