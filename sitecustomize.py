"""Guarded one-shot launchers for CFB Step-4 Runless control actions.

All launchers are inert unless the exact Runless uvicorn service is explicitly
armed. Triggers are removed from the process environment before worker threads
start, preventing recursive/duplicate execution in child processes.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback

SERVICE_ID = "srv-db23fee7bikc73ca8ua0"
MODE_ENV = "RPP_CFB_STEP4_REPAIR_MODE"
MERGED_ENV = "RPP_CFB_STEP4_REPAIR_MERGED_SHA"
PUBLIC_CLOSEOUT_ENV = "RPP_CFB_STEP4_PUBLIC_REPAIR_CLOSEOUT_ON_START"
EVENT_PAGE_CLOSEOUT_ENV = "RPP_CFB_STEP4_EVENT_PAGE_SIDE_MARKET_CLOSEOUT_ON_START"


def _configure_repair(repair) -> None:
    repair.THAW_ID = "THAW-CFB-GAME-TOTAL-PAGE1-V2-STEP4-LIVE-OWNER-REPAIR-R2"
    repair.OWNER_ID = "api2-cfb-game-total-page1-v2-step4-live-owner-repair"
    repair.TARGET_HEAD = "2a099dda3b535288fa48da46feec23329fc05056"
    repair.BASE_MAIN = "b814704b35aac99a3bfc2db05d84dcbc2d0b9c47"
    repair.AUTHORIZATION_ID = "AUTH-CFB-GAME-TOTAL-PAGE1-V2-STEP4-LIVE-OWNER-REPAIR-R2"
    repair.THAW_FILES = {
        "cfb_game_total_page1_v2_step4_activation.py": {
            "from_blob": "4b347939afe92feea0365068265ecf8887da0360",
            "to_blob": "97679c0f375d6cf47b69997cec0ab943bb0ad285",
        },
        "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json": {
            "from_blob": "7b4e473dc700cbcee8f6fab08ade6c61db88dabe",
            "to_blob": "f5f598f08a61307aaace4f760de56a49fa9e06ce",
        },
        "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json": {
            "from_blob": "8de9a5c0a2d2865db08a3f4b3354a741c8020a81",
            "to_blob": "07c2daf34702bc1819160ddc367c7d89977a326d",
        },
        "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json": {
            "from_blob": "f52d1977494a822e923bfe6053e120e6447c1675",
            "to_blob": "b721db751dd2ce316555e04fb2f797f935a6f0d6",
        },
    }
    repair.ARTIFACT_PATHS = (
        "cfb_game_total_page1_step4_prediction_market_v1.py",
        "cfb_game_total_page1_step4_side_market_v1.py",
        "cfb_game_total_clean_page_v37.py",
        "cfb_game_total_clean_page_v38.py",
        "cfb_game_total_page1_v2_step4_activation.py",
        "kyre_universal_components_v1.py",
        "tests/test_cfb_game_total_page1_v2_step4_prediction_market.py",
        "tests/test_cfb_game_total_page1_v2_step4_runtime_repair.py",
        "tests/test_cfb_game_total_page1_v2_step4_live_owner_repair.py",
        "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
        "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
        "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json",
    )
    repair.WRITE_PATHS = (
        "cfb_game_total_page1_v2_step4_activation.py",
        "tests/test_cfb_game_total_page1_v2_step4_live_owner_repair.py",
        "devsystem/execution_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
        "devsystem/runless_proof_plans/cfb-game-total-page1-v2-step4-prediction-market.json",
        "devsystem/task_ledgers/cfb-game-total-page1-v2-step4-prediction-market.json",
    )


def _run(mode: str, merged_sha: str) -> None:
    try:
        from runless_proof_plane.config import Settings
        from runless_proof_plane.github_app import GithubAppAuth
        from runless_proof_plane.github_client import GithubClient
        from runless_proof_plane.orchestrator import ProofOrchestrator
        from runless_proof_plane import cfb_step4_runtime_repair as repair

        _configure_repair(repair)
        settings = Settings.from_env()
        if settings.bootstrap:
            raise RuntimeError("CFB_STEP4_REPAIR_FULL_RUNLESS_MODE_REQUIRED")
        client = GithubClient(GithubAppAuth(settings), settings.repository)
        if mode == "prepare":
            result = repair.prepare_and_prove(
                client,
                settings=settings,
                orchestrator=ProofOrchestrator(),
                receipts={},
            )
        elif mode == "finalize":
            result = repair.finalize_freeze(client, merged_sha)
        else:
            raise RuntimeError("CFB_STEP4_REPAIR_UNKNOWN_MODE:" + mode)
        print("CFB_STEP4_REPAIR_CONTROL_RESULT=" + json.dumps(result, sort_keys=True, default=str), flush=True)
    except Exception as exc:
        packet = {
            "status": "FAIL",
            "mode": mode,
            "error": type(exc).__name__,
            "detail": str(exc)[:700],
            "traceback": traceback.format_exc(limit=8)[-2600:],
        }
        print("CFB_STEP4_REPAIR_CONTROL_RESULT=" + json.dumps(packet, sort_keys=True), flush=True)


def _run_public_closeout() -> None:
    try:
        time.sleep(20)
        from runless_proof_plane.config import Settings
        from runless_proof_plane.github_app import GithubAppAuth
        from runless_proof_plane.github_client import GithubClient
        from runless_proof_plane.cfb_game_total_page1_v2_step4_public_repair_closeout import run_and_print

        settings = Settings.from_env()
        if settings.bootstrap:
            raise RuntimeError("CFB_STEP4_PUBLIC_CLOSEOUT_FULL_RUNLESS_MODE_REQUIRED")
        client = GithubClient(GithubAppAuth(settings), settings.repository)
        run_and_print(client)
    except Exception as exc:
        packet = {
            "status": "FAIL",
            "error": type(exc).__name__,
            "detail": str(exc)[:700],
            "traceback": traceback.format_exc(limit=8)[-2600:],
        }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP4_PUBLIC_REPAIR_CLOSEOUT="
            + json.dumps(packet, sort_keys=True),
            flush=True,
        )


def _run_event_page_closeout() -> None:
    try:
        time.sleep(20)
        from runless_proof_plane.config import Settings
        from runless_proof_plane.github_app import GithubAppAuth
        from runless_proof_plane.github_client import GithubClient
        from runless_proof_plane.cfb_game_total_page1_v2_step4_event_page_side_market_closeout import run_and_print

        settings = Settings.from_env()
        if settings.bootstrap:
            raise RuntimeError("CFB_STEP4_EVENT_PAGE_CLOSEOUT_FULL_RUNLESS_MODE_REQUIRED")
        client = GithubClient(GithubAppAuth(settings), settings.repository)
        run_and_print(client)
    except Exception as exc:
        packet = {
            "status": "FAIL",
            "error": type(exc).__name__,
            "detail": str(exc)[:700],
            "traceback": traceback.format_exc(limit=8)[-2600:],
        }
        print(
            "CFB_GAME_TOTAL_PAGE1_V2_STEP4_EVENT_PAGE_SIDE_MARKET_CLOSEOUT="
            + json.dumps(packet, sort_keys=True),
            flush=True,
        )


def _is_exact_uvicorn_service() -> bool:
    argv0 = os.path.basename(sys.argv[0] or "").lower()
    return (
        "uvicorn" in argv0
        and os.environ.get("RENDER_SERVICE_ID", "").strip() == SERVICE_ID
    )


if _is_exact_uvicorn_service():
    _mode = os.environ.pop(MODE_ENV, "").strip().lower()
    _merged = os.environ.pop(MERGED_ENV, "").strip().lower()
    _public_closeout = os.environ.pop(PUBLIC_CLOSEOUT_ENV, "").strip()
    _event_page_closeout = os.environ.pop(EVENT_PAGE_CLOSEOUT_ENV, "").strip()
    if _mode:
        threading.Thread(
            target=_run,
            args=(_mode, _merged),
            daemon=True,
            name="cfb-step4-runtime-repair-control",
        ).start()
    if _public_closeout == "1":
        threading.Thread(
            target=_run_public_closeout,
            daemon=True,
            name="cfb-step4-public-repair-closeout",
        ).start()
    if _event_page_closeout == "1":
        threading.Thread(
            target=_run_event_page_closeout,
            daemon=True,
            name="cfb-step4-event-page-side-market-closeout",
        ).start()
