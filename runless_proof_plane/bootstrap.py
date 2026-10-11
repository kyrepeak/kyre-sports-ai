from __future__ import annotations
import os

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_SUBMIT_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_CLOSEOUT_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_PREMERGE_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_CLOSEOUT_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_DIAGNOSTIC_ON_START"] = "0"

from .api import app
from . import cfb_step8_terminal_freeze_event_guard_r3 as terminal


def _verified_premerge_authority(client):
    receipt = terminal._decode(
        client.content(terminal.PREMERGE_RECEIPT_PATH, ref=terminal.RECEIPT_BRANCH)
    )
    if (
        receipt.get("proof_id") != terminal.PREMERGE_PROOF_ID
        or receipt.get("candidate_sha") != terminal.CANDIDATE_SHA
        or receipt.get("digest") != terminal.PREMERGE_RECEIPT_DIGEST
        or receipt.get("failure_class") != "NONE"
    ):
        raise terminal.TerminalFreezeFailure("PREMERGE_AUTHORITY_DRIFT")
    return {
        "proof_id": terminal.PREMERGE_PROOF_ID,
        "receipt_digest": terminal.PREMERGE_RECEIPT_DIGEST,
    }


def _activated_cert_script():
    return f'''
import json
import time
from devsystem import browser_qa_v1 as nav
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert

cert.SOURCE_MAIN_SHA = "{terminal.PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{terminal.HANDOFF_CERT_DAY}"
_original_find = cert._find_cfb_frame


def _activate_game_total(page):
    frame, _ = nav._find_app_frame(page)
    sports = nav._read_sport_options(page, frame)
    if "College Football" not in sports:
        raise cert.Step8MobileProductionFailure(
            "CFB_SPORT_SELECTOR_OPTION_MISSING:" + json.dumps(sports, ensure_ascii=False)
        )
    nav._choose(page, frame, 0, "College Football")
    market = frame.get_by_role("combobox", name="🎯 CFB Market", exact=True)
    market.wait_for(state="visible", timeout=45000)
    nav._choose(page, frame, 1, "Game Total")
    deadline = time.monotonic() + 90.0
    last_body = ""
    while time.monotonic() < deadline:
        try:
            last_body = frame.locator("body").inner_text(timeout=5000)
        except Exception:
            last_body = ""
        if "PHOENIX TIME" in last_body and (
            "GAMES ON THIS DAY" in last_body or "GAME DAY" in last_body
        ):
            return
        page.wait_for_timeout(500)
    raise cert.Step8MobileProductionFailure(
        "CFB_GAME_TOTAL_UI_ACTIVATION_TIMEOUT:" + last_body[:1200]
    )


def _activated_find(
    page,
    *,
    required_markers=(),
    required_testids=(),
    timeout_seconds=120.0,
):
    page1_or_day = (
        cert.PHOENIX_DAY_TESTID in required_testids
        or cert.PAGE1_TESTID in required_testids
        or "PHOENIX TIME" in required_markers
    )
    if page1_or_day:
        _activate_game_total(page)
    return _original_find(
        page,
        required_markers=required_markers,
        required_testids=required_testids,
        timeout_seconds=timeout_seconds,
    )


cert._find_cfb_frame = _activated_find
_original_page1 = cert._page1_result


def _guarded_page1(page, name, artifact_dir, base_url):
    row, selected_url, event_id = _original_page1(page, name, artifact_dir, base_url)
    frame, _ = _original_find(
        page,
        required_markers=cert.PAGE1_FRAME_MARKERS,
        required_testids=(cert.PHOENIX_DAY_TESTID, cert.PAGE1_TESTID),
        timeout_seconds=30.0,
    )
    wrapper_event = cert._event_from_url(page.url)
    frame_event = cert._event_from_url(str(getattr(frame, "url", "") or ""))
    if wrapper_event or frame_event:
        raise cert.Step8MobileProductionFailure(
            f"PAGE1_AUTO_EVENT_VISIBLE:{{name}}:{{wrapper_event}}:{{frame_event}}"
        )
    row["auto_event_visible"] = False
    return row, selected_url, event_id


cert._page1_result = _guarded_page1
payload = cert.run_public(
    base_url="{terminal.PRODUCTION_URL}",
    artifact_dir="artifacts/cfb-game-total-step8-terminal-r4",
)
if not cert.evidence_is_terminal_green(payload):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")
print("CFB_STEP8_R4_PUBLIC_PAYLOAD=" + json.dumps(payload, sort_keys=True), flush=True)
'''


terminal._ensure_authority = _verified_premerge_authority
terminal._cert_script = _activated_cert_script
terminal.install_startup(app)
