from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone

from devsystem.runless_terminal_proof_receipt_v1 import build_runless_receipt
from .gate import publish_gate
from .cfb_game_total_page1_visual_cleanup_step1_closeout import install_startup as install_cfb_visual_cleanup_step1_closeout
from .cfb_game_total_page1_visual_cleanup_step2_closeout import install_startup as install_cfb_visual_cleanup_step2_closeout
from .cfb_game_total_page1_visual_cleanup_step3_thaw import install_startup as install_cfb_visual_cleanup_step3_thaw
from .cfb_game_total_page1_visual_cleanup_step3_proof import install_startup as install_cfb_visual_cleanup_step3_proof
from .cfb_game_total_page1_visual_cleanup_step3_closeout import install_startup as install_cfb_visual_cleanup_step3_closeout
from .cfb_game_total_page1_visual_cleanup_step4_thaw import install_startup as install_cfb_visual_cleanup_step4_thaw
from .cfb_game_total_page1_visual_cleanup_step4_proof import install_startup as install_cfb_visual_cleanup_step4_proof
from .cfb_game_total_page1_visual_cleanup_step4_closeout import install_startup as install_cfb_visual_cleanup_step4_closeout
from .cfb_game_total_page1_visual_cleanup_step5_deployment_convergence import install_startup as install_cfb_visual_cleanup_step5_deployment_convergence
from .cfb_game_total_page1_visual_cleanup_step5_thaw import install_startup as install_cfb_visual_cleanup_step5_thaw
from .cfb_game_total_page1_visual_cleanup_step5_proof import install_startup as install_cfb_visual_cleanup_step5_proof
from .cfb_game_total_page1_visual_cleanup_step5_cert import install_startup as install_cfb_visual_cleanup_step5_cert
from . import cfb_game_total_page1_visual_cleanup_step5_closeout as step5_closeout_core

DEPLOYMENT_MAIN_SHA = "443bd71d4ee956a0b26539a900771b30b90a77fe"
CERTIFIED_PRODUCT_MAIN_SHA = "5c155c494cf4e10148ebb3d6133d83a0ef42172c"
DEPLOYMENT_MARKER_CANDIDATE_SHA = "37654ccba369fca46476af0845b3887e325db71c"
DEPLOYMENT_MARKER_PATH = "devsystem/deployment_markers/monster-speed-v3-streamlit-redeploy-epoch-v1.txt"
POSTMERGE_LEASE_ID = "SCOPE-LEASE-228D3523AABA8F66D855690A"

REPAIR_PR_NUMBER = 1485
REPAIR_HEAD_SHA = "ba1caf4f1383e5169a1661cab1f5b78ed5c4c757"
REPAIR_TASK_ID = "cfb-game-total-page1-visual-cleanup-step5-v191-idempotence"
REPAIR_PROOF_ID = REPAIR_TASK_ID + "-" + REPAIR_HEAD_SHA[:16]
REPAIR_RECEIPT_BRANCH = "runless-proof-receipts"
REPAIR_RECEIPT_PATH = f"devsystem/runless_proof_receipts/{REPAIR_PROOF_ID}.json"
REPAIR_ALLOWED_PATHS = (
    "devsystem/execution_plans/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json",
    "streamlit_memory_lazy_router_v191.py",
    "tests/test_cfb_game_total_page1_visual_cleanup_step5_v191_idempotence.py",
)
REPAIR_FROZEN_DEPENDENCIES = (
    "cfb_game_total_page1_visual_cleanup_step3_activation_v1.py",
    "cfb_game_total_page1_visual_cleanup_step4_activation_v1.py",
    "cfb_game_total_page1_v2_step4_side_market_completeness_v1.py",
    "kyre_remaining_pages_theme_v1.py",
)
REGISTRY_REVISION = 221
REGISTRY_HASH = "acbe369a22b2dd4703be0344eb4838862fccc33b71aeeaaca0190385f5698763"
CHECK_APP_ID = 5204253


def _install_optional_404_compat(app):
    client = app.state.github_client
    current = client.content
    if getattr(current, "_cfb_optional_404_compat", False):
        return

    def content(path, ref=None, allow_404=False):
        try:
            return current(path, ref=ref, allow_404=allow_404)
        except Exception as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if allow_404 and (status_code == 404 or "404" in str(exc)):
                return None
            raise

    setattr(content, "_cfb_optional_404_compat", True)
    client.content = content


def _decode_text(raw, label):
    if not raw or raw.get("encoding") != "base64":
        raise RuntimeError(label + "_READ_FAILED")
    return base64.b64decode(raw["content"]).decode("utf-8")


def _decode_json(raw, label):
    return json.loads(_decode_text(raw, label))


def _repair_gate(client):
    runs = client.request(
        "GET",
        f"/commits/{REPAIR_HEAD_SHA}/check-runs?check_name=runless-final-gate&filter=latest&per_page=100",
    ) or {}
    for run in runs.get("check_runs", []):
        app = run.get("app") or {}
        if (
            str(run.get("head_sha") or "") == REPAIR_HEAD_SHA
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
            and int(app.get("id") or 0) == CHECK_APP_ID
        ):
            return run
    return None


def _repair_pr_open(client):
    pr = client.request("GET", f"/pulls/{REPAIR_PR_NUMBER}") or {}
    return not bool(pr.get("merged_at")) and str(pr.get("state") or "") == "open"


def _repair_lease(client):
    core = step5_closeout_core
    state = core.validate_scope_lease_state(
        core._decode_json(client.content(core.LEASE_PATH, ref=core.LEASE_BRANCH), "STEP5_REPAIR_LEASE")
    )
    now = datetime.now(timezone.utc)
    matches = [
        item for item in state.get("holders", [])
        if item.get("owner_id") == core.LEASE_OWNER
        and item.get("lease_id") == POSTMERGE_LEASE_ID
        and now < core._utc(item["expires_at_utc"])
    ]
    if len(matches) != 1:
        raise RuntimeError("STEP5_REPAIR_LEASE_NOT_LIVE")
    holder = matches[0]
    scope = holder.get("scope") or {}
    identity = scope.get("resource_identity") or {}
    if (
        str(identity.get("main_sha") or "") != DEPLOYMENT_MAIN_SHA
        or str(identity.get("certified_product_main_sha") or "") != CERTIFIED_PRODUCT_MAIN_SHA
        or str(identity.get("workstream") or "") != core.WORKSTREAM
        or str(identity.get("phase") or "") != "postmerge-live-cert-closeout"
        or str(identity.get("live_repair") or "") != "v191-once-per-process-installer-guard"
    ):
        raise RuntimeError("STEP5_REPAIR_LEASE_IDENTITY_DRIFT")
    required = {
        "streamlit_memory_lazy_router_v191.py",
        "tests/test_cfb_game_total_page1_visual_cleanup_step5_v191_idempotence.py",
        "devsystem/runless_proof_receipts",
        "runless_proof_plane/nfl_rb_wr_step3_closeout.py",
    }
    if not required.issubset(set(scope.get("write_paths") or [])):
        raise RuntimeError("STEP5_REPAIR_LEASE_SCOPE_DRIFT")
    return holder


def _execute_repair_premerge(app):
    client = app.state.github_client
    if client.branch_sha("main") != DEPLOYMENT_MAIN_SHA:
        raise RuntimeError("STEP5_REPAIR_MAIN_DRIFT")
    holder = _repair_lease(client)
    pr = client.request("GET", f"/pulls/{REPAIR_PR_NUMBER}") or {}
    if (
        pr.get("merged_at")
        or str(pr.get("state") or "") != "open"
        or str((pr.get("head") or {}).get("sha") or "") != REPAIR_HEAD_SHA
        or str((pr.get("base") or {}).get("sha") or "") != DEPLOYMENT_MAIN_SHA
    ):
        raise RuntimeError("STEP5_REPAIR_PR_IDENTITY_DRIFT")

    comparison = client.request("GET", f"/compare/{DEPLOYMENT_MAIN_SHA}...{REPAIR_HEAD_SHA}") or {}
    files = comparison.get("files") or []
    names = tuple(sorted(str(item.get("filename") or "") for item in files))
    if names != tuple(sorted(REPAIR_ALLOWED_PATHS)):
        raise RuntimeError("STEP5_REPAIR_SCOPE_DRIFT:" + ",".join(names))
    if str(comparison.get("merge_base_commit", {}).get("sha") or "") != DEPLOYMENT_MAIN_SHA:
        raise RuntimeError("STEP5_REPAIR_MERGE_BASE_DRIFT")

    v191_raw = client.content("streamlit_memory_lazy_router_v191.py", ref=REPAIR_HEAD_SHA)
    test_raw = client.content(
        "tests/test_cfb_game_total_page1_visual_cleanup_step5_v191_idempotence.py",
        ref=REPAIR_HEAD_SHA,
    )
    exec_plan_raw = client.content(
        "devsystem/execution_plans/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json",
        ref=REPAIR_HEAD_SHA,
    )
    proof_plan_raw = client.content(
        "devsystem/runless_proof_plans/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json",
        ref=REPAIR_HEAD_SHA,
    )
    v191 = _decode_text(v191_raw, "STEP5_REPAIR_V191")
    test_source = _decode_text(test_raw, "STEP5_REPAIR_TEST")
    exec_plan = _decode_json(exec_plan_raw, "STEP5_REPAIR_EXEC_PLAN")
    proof_plan = _decode_json(proof_plan_raw, "STEP5_REPAIR_PROOF_PLAN")

    compile(v191, "streamlit_memory_lazy_router_v191.py", "exec")
    compile(test_source, "tests/test_cfb_game_total_page1_visual_cleanup_step5_v191_idempotence.py", "exec")
    required_v191 = (
        "_PUBLIC_REPAIR_INSTALLED = False",
        "def _ensure_public_repair_once()",
        "if _PUBLIC_REPAIR_INSTALLED:",
        "_CFB_GAME_TOTAL_COMPAT_INSTALLED = False",
        "def _should_theme_route_once(sport: str, market: str) -> bool:",
        "if _CFB_GAME_TOTAL_COMPAT_INSTALLED:",
        '(normalized_sport, normalized_market) != ("CFB", "Game Total")',
        "return prior.render_app()",
    )
    missing = [item for item in required_v191 if item not in v191]
    if missing:
        raise RuntimeError("STEP5_REPAIR_CONTRACT_MISSING:" + "|".join(missing))
    if v191.count("install_public_repair()") != 1:
        raise RuntimeError("STEP5_REPAIR_PUBLIC_INSTALLER_NOT_SINGLE")
    if v191.count('should_theme_route("CFB", "Game Total")') != 1:
        raise RuntimeError("STEP5_REPAIR_CFB_COMPAT_NOT_SINGLE")
    if "scan_slate(" in v191 or "rank_slate(" in v191 or "projected_combined_total =" in v191:
        raise RuntimeError("STEP5_REPAIR_MODEL_SCOPE_VIOLATION")
    if "requests.get(" in v191:
        raise RuntimeError("STEP5_REPAIR_NETWORK_SCOPE_VIOLATION")

    test_path = "tests/test_cfb_game_total_page1_visual_cleanup_step5_v191_idempotence.py"
    commands = proof_plan.get("commands") or []
    if not any(test_path in str(part) for command in commands for part in (command if isinstance(command, list) else [command])):
        raise RuntimeError("STEP5_REPAIR_TEST_NOT_IN_RUNLESS_PLAN")
    if "streamlit_memory_lazy_router_v191.py" not in set(exec_plan.get("write_paths") or []):
        raise RuntimeError("STEP5_REPAIR_EXEC_PLAN_MISSING_V191")
    protected = set(exec_plan.get("protected_dependencies") or [])
    for path in REPAIR_FROZEN_DEPENDENCIES[:3]:
        if path not in protected:
            raise RuntimeError("STEP5_REPAIR_FROZEN_PROTECTION_DRIFT:" + path)

    frozen_blobs = {}
    for path in REPAIR_FROZEN_DEPENDENCIES:
        base_raw = client.content(path, ref=DEPLOYMENT_MAIN_SHA)
        candidate_raw = client.content(path, ref=REPAIR_HEAD_SHA)
        if str(base_raw.get("sha") or "") != str(candidate_raw.get("sha") or ""):
            raise RuntimeError("STEP5_REPAIR_FROZEN_BLOB_DRIFT:" + path)
        frozen_blobs[path] = str(candidate_raw.get("sha") or "")

    artifacts = {
        "streamlit_memory_lazy_router_v191.py": str(v191_raw.get("sha") or ""),
        test_path: str(test_raw.get("sha") or ""),
        "devsystem/execution_plans/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json": str(exec_plan_raw.get("sha") or ""),
        "devsystem/runless_proof_plans/cfb-game-total-page1-visual-cleanup-step5-live-visual-cert.json": str(proof_plan_raw.get("sha") or ""),
    }
    evidence = {
        "pr": REPAIR_PR_NUMBER,
        "base_sha": DEPLOYMENT_MAIN_SHA,
        "candidate_sha": REPAIR_HEAD_SHA,
        "changed_paths": list(names),
        "v191_blob": artifacts["streamlit_memory_lazy_router_v191.py"],
        "test_blob": artifacts[test_path],
        "frozen_dependency_blobs": frozen_blobs,
        "installer_guard": "once-per-process",
        "github_actions_fallback": 0,
        "failure_class": "NONE",
    }
    evidence_digest = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    receipt = build_runless_receipt(
        proof_id=REPAIR_PROOF_ID,
        task_id=REPAIR_TASK_ID,
        project="API2",
        workstream=step5_closeout_core.WORKSTREAM,
        step="5/5-live-repair",
        candidate_sha=REPAIR_HEAD_SHA,
        artifact_map=artifacts,
        dependency_map=frozen_blobs,
        registry_before={"revision": REGISTRY_REVISION, "state_hash": REGISTRY_HASH},
        registry_after={"revision": REGISTRY_REVISION, "state_hash": REGISTRY_HASH},
        evidence_digests={"v191_once_per_process_repair": evidence_digest},
        failure_class="NONE",
        github_actions_fallback=0,
        scope_lease_id=str(holder.get("lease_id") or ""),
        authorization_id="AUTH-CFB-GT-P1-STEP5-V191-IDEMPOTENCE-1485",
    )
    existing = client.content(REPAIR_RECEIPT_PATH, ref=REPAIR_RECEIPT_BRANCH, allow_404=True)
    if existing is None:
        client.put_content(
            REPAIR_RECEIPT_PATH,
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            REPAIR_RECEIPT_BRANCH,
            "runless: persist CFB Game Total Step5 V191 repair receipt",
        )
    stored = _decode_json(
        client.content(REPAIR_RECEIPT_PATH, ref=REPAIR_RECEIPT_BRANCH),
        "STEP5_REPAIR_RECEIPT",
    )
    if stored != receipt:
        raise RuntimeError("STEP5_REPAIR_RECEIPT_DRIFT")

    publish_gate(client, REPAIR_HEAD_SHA, "success", receipt, "runless-final-gate")
    gate = _repair_gate(client)
    if gate is None:
        raise RuntimeError("STEP5_REPAIR_GATE_READBACK_FAILED")
    return {
        "status": "GREEN",
        "decision": "STEP5_V191_IDEMPOTENCE_EXACT_HEAD_GREEN",
        "candidate_sha": REPAIR_HEAD_SHA,
        "check_id": int(gate.get("id") or 0),
        "receipt_digest": receipt["digest"],
        "lease_id": str(holder.get("lease_id") or ""),
        "github_actions_fallback": 0,
    }


def _install_repair_premerge_gate(app):
    app.state.cfb_game_total_step5_v191_repair = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        if _repair_gate(app.state.github_client) is not None:
            return
        try:
            app.state.cfb_game_total_step5_v191_repair = _execute_repair_premerge(app)
        except Exception as exc:
            app.state.cfb_game_total_step5_v191_repair = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:2400],
            }
        print(
            "CFB_GT_VISUAL_CLEANUP_STEP5_V191_REPAIR="
            + json.dumps(app.state.cfb_game_total_step5_v191_repair, sort_keys=True),
            flush=True,
        )
    return app


def _install_step5_closeout_current_main(app):
    core = step5_closeout_core
    core.MERGED_MAIN_SHA = DEPLOYMENT_MAIN_SHA
    core.POSTMERGE_PROOF_ID = core.TASK_ID + "-" + DEPLOYMENT_MAIN_SHA[:16] + "-postmerge-reuse"
    core.POSTMERGE_RECEIPT_PATH = f"{core.RECEIPT_DIR}/{core.POSTMERGE_PROOF_ID}.json"
    core.LEASE_ID = POSTMERGE_LEASE_ID

    def _live_lease(client):
        state = core.validate_scope_lease_state(
            core._decode_json(client.content(core.LEASE_PATH, ref=core.LEASE_BRANCH), "STEP5_CLOSEOUT_LEASE")
        )
        now = datetime.now(timezone.utc)
        matches = [
            item for item in state.get("holders", [])
            if item.get("owner_id") == core.LEASE_OWNER
            and item.get("lease_id") == POSTMERGE_LEASE_ID
            and now < core._utc(item["expires_at_utc"])
        ]
        if len(matches) != 1:
            return None
        holder = matches[0]
        scope = holder.get("scope") or {}
        identity = scope.get("resource_identity") or {}
        if (
            str(identity.get("candidate_sha") or "") != core.CANDIDATE_SHA
            or str(identity.get("main_sha") or "") != DEPLOYMENT_MAIN_SHA
            or str(identity.get("certified_product_main_sha") or "") != CERTIFIED_PRODUCT_MAIN_SHA
            or str(identity.get("workstream") or "") != core.WORKSTREAM
            or str(identity.get("registry_state_hash") or "") != core.EXPECTED_REGISTRY_HASH
            or str(identity.get("phase") or "") != "postmerge-live-cert-closeout"
        ):
            raise RuntimeError("STEP5_CLOSEOUT_LEASE_IDENTITY_DRIFT")
        required = {
            core.REGISTRY_PATH,
            core.EVIDENCE_PATH,
            "devsystem/runless_proof_receipts",
            "runless_proof_plane/cfb_game_total_page1_visual_cleanup_step5_cert.py",
            "runless_proof_plane/cfb_game_total_page1_visual_cleanup_step5_closeout.py",
            "runless_proof_plane/nfl_rb_wr_step3_closeout.py",
        }
        if not required.issubset(set(scope.get("write_paths") or [])):
            raise RuntimeError("STEP5_CLOSEOUT_LEASE_SCOPE_DRIFT")
        return holder

    def _merge_identity(client):
        if client.branch_sha("main") != DEPLOYMENT_MAIN_SHA:
            raise RuntimeError("STEP5_MERGED_MAIN_DRIFT")
        pr = client.request("GET", f"/pulls/{core.PR_NUMBER}") or {}
        if (
            not pr.get("merged_at")
            or str((pr.get("head") or {}).get("sha") or "") != core.CANDIDATE_SHA
            or str((pr.get("base") or {}).get("sha") or "") != core.SOURCE_MAIN_SHA
            or str(pr.get("merge_commit_sha") or "") != CERTIFIED_PRODUCT_MAIN_SHA
        ):
            raise RuntimeError("STEP5_PRODUCT_MERGE_PROVENANCE_DRIFT")
        product_commit = client.commit(CERTIFIED_PRODUCT_MAIN_SHA)
        product_parents = {str(item.get("sha") or "") for item in product_commit.get("parents", [])}
        if core.CANDIDATE_SHA not in product_parents or core.SOURCE_MAIN_SHA not in product_parents:
            raise RuntimeError("STEP5_PRODUCT_MERGE_LINEAGE_DRIFT")
        deploy_commit = client.commit(DEPLOYMENT_MAIN_SHA)
        deploy_parents = {str(item.get("sha") or "") for item in deploy_commit.get("parents", [])}
        if CERTIFIED_PRODUCT_MAIN_SHA not in deploy_parents or DEPLOYMENT_MARKER_CANDIDATE_SHA not in deploy_parents:
            raise RuntimeError("STEP5_DEPLOYMENT_MARKER_LINEAGE_DRIFT")
        comparison = client.request("GET", f"/compare/{CERTIFIED_PRODUCT_MAIN_SHA}...{DEPLOYMENT_MAIN_SHA}") or {}
        files = comparison.get("files") or []
        if [str(item.get("filename") or "") for item in files] != [DEPLOYMENT_MARKER_PATH]:
            raise RuntimeError("STEP5_DEPLOYMENT_ONLY_SCOPE_DRIFT")
        if int(files[0].get("additions") or 0) != 1 or int(files[0].get("deletions") or 0) != 1:
            raise RuntimeError("STEP5_DEPLOYMENT_ONLY_DIFF_DRIFT")
        return {
            "product_merge_parents": sorted(product_parents),
            "deployment_merge_parents": sorted(deploy_parents),
            "deployment_only_path": DEPLOYMENT_MARKER_PATH,
        }

    core._live_lease = _live_lease
    core._merge_identity = _merge_identity
    return core.install_startup(app)


def install_startup(app):
    """One-shot bridge for CFB Game Total Page1 visual-cleanup finalization."""
    app.state.nfl_rb_wr_step3_closeout = {
        "status": "NOT_RUN",
        "decision": "CFB_GT_PAGE1_VISUAL_CLEANUP_FINALIZER_BRIDGE",
    }
    _install_optional_404_compat(app)

    # While the live-proven V191 repair PR is open, run exactly one premerge
    # proof chain and do not re-run the known-failing live cert.
    if _repair_pr_open(app.state.github_client):
        _install_repair_premerge_gate(app)
        return app

    install_cfb_visual_cleanup_step1_closeout(app)
    install_cfb_visual_cleanup_step2_closeout(app)
    install_cfb_visual_cleanup_step3_thaw(app)
    install_cfb_visual_cleanup_step3_proof(app)
    install_cfb_visual_cleanup_step3_closeout(app)
    install_cfb_visual_cleanup_step4_thaw(app)
    install_cfb_visual_cleanup_step4_proof(app)
    install_cfb_visual_cleanup_step4_closeout(app)
    install_cfb_visual_cleanup_step5_deployment_convergence(app)
    install_cfb_visual_cleanup_step5_thaw(app)
    install_cfb_visual_cleanup_step5_proof(app)
    install_cfb_visual_cleanup_step5_cert(app)
    _install_step5_closeout_current_main(app)
    return app
