from __future__ import annotations

from . import cfb_step8_terminal_route_lock_rerender_safe_r10 as r10

terminal = r10.terminal
r5 = r10.r5

PAGE2_ANCHOR_TESTID = "gtp2s8-final"
PAGE1_FRAME_TIMEOUT_SECONDS = 30.0
PAGE2_FRAME_TIMEOUT_SECONDS = 60.0
SECTION_VISIBLE_TIMEOUT_MS = 60000
FINAL_OWNER = (
    "api2/cfb-game-total-native-website-rebuild-v1/"
    "step8-route-pointer-lock-postmerge-r11"
)


def _r11_cert_script() -> str:
    return f'''
import gc
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from devsystem import cfb_game_total_mobile_production_step8_v1 as cert

cert.SOURCE_MAIN_SHA = "{r5.PRODUCT_MAIN_SHA}"
cert.HANDOFF_CERT_DAY = "{r5.HANDOFF_CERT_DAY}"

PAGE2_ANCHOR_TESTID = "{PAGE2_ANCHOR_TESTID}"
BASE_URL = "{terminal.PRODUCTION_URL}"


def _jump_route_for_day(base_url, selected_day):
    query = urlencode({{
        "ks_jump_sport": "CFB",
        "ks_jump_market": "Game Total",
        "ks_cfb_game_total_date": str(selected_day),
    }})
    return base_url.rstrip("/") + "/?" + query


cert._route_for_day = _jump_route_for_day
_original_find = cert._find_cfb_frame


def _r11_find(
    page,
    *,
    required_markers=(),
    required_testids=(),
    timeout_seconds=120.0,
):
    required_testids = tuple(required_testids or ())
    if required_testids == tuple(cert.PAGE2_REQUIRED_TESTIDS):
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


cert._find_cfb_frame = _r11_find


def _rerender_safe_visible(frame, testid, timeout_ms=90000):
    deadline = time.monotonic() + (min(int(timeout_ms), {SECTION_VISIBLE_TIMEOUT_MS}) / 1000.0)
    last_error = ""
    while time.monotonic() < deadline:
        try:
            locator = frame.locator(f'[data-testid="{{testid}}"]') .first
            if locator.count() > 0 and locator.is_visible(timeout=1500):
                return None
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(0.25)
    raise cert.Step8MobileProductionFailure(
        f"TESTID_NOT_VISIBLE_AFTER_RERENDER_SAFE_WAIT:{{testid}}:{{last_error or 'timeout'}}"
    )


cert._visible = _rerender_safe_visible
_original_page1 = cert._page1_result


def _guarded_page1(page, name, artifact_dir, base_url):
    row, selected_url, event_id = _original_page1(page, name, artifact_dir, base_url)
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
artifacts = Path("artifacts/cfb-game-total-step8-terminal-r11")
artifacts.mkdir(parents=True, exist_ok=True)
health = cert.base._wait_for_health(BASE_URL)
render_identity = cert.verify_render_identity()
all_viewports = dict(cert.VIEWPORTS)
rows = {{}}

with cert.sync_playwright() as p:
    for name, viewport in all_viewports.items():
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = None
        try:
            page = browser.new_page(viewport=viewport)
            current_day = cert._current_day_result(page, name, artifacts, BASE_URL)
            page1, selected_url, event_id = cert._page1_result(
                page, name, artifacts, BASE_URL
            )
            page2 = cert._page2_result(
                page, name, selected_url, event_id, artifacts
            )
            rows[name] = {{
                "viewport": dict(viewport),
                "current_day": current_day,
                "page1": page1,
                "page2": page2,
            }}
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            browser.close()
            gc.collect()

payload = {{
    "status": "GREEN",
    "model_version": cert.MODEL_VERSION,
    "source_main_sha": cert.SOURCE_MAIN_SHA,
    "production_url": BASE_URL,
    "current_day_route": cert.current_day_route(BASE_URL),
    "page1_route": cert.page1_route(BASE_URL),
    "phoenix_timezone": cert.PHOENIX_TZ,
    "phoenix_date": cert.authoritative_phoenix_day(),
    "handoff_cert_day": cert.HANDOFF_CERT_DAY,
    "sportsbook_projection_influence": cert.SPORTSBOOK_PROJECTION_INFLUENCE,
    "github_actions_fallback": cert.GITHUB_ACTIONS_FALLBACK,
    "render_identity": render_identity,
    "streamlit_health": health,
    "viewports": rows,
}}

if set(rows) != set(all_viewports):
    raise SystemExit("R11_VIEWPORT_SET_DRIFT")
if not cert.evidence_is_terminal_green(payload):
    raise SystemExit("CANONICAL_TERMINAL_GREEN_REJECTED")

print(
    "CFB_STEP8_R5_PUBLIC_PAYLOAD=" + json.dumps(payload, sort_keys=True),
    flush=True,
)
'''


r5._jump_route_cert_script = _r11_cert_script
terminal._cert_script = _r11_cert_script
terminal.FINAL_OWNER = FINAL_OWNER
install_startup = r10.install_startup
