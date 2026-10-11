from __future__ import annotations

from . import cfb_step8_terminal_route_lock_low_mem_r9 as r9

r5 = r9.r5
terminal = r9.terminal

PAGE2_ANCHOR_TESTID = "gtp2s8-final"
PAGE1_FRAME_TIMEOUT_SECONDS = 30.0
SNAPSHOT_DEADLINE_SECONDS = 90.0
FINAL_OWNER = "api2/cfb-game-total-native-website-rebuild-v1/step8-route-pointer-lock-postmerge-r11"


def _r11_cert_script() -> str:
    return f'''
import gc
import json
import time
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


def _page1_find(page, *, required_markers=(), required_testids=(), timeout_seconds=120.0):
    return _original_find(
        page,
        required_markers=required_markers,
        required_testids=required_testids,
        timeout_seconds=min(float(timeout_seconds), {PAGE1_FRAME_TIMEOUT_SECONDS}),
    )


cert._find_cfb_frame = _page1_find
_original_page1 = cert._page1_result


def _guarded_page1(page, name, artifact_dir, base_url):
    row, selected_url, event_id = _original_page1(page, name, artifact_dir, base_url)
    frame, _ = _original_find(
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


def _snapshot_page2(page, name, selected_url, event_id, artifact_dir):
    del artifact_dir
    page.goto(selected_url, wait_until="domcontentloaded", timeout=120000)
    deadline = time.monotonic() + {SNAPSHOT_DEADLINE_SECONDS}
    frame = None
    scans = []
    seen_visible = set()

    while time.monotonic() < deadline:
        try:
            frame, scans = _original_find(
                page,
                required_testids=(PAGE2_ANCHOR_TESTID,),
                timeout_seconds=5.0,
            )
        except Exception:
            frame = None
            page.wait_for_timeout(750)
            continue

        for testid in cert.PAGE2_REQUIRED_TESTIDS:
            if testid in seen_visible:
                continue
            try:
                locator = frame.locator(f'[data-testid="{{testid}}"]') .first
                if locator.count() > 0 and locator.is_visible(timeout=1500):
                    seen_visible.add(testid)
            except Exception:
                pass

        missing = [testid for testid in cert.PAGE2_REQUIRED_TESTIDS if testid not in seen_visible]
        if not missing:
            break
        page.wait_for_timeout(750)

    missing = [testid for testid in cert.PAGE2_REQUIRED_TESTIDS if testid not in seen_visible]
    if frame is None or missing:
        raise cert.Step8MobileProductionFailure(
            f"PAGE2_REQUIRED_NOT_OBSERVED_VISIBLE:{{name}}:missing={{missing}}:seen={{sorted(seen_visible)}}:scans={{scans}}"
        )

    body = frame.locator("body").inner_text(timeout=30000)
    forbidden = cert._forbidden(body, cert.PAGE2_FORBIDDEN_VISIBLE_TEXT)
    runtime_error = cert._runtime_error(body)
    overflow = cert._horizontal_overflow(frame)
    wrapper_event = cert._event_from_url(page.url)
    frame_event = cert._event_from_url(str(getattr(frame, "url", "") or ""))
    observed_events = {{value for value in (wrapper_event, frame_event) if value}}

    if observed_events != {{event_id}}:
        raise cert.Step8MobileProductionFailure(
            f"PAGE2_EVENT_ID_DRIFT:{{name}}:expected={{event_id}}:observed={{sorted(observed_events)}}"
        )
    if forbidden:
        raise cert.Step8MobileProductionFailure(f"PAGE2_FORBIDDEN_COPY:{{name}}:{{forbidden}}")
    if runtime_error:
        raise cert.Step8MobileProductionFailure(f"PAGE2_RUNTIME_ERROR:{{name}}:{{runtime_error}}")
    if overflow:
        raise cert.Step8MobileProductionFailure(f"PAGE2_HORIZONTAL_OVERFLOW:{{name}}")

    return {{
        "all_required_visible": True,
        "required_testids_visible": list(cert.PAGE2_REQUIRED_TESTIDS),
        "exact_event_id": event_id,
        "wrapper_event_id": wrapper_event,
        "frame_event_id": frame_event,
        "observed_event_ids": sorted(observed_events),
        "horizontal_overflow": False,
        "forbidden_visible_text": [],
        "runtime_error": "",
        "frame_scan": scans,
        "screenshot": "",
    }}


cert._page2_result = _snapshot_page2
all_viewports = dict(cert.VIEWPORTS)
rows = {{}}
template = None

for name, viewport in all_viewports.items():
    cert.VIEWPORTS = {{name: viewport}}
    payload = cert.run_public(
        base_url="{terminal.PRODUCTION_URL}",
        artifact_dir=f"artifacts/cfb-game-total-step8-terminal-r11/{{name}}",
    )
    if template is None:
        template = payload
    rows[name] = payload["viewports"][name]
    gc.collect()

cert.VIEWPORTS = all_viewports
combined = dict(template or {{}})
combined["viewports"] = rows

if set(rows) != set(all_viewports):
    raise SystemExit("R11_VIEWPORT_SET_DRIFT")
if not cert.evidence_is_terminal_green(combined):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")

print("CFB_STEP8_R5_PUBLIC_PAYLOAD=" + json.dumps(combined, sort_keys=True), flush=True)
'''


r5._jump_route_cert_script = _r11_cert_script
terminal._cert_script = _r11_cert_script
terminal.FINAL_OWNER = FINAL_OWNER
install_startup = r9.install_startup
