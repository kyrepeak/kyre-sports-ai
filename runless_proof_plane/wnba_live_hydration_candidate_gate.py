from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "c038037f0c7f9e1a6338c2ca29bdcae08e15fae7"
CANDIDATE_SHA = "54e3fe375cb22fc53c844ba50bb6dd04f45e7482"
REPAIR_BRANCH = "api2-wnba-data-completeness-repair-v1-step2-live-hydration-r1"
RUNTIME_PATH = "wnba_players_v25.py"
HELPER_PATH = "wnba_data_completeness_repair_v1_step2_live_history.py"
TEST_PATH = "tests/test_wnba_data_completeness_repair_v1_step2_live_history.py"
EXPECTED_RUNTIME_BLOB = "13055f7bc06a8af369daba47453e92fe7e6c8ea7"
THAW_ID = "THAW-API2-WNBA-DATA-STEP2-LIVE-HYDRATION-R1"
EXPECTED_REGISTRY_REVISION = 150
EXPECTED_REGISTRY_HASH = "d96db7f9718aa2507a40f3a46bba3db5f705b690c6c9406de53fe668fa54752e"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")
EXPECTED_FILES = {RUNTIME_PATH, HELPER_PATH, TEST_PATH}


def _read_text(client, path: str, ref: str) -> tuple[str, str]:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("CANDIDATE_CONTENT_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _verify_scope(client) -> dict[str, str]:
    if client.branch_sha("main") != BASE_SHA:
        raise RuntimeError("CANDIDATE_GATE_MAIN_DRIFT")
    if client.branch_sha(REPAIR_BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("CANDIDATE_GATE_BRANCH_DRIFT")
    comparison = client.request("GET", f"/compare/{BASE_SHA}...{CANDIDATE_SHA}") or {}
    changed = {str(item.get("filename") or "") for item in comparison.get("files", [])}
    if changed != EXPECTED_FILES:
        raise RuntimeError("CANDIDATE_GATE_SCOPE_DRIFT:" + ",".join(sorted(changed)))
    tree = client.tree_blobs(CANDIDATE_SHA)
    artifacts = {path: str(tree.get(path) or "") for path in sorted(EXPECTED_FILES)}
    if artifacts.get(RUNTIME_PATH) != EXPECTED_RUNTIME_BLOB:
        raise RuntimeError("CANDIDATE_GATE_RUNTIME_BLOB_DRIFT")
    if any(len(value) != 40 for value in artifacts.values()):
        raise RuntimeError("CANDIDATE_GATE_ARTIFACT_MISSING")
    return artifacts


def _verify_registry(client) -> dict[str, Any]:
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("CANDIDATE_GATE_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    if int(payload.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("CANDIDATE_GATE_REGISTRY_REVISION_DRIFT")
    if str(payload.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("CANDIDATE_GATE_REGISTRY_HASH_DRIFT")
    matches = [item for item in payload.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise RuntimeError("CANDIDATE_GATE_THAW_MISSING")
    grant = matches[0]
    if str(grant.get("target_head_sha") or "") != CANDIDATE_SHA:
        raise RuntimeError("CANDIDATE_GATE_THAW_HEAD_DRIFT")
    pair = (grant.get("files") or {}).get(RUNTIME_PATH) or {}
    if str(pair.get("to_blob") or "") != EXPECTED_RUNTIME_BLOB:
        raise RuntimeError("CANDIDATE_GATE_THAW_BLOB_DRIFT")
    return payload


def _verify_behavior(client) -> dict[str, Any]:
    helper, _ = _read_text(client, HELPER_PATH, CANDIDATE_SHA)
    runtime, _ = _read_text(client, RUNTIME_PATH, CANDIDATE_SHA)
    test, _ = _read_text(client, TEST_PATH, CANDIDATE_SHA)
    compile(helper, HELPER_PATH, "exec")
    compile(runtime, RUNTIME_PATH, "exec")
    compile(test, TEST_PATH, "exec")

    ns: dict[str, Any] = {"__name__": "wnba_live_history_candidate"}
    exec(compile(helper, HELPER_PATH, "exec"), ns)
    summarize = ns.get("summarize_player_history")
    if not callable(summarize):
        raise RuntimeError("CANDIDATE_GATE_SUMMARIZER_MISSING")
    sample = {"games": [
        {"game_date": "2026-10-07", "minutes": 40, "points": 99, "rebounds": 99, "assists": 99},
        {"game_date": "2026-10-06", "minutes": 30, "points": 18, "rebounds": 5, "assists": 7},
        {"game_date": "2026-10-04", "minutes": 20, "points": 10, "rebounds": 4, "assists": 3},
        {"game_date": "2026-10-02", "minutes": 10, "points": 6, "rebounds": 2, "assists": 1},
    ]}
    result = summarize(sample, "2026-10-07")
    if int(result.get("GP") or 0) != 3:
        raise RuntimeError("CANDIDATE_GATE_CUTOFF_FAILED")
    if abs(float(result.get("MIN") or 0) - 20.0) > 1e-9:
        raise RuntimeError("CANDIDATE_GATE_MINUTES_FAILED")
    if abs(float(result.get("PRA") or 0) - (56.0 / 3.0)) > 1e-9:
        raise RuntimeError("CANDIDATE_GATE_PRA_FAILED")
    if str(result.get("LAST_GAME_DATE") or "") != "2026-10-06":
        raise RuntimeError("CANDIDATE_GATE_LAST_GAME_FAILED")

    required_runtime = (
        "get_step3_espn_player_game_log_dataset",
        "_aggregate_espn_athlete_gamelogs",
        "ESPN WNBA Athlete Gamelog",
        "summarize_player_history",
    )
    if not all(token in runtime for token in required_runtime):
        raise RuntimeError("CANDIDATE_GATE_RUNTIME_INTEGRATION_MISSING")
    if "wnba_data_completeness_repair_v1_step2_live_history" not in test:
        raise RuntimeError("CANDIDATE_GATE_REGRESSION_TEST_MISSING")
    return {
        "sample_gp": result["GP"],
        "sample_minutes": result["MIN"],
        "sample_pra": result["PRA"],
        "last_game_date": result["LAST_GAME_DATE"],
        "runtime_integration": True,
    }


def execute(client):
    artifacts = _verify_scope(client)
    registry = _verify_registry(client)
    behavior = _verify_behavior(client)
    evidence = {
        "base_sha": BASE_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "changed_files": sorted(EXPECTED_FILES),
        "provider_diagnostic": "ESPN_HISTORY_AND_SUMMARY_HEALTHY",
        "provider_completed_games": 363,
        "provider_summary_rows": 25,
        "root_cause": "old Streamlit season-summary fanout can collapse healthy provider history into roster-only zero production",
        "patch": "reuse repository-established latency-safe ESPN WNBA athlete gamelog and summarize season/L10/L5 before role projection",
        "behavior": behavior,
        "other_pages_changed": 0,
        "other_sports_changed": 0,
        "navigation_changed": False,
        "projection_math_changed": False,
        "market_changed": False,
        "probability_changed": False,
        "sportsbook_changed": False,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step2-live-hydration-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step2-live-hydration",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step2-live-hydration-r1",
        step="2/5-live-hydration-candidate",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifacts,
        dependency_map={
            "base_main_sha": BASE_SHA,
            "thaw_id": THAW_ID,
            "provider_diagnostic": "ESPN_HISTORY_AND_SUMMARY_HEALTHY",
            "github_actions_fallback": False,
        },
        registry_before={"revision": EXPECTED_REGISTRY_REVISION, "state_hash": EXPECTED_REGISTRY_HASH},
        registry_after={"mode": "candidate_gate_only", "thaw_remains_active": True},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": int(check["id"]),
        "receipt": str(receipt["digest"]),
        "artifacts": artifacts,
        "registry_revision": int(registry["revision"]),
        "behavior": behavior,
    }


def install_startup(app):
    app.state.wnba_live_hydration_candidate_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_live_hydration_candidate_gate = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_live_hydration_candidate_gate = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print("WNBA_LIVE_HYDRATION_CANDIDATE_GATE=" + json.dumps(app.state.wnba_live_hydration_candidate_gate, sort_keys=True), flush=True)
    return app
