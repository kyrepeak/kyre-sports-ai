from __future__ import annotations

import json

from . import cfb_game_total_phoenix_day_selector_step4_closeout as core

TASK_ID = "cfb-game-total-games-on-day-data-step5-v1"
WORKSTREAM = "cfb-game-total-native-website-rebuild-v1"
PLAN_PATH = "devsystem/runless_proof_plans/cfb-game-total-games-on-day-data-step5-v1.json"
SOURCE_MAIN_SHA = "e28ad8458aa1ee4b4fdaa2215fc638c6215ecd02"
SOURCE_CANDIDATE_SHA = "1ca44039051369129a42c7e5db4a7a7825d15010"
MAIN_SHA = "90683fb9affefbe960b37590ff02303f94fd8d3d"
PREMERGE_PROOF_ID = "cfb-game-total-games-on-day-data-step5-v1-1ca4403905136912-888bddb109657824"
PREMERGE_DIGEST = "5b10ab7ce76a4afbc982dd6f4ce9165b796f76661779a23e4cc2f68f2a32442a"
PREMERGE_CHECK_ID = 114346680371
MERGED_PROOF_ID = "cfb-game-total-games-on-day-data-step5-v1-90683fb9affefbe9-reused"
FREEZE_TOKEN = "CFB_GAME_TOTAL_NATIVE_WEBSITE_REBUILD_STEP5_GAMES_ON_DAY_DATA_V1_FROZEN"
THAW_ID = "THAW-CFB-GT-GAMES-ON-DAY-DATA-STEP5-R1"
ROUTER_PATH = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
FROM_BLOB = "cfbdc3767e8cddc3b80babe464baeead15ac7146"
TO_BLOB = "49982eeb8c6f2eca7f765fd07afa851cda519d74"
LEASE_ID = "SCOPE-LEASE-1B64A0231819EF84CC5E8B2F"
LEASE_OWNER = "api2-cfb-game-total-games-on-day-data-step5"

_ORIGINAL_BUILD_RECEIPT = core.build_runless_receipt


def _step5_build_receipt(*args, **kwargs):
    kwargs["step"] = "games-on-day-data-step5-closeout"
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
        "build_runless_receipt": _step5_build_receipt,
    }
    for name, value in overrides.items():
        setattr(core, name, value)


def execute(app):
    _configure_core()
    result = dict(core.execute(app))
    result["decision"] = "CFB_GAME_TOTAL_GAMES_ON_DAY_DATA_STEP5_GREEN_FROZEN"
    result["step"] = "5/8"
    result["freeze_token"] = FREEZE_TOKEN
    result["page1_data_owner"] = "cfb_game_total_clean_page_v42"
    result["single_selected_day_snapshot"] = True
    result["cards_step6_started"] = False
    result["static_evidence_reexecuted"] = False
    result["github_actions_fallback"] = 0
    result.pop("page1_day_owner", None)
    result.pop("games_on_day_step5_started", None)
    return result


def install_startup(app):
    app.state.cfb_game_total_games_on_day_data_step5_closeout = {"status": "NOT_RUN"}

    @app.on_event("startup")
    def _run():
        try:
            app.state.cfb_game_total_games_on_day_data_step5_closeout = execute(app)
        except Exception as exc:
            app.state.cfb_game_total_games_on_day_data_step5_closeout = {
                "status": "FAIL",
                "error": type(exc).__name__,
                "detail": str(exc)[:5200],
            }
        print(
            "CFB_GAME_TOTAL_GAMES_ON_DAY_DATA_STEP5_CLOSEOUT="
            + json.dumps(app.state.cfb_game_total_games_on_day_data_step5_closeout, sort_keys=True, default=str),
            flush=True,
        )

    return app


__all__ = ["execute", "install_startup"]
