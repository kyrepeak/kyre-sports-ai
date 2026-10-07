from __future__ import annotations

import json

from . import wnba_pra_history_step1_closeout as base

SOURCE_MAIN_SHA = "aba567ca13d1a01d9ef783efcff47b784b414a5c"
SOURCE_CANDIDATE_SHA = "1f15353bdaba0b955bf464df22923e5f28394266"
MAIN_SHA = "e313222d0c4e55a6217f4aaf62d3afed7aeead13"
PREMERGE_PROOF_ID = "wnba-pra-history-multisource-v1-step1-1f15353bdaba0b95-71e660d153b4f2b8"
PREMERGE_DIGEST = "565f12e0b5f621bcf358def8f437529726586084bccce811d925b7ebb1fa3847"
PREMERGE_CHECK_ID = 113070429806
MERGED_PROOF_ID = "wnba-pra-history-multisource-v1-step1-e313222d0c4e55a6-reused"
EXPECTED_REGISTRY_REVISION = 188
EXPECTED_REGISTRY_HASH = "de3a935ee3f9bc0b90bee22c65ee879ade4a58a4041dbf26d76a84bc8727179f"
FREEZE_PATHS = (
    "devsystem/runless_proof_plans/wnba-pra-history-multisource-v1-step1.json",
    "devsystem/task_ledgers/wnba-pra-history-multisource-v1-step1.json",
    "docs/superpowers/plans/2026-10-07-wnba-pra-history-multisource-step1.md",
    "sports_api/api/wnba_pra_detail_bundle.py",
    "sports_api/wnba_pra_history_multisource_v1.py",
    "tests/test_wnba_pra_history_multisource_v1_step1.py",
    "tests/test_wnba_pra_history_bref_fallback_v1.py",
)

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
    "FREEZE_PATHS": FREEZE_PATHS,
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
