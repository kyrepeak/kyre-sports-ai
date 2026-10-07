from __future__ import annotations

import json

from . import wnba_pra_history_step1_closeout as base

SOURCE_MAIN_SHA = "42b9bcf3465af8aca41141a1d2713d5731ea6c00"
SOURCE_CANDIDATE_SHA = "a6570bfc5f8cdc4fb78f6d0ec385afd906b82791"
MAIN_SHA = "f84bf63f966a52ed3cd1d6275bedc2a0cf3b125b"
PREMERGE_PROOF_ID = "wnba-pra-history-multisource-v1-step1-a6570bfc5f8cdc4f-9bf40a36a97ceb76"
PREMERGE_DIGEST = "33776e3a7e37bc90647c686713bff88ee28122c910676304b78e4f75003f8c3b"
PREMERGE_CHECK_ID = 113049559939
MERGED_PROOF_ID = "wnba-pra-history-multisource-v1-step1-f84bf63f966a52ed-reused"
EXPECTED_REGISTRY_REVISION = 186
EXPECTED_REGISTRY_HASH = "21d594e5f52335bb2b5eba22a23da5e467856ee238f2730a3459c29c99f03f6f"

_OVERRIDES = {
    "SOURCE_MAIN_SHA": SOURCE_MAIN_SHA,
    "SOURCE_CANDIDATE_SHA": SOURCE_CANDIDATE_SHA,
    "MAIN_SHA": MAIN_SHA,
    "PREMERGE_PROOF_ID": PREMERGE_PROOF_ID,
    "PREMERGE_DIGEST": PREMERGE_DIGEST,
    "PREMERGE_CHECK_ID": PREMERGE_CHECK_ID,
    "MERGED_PROOF_ID": MERGED_PROOF_ID,
    "EXPECTED_REGISTRY_REVISION": EXPECTED_REGISTRY_REVISION,
    "EXPECTED_REGISTRY_HASH": EXPECTED_REGISTRY_HASH,
}


def execute(client):
    saved = {name: getattr(base, name) for name in _OVERRIDES}
    try:
        for name, value in _OVERRIDES.items():
            setattr(base, name, value)
        return base.execute(client)
    finally:
        for name, value in saved.items():
            setattr(base, name, value)


def install_startup(app):
    app.state.wnba_pra_history_step1_final_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.wnba_pra_history_step1_final_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.wnba_pra_history_step1_final_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "WNBA_PRA_HISTORY_STEP1_FINAL_CLOSEOUT="
            + json.dumps(app.state.wnba_pra_history_step1_final_closeout, sort_keys=True),
            flush=True,
        )

    return app
