from __future__ import annotations

import json

from . import cfb_games_on_day_step2_visual_closeout as base


def execute(app):
    client = app.state.github_client
    tree = base._verify_merge(client)
    premerge = base._load_premerge_receipt(client)
    registry = base.GithubRegistryBackend(client).read_registry()
    merged = base._ensure_merged_receipt_and_gate(
        client,
        tree=tree,
        premerge=premerge,
        registry=registry,
    )
    frozen = base._atomic_forward_port_and_freeze(client, tree=tree, premerge=premerge)
    lease = base._release_lease(client)
    if client.branch_sha("main") != base.MAIN_SHA:
        raise base.Step2VisualCloseoutFailure("MAIN_MOVED_AFTER_CLOSEOUT")
    return {
        "status": "GREEN",
        "decision": "CFB_GAMES_ON_DAY_STEP2_VISUAL_GREEN_FROZEN",
        "main_sha": base.MAIN_SHA,
        "source_candidate_sha": base.SOURCE_CANDIDATE_SHA,
        "premerge_check_id": base.PREMERGE_CHECK_ID,
        "premerge_receipt_digest": base.PREMERGE_DIGEST,
        "merged_receipt_digest": str(merged["receipt"]["digest"]),
        "canonical_public_probe_required": False,
        "freeze_token": base.FREEZE_TOKEN,
        "freeze": frozen,
        "lease": lease,
        "static_evidence_reexecuted": False,
        "github_actions_fallback": 0,
    }


def install_startup(app):
    app.state.cfb_games_on_day_step2_final_authority = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_games_on_day_step2_final_authority = execute(app)
        except Exception as exc:
            app.state.cfb_games_on_day_step2_final_authority = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAMES_ON_DAY_STEP2_FINAL_AUTHORITY="
            + json.dumps(
                app.state.cfb_games_on_day_step2_final_authority,
                sort_keys=True,
                default=str,
            ),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
