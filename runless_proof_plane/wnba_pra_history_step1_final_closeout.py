from __future__ import annotations

import json

from . import wnba_pra_history_step1_closeout as base

SOURCE_MAIN_SHA = "f84bf63f966a52ed3cd1d6275bedc2a0cf3b125b"
SOURCE_CANDIDATE_SHA = "3a177612513cb5ee33d310efeadedb2eb22723ec"
MAIN_SHA = "aba567ca13d1a01d9ef783efcff47b784b414a5c"
PREMERGE_PROOF_ID = "wnba-pra-history-multisource-v1-step1-3a177612513cb5ee-c1adc2163b06b63d"
PREMERGE_DIGEST = "b2a154373402cb843aa2ce79ca51ed1b4ae31c62cfe4f254654486ab3ddc9881"
PREMERGE_CHECK_ID = 113057967428
MERGED_PROOF_ID = "wnba-pra-history-multisource-v1-step1-aba567ca13d1a01d-reused"
EXPECTED_REGISTRY_REVISION = 188
EXPECTED_REGISTRY_HASH = "de3a935ee3f9bc0b90bee22c65ee879ade4a58a4041dbf26d76a84bc8727179f"

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
