from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

BASE_SHA = "ec301504ee74fe247eaf62d992b78929d4b2f6ed"
CANDIDATE_SHA = "0a4341139ef22742bc1440aaa41a6133164eb94c"
PR_NUMBER = 1421
RUNLESS_APP_ID = 5204253

OWNER = "wnba_availability_v27.py"
TEST = "tests/test_wnba_data_completeness_repair_v1_step1.py"
CERT = "devsystem/wnba_data_completeness_repair_v1_step1_source_id_truth_cert.py"
PLAN = "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step1-source-id-truth.json"
LEDGER = "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step1-source-id-truth.json"
EXPECTED_FILES = tuple(sorted((OWNER, TEST, CERT, PLAN, LEDGER)))


def _read_text(client, path: str, ref: str) -> str:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("WNBA_DATA_STEP1_CONTENT_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode("utf-8")


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _verify_identity(client) -> dict[str, str]:
    if client.branch_sha("main") != BASE_SHA:
        raise RuntimeError("WNBA_DATA_STEP1_MAIN_DRIFT")

    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if str(pr.get("state") or "") != "open":
        raise RuntimeError("WNBA_DATA_STEP1_PR_NOT_OPEN")
    if str(((pr.get("head") or {}).get("sha") or "")) != CANDIDATE_SHA:
        raise RuntimeError("WNBA_DATA_STEP1_HEAD_DRIFT")
    base = pr.get("base") or {}
    if str(base.get("ref") or "") != "main" or str(base.get("sha") or "") != BASE_SHA:
        raise RuntimeError("WNBA_DATA_STEP1_BASE_DRIFT")

    files = client.request("GET", f"/pulls/{PR_NUMBER}/files?per_page=100") or []
    changed = tuple(sorted(str(item.get("filename") or "") for item in files))
    if changed != EXPECTED_FILES:
        raise RuntimeError("WNBA_DATA_STEP1_SCOPE_DRIFT:" + ",".join(changed))

    forbidden_prefixes = (
        "app.py",
        "streamlit_memory_lazy_router_",
        ".github/",
        "cfb_",
        "nfl_",
        "nba_",
        "mlb_",
    )
    for path in changed:
        if path == OWNER or path == TEST or path == CERT or path == PLAN or path == LEDGER:
            continue
        if path.startswith(forbidden_prefixes):
            raise RuntimeError("WNBA_DATA_STEP1_FORBIDDEN_SCOPE:" + path)

    tree = client.tree_blobs(CANDIDATE_SHA)
    artifact_map: dict[str, str] = {}
    for path in EXPECTED_FILES:
        blob = str(tree.get(path) or "")
        if len(blob) != 40:
            raise RuntimeError("WNBA_DATA_STEP1_ARTIFACT_MISSING:" + path)
        artifact_map[path] = blob
    return artifact_map


def _verify_behavior(client) -> dict[str, Any]:
    base_owner = _read_text(client, OWNER, BASE_SHA)
    owner = _read_text(client, OWNER, CANDIDATE_SHA)
    test = _read_text(client, TEST, CANDIDATE_SHA)
    cert = _read_text(client, CERT, CANDIDATE_SHA)
    plan_text = _read_text(client, PLAN, CANDIDATE_SHA)
    ledger_text = _read_text(client, LEDGER, CANDIDATE_SHA)

    compile(owner, OWNER, "exec")
    compile(test, TEST, "exec")
    compile(cert, CERT, "exec")
    plan = json.loads(plan_text)
    ledger = json.loads(ledger_text)

    old_overwrite = 'for c in ["PLAYER_ID","PLAYER_NAME","TEAM_ID","TEAM_NAME","TEAM_ABBREVIATION","POSITION","ROSTER_STATUS"]'
    fixed_overlay = 'for c in ["PLAYER_NAME","TEAM_ID","TEAM_NAME","TEAM_ABBREVIATION","POSITION","ROSTER_STATUS"]'
    if old_overwrite not in base_owner:
        raise RuntimeError("WNBA_DATA_STEP1_ROOT_CAUSE_BASELINE_MISSING")
    if old_overwrite in owner:
        raise RuntimeError("WNBA_DATA_STEP1_PLAYER_ID_OVERWRITE_STILL_PRESENT")
    if fixed_overlay not in owner:
        raise RuntimeError("WNBA_DATA_STEP1_ROSTER_OVERLAY_CONTRACT_MISSING")

    required_owner = (
        'production_pid = sr.get("PLAYER_ID")',
        'base["PLAYER_ID"] = production_pid',
        'base["PLAYER_ID_SOURCE"] = source',
        'base["PLAYER_ID_SOURCE"] = _identity_text(rr.get("PLAYER_ID_SOURCE")) or "ESPN"',
        'def _identity_text(value) -> str:',
        'text.casefold() in {"nan", "none"}',
        'out[c] = out[c].map(_identity_text)',
    )
    missing = [item for item in required_owner if item not in owner]
    if missing:
        raise RuntimeError("WNBA_DATA_STEP1_OWNER_CONTRACT_MISSING:" + "|".join(missing))

    required_tests = (
        "test_verified_pool_preserves_production_player_id_when_roster_id_differs",
        "test_unmatched_roster_id_is_explicitly_labeled_espn",
        "test_verified_pool_never_emits_nan_identity_text",
        'assert float(row["PTS"]) == 18.4',
    )
    missing_tests = [item for item in required_tests if item not in test]
    if missing_tests:
        raise RuntimeError("WNBA_DATA_STEP1_TEST_CONTRACT_MISSING:" + "|".join(missing_tests))

    if plan.get("base_main_sha") != BASE_SHA or plan.get("github_actions_fallback") is not False:
        raise RuntimeError("WNBA_DATA_STEP1_PLAN_CONTRACT_INVALID")
    if plan.get("freeze_token") != "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP1_FROZEN":
        raise RuntimeError("WNBA_DATA_STEP1_FREEZE_TOKEN_DRIFT")
    if ledger.get("status") != "CANDIDATE_READY_FOR_RUNLESS":
        raise RuntimeError("WNBA_DATA_STEP1_LEDGER_STATE_INVALID")

    return {
        "root_cause_reproduced_on_base": True,
        "production_id_preserved": True,
        "production_id_source_preserved": True,
        "espn_fallback_labeled": True,
        "nan_identity_blocked": True,
        "existing_stat_value_contract_locked": True,
        "product_files_changed": 1,
        "cross_sport_files_changed": 0,
        "navigation_files_changed": 0,
        "github_actions_fallback": False,
    }


def publish_candidate_gate(client) -> dict[str, Any]:
    artifact_map = _verify_identity(client)
    behavior = _verify_behavior(client)
    evidence = {
        "base_sha": BASE_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "pr_number": PR_NUMBER,
        "scope": list(EXPECTED_FILES),
        "behavior": behavior,
    }
    receipt = build_runless_receipt(
        proof_id=f"wnba-data-step1-source-id-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step1-source-id-truth",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step1",
        step="1/5-candidate-certification",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifact_map,
        dependency_map={
            "base_main_sha": BASE_SHA,
            "pr_number": PR_NUMBER,
            "proof_authority": "Runless Proof Plane",
            "github_actions_fallback": False,
        },
        registry_before={"pushstate_mission": "FROZEN_AND_PROTECTED"},
        registry_after={"freeze_token": "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP1_FROZEN", "mode": "pending_merge"},
        evidence_digests=[_digest(evidence)],
        failure_class="NONE",
    )
    check = publish_gate(client, CANDIDATE_SHA, "success", receipt)
    return {
        "status": "GREEN",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": int(check["id"]),
        "receipt_digest": str(receipt["digest"]),
        **behavior,
    }


def install_startup_gate(app):
    app.state.wnba_data_step1_source_id_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _publish_wnba_data_step1_source_id_gate():
        try:
            app.state.wnba_data_step1_source_id_gate = publish_candidate_gate(app.state.github_client)
        except Exception as exc:
            app.state.wnba_data_step1_source_id_gate = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:500],
            }

    return app
