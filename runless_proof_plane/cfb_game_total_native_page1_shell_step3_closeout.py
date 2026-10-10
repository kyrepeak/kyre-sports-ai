from __future__ import annotations

import json

from . import cfb_game_total_native_routing_step1_closeout as prior

TASK_ID = "cfb-game-total-native-page1-shell-step3-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-native-page1-shell-step3-v1.json"
SOURCE_MAIN_SHA = "a3166e7d980d85b6adb6a064b8ac225befd9b9e3"
SOURCE_CANDIDATE_SHA = "9afe37ec19d2b02aa204dd6158d55f2eae6dd726"
MAIN_SHA = "ac8c6fbec4d97d3e130a8c4f581f495456ad443c"
PREMERGE_PROOF_ID = "cfb-game-total-native-page1-shell-step3-v1-9afe37ec19d2b02a-cfb33652e38afde6"
PREMERGE_DIGEST = "14ac68ffb97d65f5b75ad031558bad37055ddd0c02e53ac0cc00a569b6f0cc3e"
PREMERGE_CHECK_ID = 114338064584
MERGED_PROOF_ID = "cfb-game-total-native-page1-shell-step3-v1-ac8c6fbec4d97d3e-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP3_PAGE1_SHELL_V1_FROZEN"
THAW_ID = "THAW-CFB-GT-NATIVE-PAGE1-SHELL-STEP3-R1"
ROUTER_PATH = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
FROM_BLOB = "7f27ead880acdbe6a272e6d34dfcd55d84a926d0"
TO_BLOB = "7e38d5b3cac89e0ea30fa01d972d8fce85abe66e"
LEASE_ID = "SCOPE-LEASE-D22E83F4CD40ACCD431DD801"
LEASE_OWNER = "api2-cfb-game-total-native-page1-shell-step3"


def _configure() -> None:
    prior.TASK_ID = TASK_ID
    prior.WORKSTREAM = WORKSTREAM
    prior.PLAN_PATH = PLAN_PATH
    prior.SOURCE_MAIN_SHA = SOURCE_MAIN_SHA
    prior.SOURCE_CANDIDATE_SHA = SOURCE_CANDIDATE_SHA
    prior.MAIN_SHA = MAIN_SHA
    prior.PREMERGE_PROOF_ID = PREMERGE_PROOF_ID
    prior.PREMERGE_DIGEST = PREMERGE_DIGEST
    prior.PREMERGE_CHECK_ID = PREMERGE_CHECK_ID
    prior.MERGED_PROOF_ID = MERGED_PROOF_ID
    prior.FREEZE_TOKEN = FREEZE_TOKEN
    prior.THAW_ID = THAW_ID
    prior.ROUTER_PATH = ROUTER_PATH
    prior.FROM_BLOB = FROM_BLOB
    prior.TO_BLOB = TO_BLOB
    prior.LEASE_ID = LEASE_ID
    prior.LEASE_OWNER = LEASE_OWNER


def execute(app):
    _configure()
    result = prior.execute(app)
    result["decision"] = "CFB_GAME_TOTAL_NATIVE_PAGE1_SHELL_STEP3_GREEN_FROZEN"
    result["step"] = "3/8"
    result["page1_shell_owner"] = "cfb_game_total_clean_page_v40"
    result["phoenix_day_selector_started"] = False
    return result


def install_startup(app):
    app.state.cfb_game_total_native_page1_shell_step3_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_native_page1_shell_step3_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_native_page1_shell_step3_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAME_TOTAL_NATIVE_PAGE1_SHELL_STEP3_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_native_page1_shell_step3_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
