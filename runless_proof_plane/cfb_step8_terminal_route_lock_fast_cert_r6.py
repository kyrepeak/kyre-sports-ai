from __future__ import annotations

from . import cfb_step8_terminal_route_lock_r5 as r5

FAST_FIND_TIMEOUT_SECONDS = 25.0
FAST_VISIBLE_TIMEOUT_MS = 25000
FINAL_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-route-pointer-lock-postmerge-r6"


def _fast_cert_script():
    return f'''
import json
from urllib.parse import urlencode
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert

cert.SOURCE_MAIN_SHA = "{r5.PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{r5.HANDOFF_CERT_DAY}"


def _jump_route_for_day(base_url, selected_day):
    query = urlencode({{
        "ks_jump_sport": "CFB",
        "ks_jump_market": "Game Total",
        "ks_cfb_game_total_date": str(selected_day),
    }})
    return base_url.rstrip("/") + "/?" + query


cert._route_for_day = _jump_route_for_day

_original_find = cert._find_cfb_frame

def _bounded_find(
    page,
    *,
    required_markers=(),
    required_testids=(),
    timeout_seconds=120.0,
):
    return _original_find(
        page,
        required_markers=required_markers,
        required_testids=required_testids,
        timeout_seconds=min(float(timeout_seconds), {FAST_FIND_TIMEOUT_SECONDS}),
    )

cert._find_cfb_frame = _bounded_find

_original_visible = cert._visible

def _bounded_visible(frame, testid, timeout_ms=90000):
    return _original_visible(
        frame,
        testid,
        timeout_ms=min(int(timeout_ms), {FAST_VISIBLE_TIMEOUT_MS}),
    )

cert._visible = _bounded_visible

_original_page1 = cert._page1_result

def _guarded_page1(page, name, artifact_dir, base_url):
    row, selected_url, event_id = _original_page1(page, name, artifact_dir, base_url)
    frame, _ = cert._find_cfb_frame(
        page,
        required_markers=cert.PAGE1_FRAME_MARKERS,
        required_testids=(cert.PHOENIX_DAY_TESTID, cert.PAGE1_TESTID),
        timeout_seconds={FAST_FIND_TIMEOUT_SECONDS},
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
    base_url="{r5.terminal.PRODUCTION_URL}",
    artifact_dir="artifacts/cfb-game-total-step8-terminal-r6",
)
if not cert.evidence_is_terminal_green(payload):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")
print("CFB_STEP8_R5_PUBLIC_PAYLOAD=" + json.dumps(payload, sort_keys=True), flush=True)
'''


# R5 owns the fail-closed lease/reconcile/freeze/ledger/readback chain.
# Replace only its slow public-cert script and bind a fresh terminal lease owner.
r5._jump_route_cert_script = _fast_cert_script
r5.terminal._cert_script = _fast_cert_script
r5.terminal.FINAL_OWNER = FINAL_OWNER
install_startup = r5.install_startup
