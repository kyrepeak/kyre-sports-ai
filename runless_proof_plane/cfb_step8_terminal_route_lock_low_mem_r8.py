from __future__ import annotations

from . import cfb_step8_terminal_route_lock_oom_recovery_r7 as r7

fast = r7.fast
r5 = fast.r5
terminal = r7.terminal

PAGE2_ANCHOR_TESTID = "gtp2s8-final"
PAGE1_FRAME_TIMEOUT_SECONDS = 30.0
PAGE2_FRAME_TIMEOUT_SECONDS = 35.0
SECTION_VISIBLE_TIMEOUT_MS = 45000
FINAL_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-route-pointer-lock-postmerge-r8"


def _r8_cert_script() -> str:
    return f'''
import gc
import json
from urllib.parse import urlencode
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert

cert.SOURCE_MAIN_SHA = "{r5.PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{r5.HANDOFF_CERT_DAY}"

PAGE2_ANCHOR_TESTID = "{PAGE2_ANCHOR_TESTID}"


def _jump_route_for_day(base_url, selected_day):
    query = urlencode({{
        "ks_jump_sport": "CFB",
        "ks_jump_market": "Game Total",
        "ks_cfb_game_total_date": str(selected_day),
    }})
    return base_url.rstrip("/") + "/?" + query


cert._route_for_day = _jump_route_for_day

_original_find = cert._find_cfb_frame


def _r8_find(
    page,
    *,
    required_markers=(),
    required_testids=(),
    timeout_seconds=120.0,
):
    required_testids = tuple(required_testids or ())
    if tuple(required_testids) == tuple(cert.PAGE2_REQUIRED_TESTIDS):
        return _original_find(
            page,
            required_markers=required_markers,
            required_testids=(PAGE2_ANCHOR_TESTID,),
            timeout_seconds=min(float(timeout_seconds), {PAGE2_FRAME_TIMEOUT_SECONDS}),
        )
    return _original_find(
        page,
        required_markers=required_markers,
        required_testids=required_testids,
        timeout_seconds=min(float(timeout_seconds), {PAGE1_FRAME_TIMEOUT_SECONDS}),
    )


cert._find_cfb_frame = _r8_find

_original_visible = cert._visible


def _r8_visible(frame, testid, timeout_ms=90000):
    return _original_visible(
        frame,
        testid,
        timeout_ms=min(int(timeout_ms), {SECTION_VISIBLE_TIMEOUT_MS}),
    )


cert._visible = _r8_visible

_original_page1 = cert._page1_result


def _guarded_page1(page, name, artifact_dir, base_url):
    row, selected_url, event_id = _original_page1(
        page, name, artifact_dir, base_url
    )
    frame, _ = cert._find_cfb_frame(
        page,
        required_markers=cert.PAGE1_FRAME_MARKERS,
        required_testids=(cert.PHOENIX_DAY_TESTID, cert.PAGE1_TESTID),
        timeout_seconds={PAGE1_FRAME_TIMEOUT_SECONDS},
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

all_viewports = dict(cert.VIEWPORTS)
rows = {{}}
template = None

for name, viewport in all_viewports.items():
    cert.VIEWPORTS = {{name: viewport}}
    payload = cert.run_public(
        base_url="{terminal.PRODUCTION_URL}",
        artifact_dir=f"artifacts/cfb-game-total-step8-terminal-r8/{{name}}",
    )
    if template is None:
        template = payload
    rows[name] = payload["viewports"][name]
    gc.collect()

cert.VIEWPORTS = all_viewports
combined = dict(template or {{}})
combined["viewports"] = rows

if set(rows) != set(all_viewports):
    raise SystemExit("R8_VIEWPORT_SET_DRIFT")
if not cert.evidence_is_terminal_green(combined):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")

print(
    "CFB_STEP8_R5_PUBLIC_PAYLOAD=" + json.dumps(combined, sort_keys=True),
    flush=True,
)
'''


# Preserve the proven R5/R7 ownership, freeze, ledger and readback chain.
# Replace only the browser-cert strategy and lease owner identity.
r5._jump_route_cert_script = _r8_cert_script
terminal._cert_script = _r8_cert_script
terminal.FINAL_OWNER = FINAL_OWNER

install_startup = r7.install_startup
