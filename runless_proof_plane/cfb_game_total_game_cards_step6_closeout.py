from __future__ import annotations

import json

from . import cfb_game_total_phoenix_day_selector_step4_closeout as core

TASK_ID = "cfb-game-total-game-cards-step6-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-game-cards-step6-v1.json"
SOURCE_MAIN_SHA = "90683fb9affefbe960b37590ff02303f94fd8d3d"
SOURCE_CANDIDATE_SHA = "16a64a4e4889467fc60685e7343871556bf245cb"
MAIN_SHA = "0baa35045941adfea5d7a5bafb216efbfed42b7a"
PREMERGE_PROOF_ID = "cfb-game-total-game-cards-step6-v1-16a64a4e4889467f-ae28f53ffda17c03"
PREMERGE_DIGEST = "2d4276b22a1badb74770c3d4912c0962101f607e8ecfd36782a3f11412bb6596"
PREMERGE_CHECK_ID = 114352463032
MERGED_PROOF_ID = "cfb-game-total-game-cards-step6-v1-0baa35045941adfe-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP6_GAME_CARDS_V1_FROZEN"
THAW_ID = "THAW-CFB-GT-GAME-CARDS-STEP6-R1"
ROUTER_PATH = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
FROM_BLOB = "49982eeb8c6f2eca7f765fd07afa851cda519d74"
TO_BLOB = "811b0cec681aa1b1b0fddc4c3d4170dd3770dd50"
LEASE_ID = "SCOPE-LEASE-E5F098090918265921B412B0"
LEASE_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step6"

_ORIGINAL_BUILD_RECEIPT = core.build_runless_receipt


def _step6_build_receipt(*args, **kwargs):
    kwargs["step"] = "game-cards-step6-closeout"
    return _ORIGINAL_BUILD_RECEIPT(*args, **kwargs)


def _configure_core() -> None:
    overrides = {
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
        "THAW_ID": THAW_ID,
        "ROUTER_PATH": ROUTER_PATH,
        "FROM_BLOB": FROM_BLOB,
        "TO_BLOB": TO_BLOB,
        "LEASE_ID": LEASE_ID,
        "LEASE_OWNER": LEASE_OWNER,
        "build_runless_receipt": _step6_build_receipt,
    }
    for name, value in overrides.items():
        setattr(core, name, value)


def execute(app):
    _configure_core()
    result = dict(core.execute(app))
    result["decision"] = "CFB_GAME_TOTAL_GAME_CARDS_STEP6_GREEN_FROZEN"
    result["step"] = "6/8"
    result["freeze_token"] = FREEZE_TOKEN
    result["page1_owner"] = "cfb_game_total_clean_page_v43"
    result["data_owner"] = "cfb_game_total_clean_page_v42"
    result["post_purge_card_chain"] = ["step1_layout", "step2_visual", "step3_details", "step4_interaction_mobile"]
    result["step7_started"] = False
    result["static_evidence_reexecuted"] = False
    result["github_actions_fallback"] = 0
    result.pop("page1_day_owner", None)
    result.pop("games_on_day_step5_started", None)
    return result


def install_startup(app):
    app.state.cfb_game_total_game_cards_step6_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_game_cards_step6_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_game_cards_step6_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAME_TOTAL_GAME_CARDS_STEP6_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_game_cards_step6_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
