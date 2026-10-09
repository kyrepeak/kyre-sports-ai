from __future__ import annotations

from datetime import datetime, timezone

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
POSTMERGE_LEASE_ID = "SCOPE-LEASE-FADB448ED17923F50A5CAA33"


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
