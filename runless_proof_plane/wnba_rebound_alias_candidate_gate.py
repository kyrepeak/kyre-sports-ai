from __future__ import annotations

import base64
import hashlib
import json

from devsystem.frozen_artifact_registry_v1 import REGISTRY_PATH, REGISTRY_REF, validate_registry
from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate

MAIN_SHA = "c87f0f2ed07631a8e7e8c3c342a2f946230a9159"
BRANCH = "api2-wnba-data-step2-rebound-alias-r1"
CANDIDATE_SHA = "1735d5871030c5aab2143edeed07a0b39877e4c8"
PATH = "sports_api/wnba_pra_speed_v3_step3_espn_history.py"
FROM_BLOB = "fa4f7a99a6c73984e90e938efc506711a9f614c6"
TO_BLOB = "385ebd3dea99516281d70179d7927aa1ae7042b6"
EXPECTED_REGISTRY_REVISION = 154
EXPECTED_REGISTRY_HASH = "63d54f1a303062167e651073dd410dd79bbc3917d5e15c5c737ab7520404f55c"
REGISTRY_BRANCH = REGISTRY_REF.removeprefix("refs/heads/")
PLAN_PATH = "devsystem/runless_proof_plans/wnba-data-completeness-repair-v1-step2-rebound-alias.json"
CERT_PATH = "devsystem/wnba_data_completeness_repair_v1_step2_rebound_alias_cert.py"
TEST_PATH = "tests/test_wnba_data_completeness_repair_v1_step2_rebound_alias.py"
LEDGER_PATH = "devsystem/task_ledgers/wnba-data-completeness-repair-v1-step2-rebound-alias.json"
CERT_TOKEN = "WNBA_DATA_COMPLETENESS_REPAIR_V1_STEP2_REBOUND_ALIAS_GREEN"
REQUIRED_OWNER = '"rebounds": _to_int(_pick(stats, "REB", "rebounds", "totalRebounds")),'
FORBIDDEN_OWNER = '"rebounds": _to_int(_pick(stats, "REB", "rebounds")),'
EXPECTED_CHANGED = tuple(sorted((PATH, PLAN_PATH, CERT_PATH, TEST_PATH, LEDGER_PATH)))


def _read_text(client, path: str, ref: str) -> tuple[str, str]:
    raw = client.content(path, ref=ref)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("REBOUND_ALIAS_GATE_READ_FAILED:" + path)
    return base64.b64decode(raw["content"]).decode(), str(raw["sha"])


def _read_json(client, path: str, ref: str) -> tuple[dict, str]:
    text, sha = _read_text(client, path, ref)
    try:
        value = json.loads(text)
    except Exception as exc:
        raise RuntimeError("REBOUND_ALIAS_GATE_JSON_INVALID:" + path) from exc
    return value, sha


def _verify_registry_unowned(client) -> tuple[int, str]:
    raw = client.content(REGISTRY_PATH, ref=REGISTRY_BRANCH)
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError("REBOUND_ALIAS_GATE_REGISTRY_READ_FAILED")
    payload = json.loads(base64.b64decode(raw["content"]).decode())
    validate_registry(payload)
    if int(payload.get("revision") or -1) != EXPECTED_REGISTRY_REVISION:
        raise RuntimeError("REBOUND_ALIAS_GATE_REGISTRY_REVISION_DRIFT")
    if str(payload.get("state_hash") or "") != EXPECTED_REGISTRY_HASH:
        raise RuntimeError("REBOUND_ALIAS_GATE_REGISTRY_HASH_DRIFT")
    for checkpoint, entry in (payload.get("entries") or {}).items():
        if PATH in ((entry or {}).get("artifacts") or {}):
            raise RuntimeError("REBOUND_ALIAS_GATE_UNEXPECTED_FROZEN_OWNER:" + str(checkpoint))
    for thaw in payload.get("active_thaws") or []:
        if PATH in ((thaw or {}).get("files") or {}):
            raise RuntimeError("REBOUND_ALIAS_GATE_UNEXPECTED_ACTIVE_THAW:" + str(thaw.get("thaw_id") or ""))
    return int(payload["revision"]), str(payload["state_hash"])


def execute(client):
    if client.branch_sha("main") != MAIN_SHA:
        raise RuntimeError("REBOUND_ALIAS_GATE_MAIN_DRIFT")
    if client.branch_sha(BRANCH) != CANDIDATE_SHA:
        raise RuntimeError("REBOUND_ALIAS_GATE_CANDIDATE_DRIFT")

    comparison = client.request("GET", f"/compare/{MAIN_SHA}...{CANDIDATE_SHA}") or {}
    changed = tuple(sorted(str(item.get("filename") or "") for item in comparison.get("files", [])))
    if changed != EXPECTED_CHANGED:
        raise RuntimeError("REBOUND_ALIAS_GATE_SCOPE_DRIFT:" + ",".join(changed))

    main_tree = client.tree_blobs(MAIN_SHA)
    candidate_tree = client.tree_blobs(CANDIDATE_SHA)
    if str(main_tree.get(PATH) or "") != FROM_BLOB:
        raise RuntimeError("REBOUND_ALIAS_GATE_MAIN_BLOB_DRIFT")
    if str(candidate_tree.get(PATH) or "") != TO_BLOB:
        raise RuntimeError("REBOUND_ALIAS_GATE_CANDIDATE_BLOB_DRIFT")
    artifacts = {path: str(candidate_tree.get(path) or "") for path in EXPECTED_CHANGED}
    if any(len(blob) != 40 for blob in artifacts.values()):
        raise RuntimeError("REBOUND_ALIAS_GATE_ARTIFACT_MISSING")

    owner, _ = _read_text(client, PATH, CANDIDATE_SHA)
    if REQUIRED_OWNER not in owner:
        raise RuntimeError("REBOUND_ALIAS_GATE_TOTAL_REBOUNDS_ALIAS_MISSING")
    if FORBIDDEN_OWNER in owner:
        raise RuntimeError("REBOUND_ALIAS_GATE_OLD_ALIAS_ONLY_PRESENT")

    cert, _ = _read_text(client, CERT_PATH, CANDIDATE_SHA)
    test, _ = _read_text(client, TEST_PATH, CANDIDATE_SHA)
    if CERT_TOKEN not in cert or "test_live_espn_total_rebounds_alias_is_preserved" not in test:
        raise RuntimeError("REBOUND_ALIAS_GATE_PROOF_CONTRACT_MISSING")

    plan, _ = _read_json(client, PLAN_PATH, CANDIDATE_SHA)
    tdd = plan.get("tdd") or {}
    evidence_plan = plan.get("evidence") or {}
    if plan.get("runless_required") is not True or plan.get("github_actions_fallback") is not False:
        raise RuntimeError("REBOUND_ALIAS_GATE_RUNLESS_CONTRACT_DRIFT")
    if plan.get("frozen_registry_thaw_required") is not False:
        raise RuntimeError("REBOUND_ALIAS_GATE_THAW_CONTRACT_DRIFT")
    if int(tdd.get("red_rc", -1)) != 1 or int(tdd.get("green_rc", -1)) != 0:
        raise RuntimeError("REBOUND_ALIAS_GATE_TDD_RECEIPT_DRIFT")
    if str(tdd.get("red_proof_deploy") or "") != "dep-db2rf50m7kps73c1rld0":
        raise RuntimeError("REBOUND_ALIAS_GATE_RED_PROOF_DRIFT")
    if str(tdd.get("green_proof_deploy") or "") != "dep-db2ricp42hec73flbg4g":
        raise RuntimeError("REBOUND_ALIAS_GATE_GREEN_PROOF_DRIFT")
    if str(evidence_plan.get("provider_shape_deploy") or "") != "dep-db2rdsid0e5s73e5ai60":
        raise RuntimeError("REBOUND_ALIAS_GATE_PROVIDER_PROOF_DRIFT")
    if str(evidence_plan.get("provider_name") or "") != "totalRebounds":
        raise RuntimeError("REBOUND_ALIAS_GATE_PROVIDER_NAME_DRIFT")

    revision, state_hash = _verify_registry_unowned(client)
    evidence = {
        "main_sha": MAIN_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "changed_files": list(changed),
        "artifacts": artifacts,
        "provider_shape_deploy": evidence_plan.get("provider_shape_deploy"),
        "provider_name": evidence_plan.get("provider_name"),
        "provider_observed_rebound_values": evidence_plan.get("provider_observed_rebound_values"),
        "tdd_red_deploy": tdd.get("red_proof_deploy"),
        "tdd_green_deploy": tdd.get("green_proof_deploy"),
        "frozen_registry_owner": False,
        "active_thaw": False,
        "navigation_changed": False,
        "projection_math_changed": False,
        "probability_changed": False,
        "market_changed": False,
        "other_sports_changed": 0,
    }
    evidence_digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt = build_runless_receipt(
        proof_id=f"wnba-step2-rebound-alias-{CANDIDATE_SHA[:16]}",
        task_id="wnba-data-completeness-repair-v1-step2-rebound-alias",
        project="API2",
        workstream="api2-wnba-data-completeness-repair-v1-step2",
        step="2/3-rebound-alias-candidate",
        candidate_sha=CANDIDATE_SHA,
        artifact_map=artifacts,
        dependency_map={
            "base_main_sha": MAIN_SHA,
            "github_actions_fallback": False,
            "frozen_registry_thaw_required": False,
            "provider_shape_deploy": evidence_plan.get("provider_shape_deploy"),
            "tdd_red_deploy": tdd.get("red_proof_deploy"),
            "tdd_green_deploy": tdd.get("green_proof_deploy"),
        },
        registry_before={"revision": revision, "state_hash": state_hash},
        registry_after={"mode": "candidate_gate_only", "registry_mutated": False},
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
        "frozen_registry_owner": False,
        "active_thaw": False,
    }


def install_startup(app):
    app.state.wnba_rebound_alias_candidate_gate = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_rebound_alias_candidate_gate = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_rebound_alias_candidate_gate = {
                "status": "FAIL", "error": type(exc).__name__, "detail": str(exc)[:800]
            }
        print(
            "WNBA_REBOUND_ALIAS_CANDIDATE_GATE="
            + json.dumps(app.state.wnba_rebound_alias_candidate_gate, sort_keys=True),
            flush=True,
        )
    return app
