from __future__ import annotations

import json
import threading

import requests

from devsystem import cfb_game_total_mobile_production_step8_v1 as cert
from . import cfb_step8_postmerge_terminal_freeze as base


class Step8FinalizationAuthorityFailure(RuntimeError):
    pass


def _reused_public_receipt(app) -> dict:
    """Converge the last mile without re-running already-proven UI matrices.

    The recovery merge changed only requirements.txt to force Streamlit redeploy.
    Product/cert artifacts must therefore be byte-identical to the certified
    recovery head. We verify that invariant, then require live Streamlit health
    and the certified Render API identity before freezing.
    """
    client = app.state.github_client
    main_tree = client.tree_blobs(base.MAIN_SHA)
    recovery_tree = client.tree_blobs(base.RECOVERY_HEAD)

    protected = [path for path in base.FINAL_ARTIFACTS if path != base.REQUIREMENTS]
    drift = [
        path for path in protected
        if not main_tree.get(path) or main_tree.get(path) != recovery_tree.get(path)
    ]
    if drift:
        raise Step8FinalizationAuthorityFailure(
            "PRODUCT_EVIDENCE_REUSE_BLOCKED:" + ",".join(sorted(drift))
        )

    health = requests.get(
        base.PRODUCTION_URL.rstrip("/") + "/_stcore/health",
        headers={"Cache-Control": "no-cache", "User-Agent": "Kyre-Step8-Finalizer/1.0"},
        timeout=20,
    )
    if health.status_code != 200:
        raise Step8FinalizationAuthorityFailure(
            f"STREAMLIT_HEALTH_RED:{health.status_code}"
        )

    render_identity = cert.verify_render_identity()
    return {
        "status": "PUBLIC_GREEN_REUSED",
        "authority": "FINALIZATION_AUTHORITY_100_CONVERGENCE_V1",
        "reason": "recovery merge changed deployment dependency only; certified product artifacts are byte-identical",
        "main_sha": base.MAIN_SHA,
        "recovery_head": base.RECOVERY_HEAD,
        "protected_product_artifact_count": len(protected),
        "product_artifact_drift": [],
        "streamlit_health_status": health.status_code,
        "render_identity": render_identity,
        "github_actions_fallback": 0,
    }


def execute(app) -> dict:
    runless_receipt = base._verify_merge_and_runless(app.state.github_client)
    public_receipt = _reused_public_receipt(app)
    result = base._freeze(app, public_receipt, runless_receipt)
    result["finalization_authority"] = "FINALIZATION_AUTHORITY_100_CONVERGENCE_V1"
    result["redundant_proof_runs"] = 0
    return result


def install_startup(app):
    app.state.cfb_step8_finalization_authority = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _start():
        def worker():
            try:
                app.state.cfb_step8_finalization_authority = execute(app)
            except Exception as exc:
                app.state.cfb_step8_finalization_authority = {
                    "status": "FAIL",
                    "error": type(exc).__name__,
                    "detail": str(exc)[:12000],
                }
            print(
                "CFB_STEP8_FINALIZATION_AUTHORITY="
                + json.dumps(app.state.cfb_step8_finalization_authority, sort_keys=True, default=str),
                flush=True,
            )
        threading.Thread(
            target=worker,
            daemon=True,
            name="cfb-step8-finalization-authority",
        ).start()

    return app
