from __future__ import annotations

import json
import os

from . import task17_step5_atomic_closeout as core
from .models import ProofRequest
from .prove import execute_proof_request

TASK_ID = "cfb-game-total-page1-v2-step4-prediction-market"
WORKSTREAM = "cfb-game-total-page1-v2"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json"
SOURCE_MAIN_SHA = "8ad570f765daf0884fe6f963f10982b05a414b60"
SOURCE_CANDIDATE_SHA = "6ce49ccd5cee2a0b39af9404f6ed413e78e49f1b"
MAIN_SHA = "091226472ad03d11d86fa2843fc37c3dc2830023"
PREMERGE_PROOF_ID = "cfb-game-total-page1-v2-step4-prediction-market-6ce49ccd5cee2a0b-acf7c2a164830ffb"
PREMERGE_DIGEST = "9829d7b5bcc735f42cccdf86ededcb09e6434435e8cf037f59533c4bcabc1710"
PREMERGE_CHECK_ID = 113165457178
MERGED_PROOF_ID = "cfb-game-total-page1-v2-step4-prediction-market-091226472ad03d11-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PREDICTION_MARKET_FROZEN"
FREEZE_PATHS = (
    "cfb_game_total_page1_step4_prediction_market_v1.py",
    "cfb_game_total_page1_step4_side_market_v1.py",
    "cfb_game_total_clean_page_v37.py",
    "cfb_game_total_page1_v2_step4_activation.py",
    "kyre_universal_components_v1.py",
    "tests/test_cfb_game_total_page1_v2_step4_prediction_market.py",
    "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
    "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
    "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json",
)
LEASE_ID = "SCOPE-LEASE-68C177FAE1838F91703FC3CF"
LEASE_OWNER = "cfb-game-total-page1-v2-step4-closeout"
EXPECTED_REGISTRY_REVISION = 196
EXPECTED_REGISTRY_HASH = "b6779f297868cae2388f18bc60bc43ae42ee181742bb5f55ff87f43d1668d8c1"
EXPECTED_EVENT_HASH = "6127af782bb3bdf62793e077d4ed5282b2fce5df7324860ee1f224d595e1f789"

NFL_RB_WR_SUBMIT_FLAG = "RPP_NFL_RB_WR_STEP1_SUBMIT_ON_START"


def _bindings() -> dict[str, object]:
    return {
        "TASK_ID": TASK_ID,
        "WORKSTREAM": WORKSTREAM,
        "PLAN_PATH": PLAN_PATH,
        "SOURCE_MAIN_SHA": SOURCE_MAIN_SHA,
        "SOURCE_CANDIDATE_SHA": SOURCE_CANDIDATE_SHA,
        "MAIN_SHA": MAIN_SHA,
        "PREMERGE_PROOF_ID": PREMERGE_PROOF_ID,
        "PREMERGE_DIGEST": PREMERGE_DIGEST,
        "PREMERGE_CHECK_ID": PREMERGE_CHECK_ID,
        "MERGED_PROOF_ID": MERGED_PROOF_ID,
        "FREEZE_TOKEN": FREEZE_TOKEN,
        "FREEZE_PATHS": FREEZE_PATHS,
        "LEASE_ID": LEASE_ID,
        "LEASE_OWNER": LEASE_OWNER,
        "EXPECTED_REGISTRY_REVISION": EXPECTED_REGISTRY_REVISION,
        "EXPECTED_REGISTRY_HASH": EXPECTED_REGISTRY_HASH,
        "EXPECTED_EVENT_HASH": EXPECTED_EVENT_HASH,
    }


def execute(client):
    saved = {name: getattr(core, name) for name in _bindings()}
    original_build_receipt = core.build_runless_receipt

    def _build_receipt(**kwargs):
        kwargs["step"] = "cfb-game-total-page1-v2-step4-prediction-market"
        return original_build_receipt(**kwargs)

    try:
        for name, value in _bindings().items():
            setattr(core, name, value)
        core.build_runless_receipt = _build_receipt
        result = dict(core.execute(client))
    finally:
        core.build_runless_receipt = original_build_receipt
        for name, value in saved.items():
            setattr(core, name, value)

    decision = str(result.get("decision") or "")
    result["decision"] = decision.replace(
        "RUNLESS_TASK17_STEP5", "CFB_GAME_TOTAL_PAGE1_V2_STEP4"
    )
    result["closeout_engine_reused"] = "RUNLESS_TASK17_STEP5_ATOMIC_CLOSEOUT"
    result["step"] = "4/9"
    return result


def _run_nfl_rb_wr_step1_submit(app) -> None:
    app.state.nfl_rb_wr_step1_submit = {"status": "NOT_RUN"}
    if os.getenv(NFL_RB_WR_SUBMIT_FLAG, "").strip() != "1":
        return
    try:
        request = ProofRequest(
            task_id=os.environ["RPP_NFL_RB_WR_STEP1_TASK_ID"],
            workstream=os.environ["RPP_NFL_RB_WR_STEP1_WORKSTREAM"],
            candidate_sha=os.environ["RPP_NFL_RB_WR_STEP1_CANDIDATE_SHA"],
            lease_id=os.environ["RPP_NFL_RB_WR_STEP1_LEASE_ID"],
            authorization_id=os.environ["RPP_NFL_RB_WR_STEP1_AUTHORIZATION_ID"],
            expected_main_sha=os.environ["RPP_NFL_RB_WR_STEP1_EXPECTED_MAIN_SHA"],
        )
        app.state.nfl_rb_wr_step1_submit = execute_proof_request(
            request,
            settings=app.state.settings,
            github_client=app.state.github_client,
            orchestrator=app.state.orchestrator,
            receipts=app.state.receipts,
        )
    except Exception as exc:
        app.state.nfl_rb_wr_step1_submit = {
            "status": "FAIL",
            "error": type(exc).__name__,
            "detail": str(exc)[:1800],
        }
    print(
        "NFL_RB_WR_STEP1_RUNLESS_SUBMIT="
        + json.dumps(app.state.nfl_rb_wr_step1_submit, sort_keys=True),
        flush=True,
    )


def install_startup(app):
    app.state.cfb_game_total_page1_v2_step4_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_page1_v2_step4_closeout = execute(app.state.github_client)
        except Exception as exc:
            app.state.cfb_game_total_page1_v2_step4_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:1800],
            }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP4_ATOMIC_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_page1_v2_step4_closeout, sort_keys=True),
            flush=True,
        )
        _run_nfl_rb_wr_step1_submit(app)

    return app
