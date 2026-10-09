from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from devsystem.scope_aware_execution_lease_v1 import validate_state as validate_scope_lease_state
from .gate import publish_gate

WORKSTREAM = "cfb-game-total-page1-visual-cleanup-v1"
TASK_ID = "cfb-game-total-page1-visual-cleanup-step5-deployment-convergence"
BASE_SHA = "5c155c494cf4e10148ebb3d6133d83a0ef42172c"
CANDIDATE_SHA = "37654ccba369fca46476af0845b3887e325db71c"
PR_NUMBER = 1484
MARKER_PATH = "devsystem/deployment_markers/monster-speed-v3-streamlit-redeploy-epoch-v1.txt"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
LEASE_OWNER = "api2-cfb-game-total-page1-visual-cleanup-step5-deployment-convergence"
LEASE_ID = "SCOPE-LEASE-FD85167BA69BE6013E8CEFD9"
REGISTRY_REVISION = 221
REGISTRY_HASH = "acbe369a22b2dd4703be0344eb4838862fccc33b71aeeaaca0190385f5698763"
CHECK_APP_ID = 5204253
GATE_NAME = "runless-final-gate"


def _decode_text(raw, label):
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    return base64.b64decode(raw["content"]).decode("utf-8")


def _decode_json(raw, label):
    return json.loads(_decode_text(raw, label))


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _holder(client):
    state = validate_scope_lease_state(_decode_json(client.content(LEASE_PATH, ref=LEASE_BRANCH), "STEP5_DEPLOY_LEASE"))
    now = datetime.now(timezone.utc)
    matches = [
        h for h in state.get("holders", [])
        if h.get("owner_id") == LEASE_OWNER
        and h.get("lease_id") == LEASE_ID
        and now < _utc(h["expires_at_utc"])
    ]
    if len(matches) != 1:
        return None
    holder = matches[0]
    scope = holder.get("scope") or {}
    identity = scope.get("resource_identity") or {}
    if (
        str(identity.get("candidate_sha") or "") != CANDIDATE_SHA
        or str(identity.get("main_sha") or "") != BASE_SHA
        or str(identity.get("workstream") or "") != WORKSTREAM
        or str(identity.get("phase") or "") != "deployment-convergence-premerge-proof"
    ):
        raise RuntimeError("STEP5_DEPLOY_LEASE_IDENTITY_DRIFT")
    if MARKER_PATH not in set(scope.get("write_paths") or []):
        raise RuntimeError("STEP5_DEPLOY_LEASE_SCOPE_DRIFT")
    return holder


def _existing_gate(client):
    runs = client.request("GET", f"/commits/{CANDIDATE_SHA}/check-runs?check_name={GATE_NAME}&filter=latest&per_page=100") or {}
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        if (
            str(run.get("head_sha") or "") == CANDIDATE_SHA
            and str(run.get("name") or "") == GATE_NAME
            and str(run.get("status") or "") == "completed"
            and int(app.get("id") or 0) == CHECK_APP_ID
        ):
            return run
    return None


def should_run(client):
    try:
        gate = _existing_gate(client)
        return _holder(client) is not None and gate is None
    except Exception:
        return False


def execute(app):
    client = app.state.github_client
    holder = _holder(client)
    if holder is None:
        raise RuntimeError("STEP5_DEPLOY_LEASE_NOT_LIVE")
    if client.branch_sha("main") != BASE_SHA:
        raise RuntimeError("STEP5_DEPLOY_MAIN_DRIFT")

    pr = client.request("GET", f"/pulls/{PR_NUMBER}") or {}
    if (
        pr.get("merged_at")
        or str((pr.get("head") or {}).get("sha") or "") != CANDIDATE_SHA
        or str((pr.get("base") or {}).get("sha") or "") != BASE_SHA
    ):
        raise RuntimeError("STEP5_DEPLOY_PR_IDENTITY_DRIFT")

    commit = client.commit(CANDIDATE_SHA)
    parents = [str(item.get("sha") or "") for item in commit.get("parents", [])]
    if parents != [BASE_SHA]:
        raise RuntimeError("STEP5_DEPLOY_PARENT_DRIFT")

    files = client.request("GET", f"/pulls/{PR_NUMBER}/files?per_page=100") or []
    names = [str(item.get("filename") or "") for item in files]
    if names != [MARKER_PATH]:
        raise RuntimeError("STEP5_DEPLOY_SCOPE_DRIFT:" + ",".join(names))
    row = files[0]
    if int(row.get("additions") or 0) != 1 or int(row.get("deletions") or 0) != 1:
        raise RuntimeError("STEP5_DEPLOY_DIFF_SIZE_DRIFT")

    base_raw = client.content(MARKER_PATH, ref=BASE_SHA)
    candidate_raw = client.content(MARKER_PATH, ref=CANDIDATE_SHA)
    base_text = _decode_text(base_raw, "STEP5_DEPLOY_BASE_MARKER")
    candidate_text = _decode_text(candidate_raw, "STEP5_DEPLOY_CANDIDATE_MARKER")
    expected_base = base_text.replace("MONSTER_SPEED_V3_STREAMLIT_REDEPLOY_EPOCH=4", "MONSTER_SPEED_V3_STREAMLIT_REDEPLOY_EPOCH=5", 1)
    if "MONSTER_SPEED_V3_STREAMLIT_REDEPLOY_EPOCH=4" not in base_text:
        raise RuntimeError("STEP5_DEPLOY_BASE_EPOCH_DRIFT")
    if candidate_text != expected_base:
        raise RuntimeError("STEP5_DEPLOY_MARKER_CONTENT_DRIFT")

    evidence = {
        "base_sha": BASE_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "pr_number": PR_NUMBER,
        "changed_files": names,
        "base_marker_blob": str(base_raw.get("sha") or ""),
        "candidate_marker_blob": str(candidate_raw.get("sha") or ""),
        "github_actions_fallback": 0,
        "product_changes": 0,
        "failure_class": "DEPLOYMENT_CONVERGENCE",
    }
    evidence_digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt = build_runless_receipt(
        proof_id=TASK_ID + "-" + CANDIDATE_SHA[:16],
        task_id=TASK_ID,
        project="API2",
        workstream=WORKSTREAM,
        step="5/5-deployment-convergence",
        candidate_sha=CANDIDATE_SHA,
        artifact_map={MARKER_PATH: str(candidate_raw.get("sha") or "")},
        dependency_map={MARKER_PATH + "@base": str(base_raw.get("sha") or "")},
        registry_before={"revision": REGISTRY_REVISION, "state_hash": REGISTRY_HASH},
        registry_after={"revision": REGISTRY_REVISION, "state_hash": REGISTRY_HASH},
        evidence_digests={"deployment_marker_exact_diff": evidence_digest},
        failure_class="NONE",
        github_actions_fallback=0,
        scope_lease_id=str(holder.get("lease_id") or ""),
        authorization_id="AUTH-CFB-GT-P1-STEP5-DEPLOYMENT-CONVERGENCE-1484",
    )
    publish_gate(client, CANDIDATE_SHA, "success", receipt, GATE_NAME)
    gate = _existing_gate(client)
    if gate is None or str(gate.get("conclusion") or "") != "success":
        raise RuntimeError("STEP5_DEPLOY_GATE_READBACK_FAILED")
    return {
        "status": "GREEN",
        "decision": "STEP5_DEPLOYMENT_MARKER_EXACT_HEAD_AUTHORIZED",
        "candidate_sha": CANDIDATE_SHA,
        "check_id": int(gate.get("id") or 0),
        "receipt_digest": receipt["digest"],
        "lease_id": str(holder.get("lease_id") or ""),
        "github_actions_fallback": 0,
        "product_changes": 0,
    }


def install_startup(app):
    app.state.cfb_gt_step5_deployment_convergence = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if not should_run(app.state.github_client):
            return
        try:
            app.state.cfb_gt_step5_deployment_convergence = execute(app)
        except Exception as exc:
            app.state.cfb_gt_step5_deployment_convergence = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP5_DEPLOYMENT_CONVERGENCE="
            + json.dumps(app.state.cfb_gt_step5_deployment_convergence, sort_keys=True),
            flush=True,
        )

    return app
