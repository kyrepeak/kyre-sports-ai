from __future__ import annotations

import base64
import hashlib
import json

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

MAIN_SHA = "2800670d1b1e15f6a98cc7a5fc3ffab4fb9600e5"
BRANCH = "api2-wnba-data-step2-selected-day-handoff-r1"
CANDIDATE_SHA = "786d3042e5c3392edc3a40218520aff5d9e1a934"
PATH = "wnba_availability_v27.py"
FROM_BLOB = "82468c9b603947c052e726cd8beb9ba1b05b2484"
TO_BLOB = "4cdb65b9fd7942865ad17e7b27e29fb815192de1"
THAW_ID = "THAW-API2-WNBA-DATA-STEP2-SELECTED-DAY-HANDOFF-R1"
OWNER_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP1_FROZEN"
EXPECTED_REGISTRY_REVISION = 154
EXPECTED_REGISTRY_HASH = "63d54f1a303062167e651073dd410dd79bbc3917d5e15c5c737ab7520404f55c"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")
PLAN_PATH = "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step2-selected-day-handoff.json"
CERT_PATH = "devsystem/wnba_data_completeness_repair_v1_step2_selected_day_handoff_cert.py"
TEST_PATH = "tests/test_wnba_data_completeness_repair_v1_step2_selected_day_handoff.py"
LEDGER_PATH = "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step2-selected-day-handoff.json"
CERT_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_SELECTED_DAY_HANDOFF_GREEN"
REQUIRED_OWNER = "raw, _ = players._build_selected_player_pool(day_str)"
FORBIDDEN_OWNER = "raw = players.player_form_table(pd.to_datetime(day_str).year)"
EXPECTED_CHANGED = tuple(sorted((PATH, PLAN_PATH, CERT_PATH, TEST_PATH, LEDGER_PATH)))


def _read_text(client, path: str, ref: str) -> tuple[str, str]:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("SELECTED_DAY_GATE_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _read_json(client, path: str, ref: str) -> tuple[dict, str]:
    text, sha = _read_text(client, path, ref)
    try:
        value = json.loads(text)
    except Exception as exc:
        raise RuntimeError("SELECTED_DAY_GATE_JSON_INVALID:" + path) from exc
    return value, sha


def _verify_registry(client) -> tuple[int, str]:
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("SELECTED_DAY_GATE_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    if int(payload.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("SELECTED_DAY_GATE_REGISTRY_REVISION_DRIFT")
    if str(payload.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("SELECTED_DAY_GATE_REGISTRY_HASH_DRIFT")
    owner = ((payload.get("entries") or {}).get(OWNER_TOKEN) or {}).get("artifacts") or {}
    if str(owner.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("SELECTED_DAY_GATE_OWNER_BASELINE_DRIFT")
    matches = [item for item in payload.get("active_thaws", []) if item.get("thaw_id") == THAW_ID]
    if len(matches) != 1:
        raise RuntimeError("SELECTED_DAY_GATE_THAW_MISSING")
    grant = matches[0]
    if str(grant.get("target_head_sha") or "") != CANDIDATE_SHA:
        raise RuntimeError("SELECTED_DAY_GATE_THAW_HEAD_DRIFT")
    pair = (grant.get("files") or {}).get(PATH) or {}
    if str(pair.get("from_blob") or "") != FROM_BLOB or str(pair.get("to_blob") or "") != TO_BLOB:
        raise RuntimeError("SELECTED_DAY_GATE_THAW_BLOB_DRIFT")
    for item in payload.get("active_thaws", []):
        if item.get("thaw_id") != THAW_ID and PATH in (item.get("files") or {}):
            raise RuntimeError("SELECTED_DAY_GATE_COMPETING_THAW")
    return int(payload["revision"]), str(payload["state_hash"])


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("SELECTED_DAY_GATE_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("SELECTED_DAY_GATE_CANDIDATE_DRIFT")

    comparison = client.request("GET", f"/compare/{MAIN_SHA}...{CANDIDATE_SHA}") or {}
    changed = tuple(sorted(str(item.get("filename") or "") for item in comparison.get("files", [])))
    if changed != EXPECTED_CHANGED:
        raise RuntimeError("SELECTED_DAY_GATE_SCOPE_DRIFT:" + ",".join(changed))

    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("SELECTED_DAY_GATE_MAIN_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != TO_BLOB:
        raise RuntimeError("SELECTED_DAY_GATE_CANDIDATE_BLOB_DRIFT")
    artifacts = {path: str(candidate_tree.get(path) or "") for path in EXPECTED_CHANGED}
    if any(len(blob) != 40 for blob in artifacts.values()):
        raise RuntimeError("SELECTED_DAY_GATE_ARTIFACT_MISSING")

    owner, _ = _read_text(client, PATH, CANDIDATE_SHA)
    if REQUIRED_OWNER not in owner:
        raise RuntimeError("SELECTED_DAY_GATE_EXACT_DAY_HANDOFF_MISSING")
    if FORBIDDEN_OWNER in owner:
        raise RuntimeError("SELECTED_DAY_GATE_YEAR_ONLY_HANDOFF_PRESENT")

    cert, _ = _read_text(client, CERT_PATH, CANDIDATE_SHA)
    test, _ = _read_text(client, TEST_PATH, CANDIDATE_SHA)
    if CERT_TOKEN not in cert or "test_verified_pool_hydrates_the_exact_requested_day" not in test:
        raise RuntimeError("SELECTED_DAY_GATE_PROOF_CONTRACT_MISSING")

    plan, _ = _read_json(client, PLAN_PATH, CANDIDATE_SHA)
    tdd = plan.get("tdd") or {}
    if plan.get("runless_required") is not True or plan.get("github_actions_fallback") is not False:
        raise RuntimeError("SELECTED_DAY_GATE_RUNLESS_CONTRACT_DRIFT")
    if str(plan.get("thaw_id") or "") != THAW_ID:
        raise RuntimeError("SELECTED_DAY_GATE_PLAN_THAW_DRIFT")
    if int(tdd.get("red_rc", -1)) != 1 or int(tdd.get("green_rc", -1)) != 0:
        raise RuntimeError("SELECTED_DAY_GATE_TDD_RECEIPT_DRIFT")
    if str(tdd.get("red_proof_deploy") or "") != "dep-db2r2bajnfac73fndf20":
        raise RuntimeError("SELECTED_DAY_GATE_RED_PROOF_DRIFT")
    if str(tdd.get("green_proof_deploy") or "") != "dep-db2r48ijnfac73fnjm20":
        raise RuntimeError("SELECTED_DAY_GATE_GREEN_PROOF_DRIFT")

    revision, state_hash = _verify_registry(client)
    evidence = {
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "changed_files": list(changed),
        "artifacts": artifacts,
        "thaw_id": THAW_ID,
        "tdd_red_deploy": tdd.get("red_proof_deploy"),
        "tdd_green_deploy": tdd.get("green_proof_deploy"),
        "selected_day_handoff": True,
        "year_only_handoff_removed": True,
        "navigation_changed": False,
        "projection_math_changed": False,
        "probability_changed": False,
        "market_changed": False,
        "other_sports_changed": 0,
    }
    evidence_digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt = build_runless_receipt(
        proof_id=f"wnba-step2-selected-day-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step2-selected-day-handoff",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step2",
        step="2/3-selected-day-candidate",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifacts,
        dependency_map={
            "base_main_sha": MAIN_SHA,
            "github_actions_fallback": False,
            "thaw_id": THAW_ID,
            "tdd_red_deploy": tdd.get("red_proof_deploy"),
            "tdd_green_deploy": tdd.get("green_proof_deploy"),
        },
        registry_before={"revision": revision, "state_hash": state_hash},
        registry_after={"mode": "candidate_gate_only", "thaw_remains_active": True},
        evidence_digests=[evidence_digest],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": int(check["id"]),
        "receipt": str(receipt["digest"]),
        "changed_files": list(changed),
        "registry_revision": revision,
        "registry_state_hash": state_hash,
        "thaw_id": THAW_ID,
    }


def install_startup(app):
    app.state.wnba_selected_day_handoff_candidate_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_selected_day_handoff_candidate_gate = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_selected_day_handoff_candidate_gate = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "WNBA_SELECTED_DAY_HANDOFF_CANDIDATE_GATE="
            + json.dumps(app.state.wnba_selected_day_handoff_candidate_gate, sort_keys=True),
            flush=True,
        )
    return app
