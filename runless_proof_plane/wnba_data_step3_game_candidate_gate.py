from __future__ import annotations

import base64
import hashlib
import json

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

MAIN_SHA = "3347f77f5b80f79e89a6bcbe675658b32ed52621"
BRANCH = "api2-wnba-data-step3-recent-form-h2h-r1"
CANDIDATE_SHA = "bd0e7d80900b5f5a64330ee0e2aced4fa501aac1"
PATH = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"
TEST_PATH = "tests/test_wnba_data_step3_player_shell_handoff.py"
FROM_BLOB = "6aeb31c68c9e4637aa87d50a70e381e283fc08f7"
TO_BLOB = "e058856a30fb29b6fa2af364b80ab5dbad695be8"
TEST_BLOB = "f7de54a226cc5373b3ec45e35f8392bd9ec16968"
THAW_ID = "THAW-API2-WNBA-DATA-STEP3-PLAYER-SHELL-HANDOFF-R1"
RED_DEPLOY = "dep-db35acrtqb8s73e7nc60"
GREEN_DEPLOY = "dep-db35eqbncjis73ehcd70"
PUBLIC_RED_DEPLOY = "dep-db2vj1e7bikc73b617tg"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")
EXPECTED_CHANGED = tuple(sorted((PATH, TEST_PATH)))


def _read_text(client, path: str, ref: str) -> tuple[str, str]:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _registry(client):
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    return payload


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_CANDIDATE_DRIFT")

    comparison = client.request("GET", f"/compare/{MAIN_SHA}...{CANDIDATE_SHA}") or {}
    changed = tuple(sorted(str(item.get("filename") or "") for item in comparison.get("files", [])))
    if changed != EXPECTED_CHANGED:
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_SCOPE_DRIFT:" + ",".join(changed))

    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != "bfaadb26eda176a291f95d61845829cdffcdd938":
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_MAIN_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != TO_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_RUNTIME_BLOB_DRIFT")
    if str(candidate_tree.get(TEST_PATH) or "") != TEST_BLOB:
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_TEST_BLOB_DRIFT")

    runtime, _ = _read_text(client, PATH, CANDIDATE_SHA)
    test, _ = _read_text(client, TEST_PATH, CANDIDATE_SHA)
    for token in (
        "original_go_to_game = navigation.go_to_game",
        "def _go_to_game_with_shell_handoff",
        "navigation.go_to_game = _go_to_game_with_shell_handoff",
        "navigation.go_to_game = original_go_to_game",
    ):
        if token not in runtime:
            raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_RUNTIME_TOKEN_MISSING:" + token)
    if "test_slate_game_navigation_emits_shell_handoff" not in test:
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_TEST_TOKEN_MISSING")

    registry = _registry(client)
    exact = {
        "thaw_id": THAW_ID,
        "status": "ACTIVE",
        "target_head_sha": CANDIDATE_SHA,
        "files": {PATH: {"from_blob": FROM_BLOB, "to_blob": TO_BLOB}},
    }
    matches = [grant for grant in registry.get("active_thaws", []) if grant.get("thaw_id") == THAW_ID]
    if matches != [exact]:
        raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_EXACT_THAW_MISSING")
    for grant in registry.get("active_thaws", []):
        if grant.get("thaw_id") != THAW_ID and PATH in (grant.get("files") or {}):
            raise RuntimeError("WNBA_DATA_STEP3_GAME_GATE_CONFLICTING_THAW")

    artifacts = {PATH: TO_BLOB, TEST_PATH: TEST_BLOB}
    evidence = {
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "changed_files": list(changed),
        "artifacts": artifacts,
        "thaw_id": THAW_ID,
        "public_red_deploy": PUBLIC_RED_DEPLOY,
        "public_red_result": "WNBA_STEP3_PUBLIC_PROOF_RC=1; Slate Game click fell to MLB shell",
        "focused_red_deploy": RED_DEPLOY,
        "focused_red_result": "WNBA_STEP3_GAME_HANDOFF_RED_RC=1",
        "green_proof_deploy": GREEN_DEPLOY,
        "green_result": "full Step3 shell handoff regression file GREEN; WNBA_STEP3_GAME_HANDOFF_GREEN_RC=0",
        "slate_game_navigation_intercept": "GREEN",
        "game_player_navigation_intercept": "GREEN",
        "projection_math_changed": False,
        "market_math_changed": False,
        "probability_changed": False,
        "qualification_changed": False,
        "ranking_changed": False,
        "sportsbook_changed": False,
        "other_sports_changed": 0,
        "github_actions_fallback": False,
    }
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step3-game-click-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step3-recent-form-h2h",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step3",
        step="3/3-slate-game-shell-handoff",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifacts,
        dependency_map={
            "base_main_sha": MAIN_SHA,
            "thaw_id": THAW_ID,
            "github_actions_fallback": False,
            "public_red_deploy": PUBLIC_RED_DEPLOY,
            "focused_red_deploy": RED_DEPLOY,
            "green_proof_deploy": GREEN_DEPLOY,
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
    app.state.wnba_data_step3_game_candidate_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_data_step3_game_candidate_gate = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step3_game_candidate_gate = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "WNBA_DATA_STEP3_GAME_CANDIDATE_GATE="
            + json.dumps(app.state.wnba_data_step3_game_candidate_gate, sort_keys=True),
            flush=True,
        )
    return app
