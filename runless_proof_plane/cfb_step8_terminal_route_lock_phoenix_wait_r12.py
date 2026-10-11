from __future__ import annotations

from . import cfb_step8_terminal_route_lock_single_pass_r11 as r11

terminal = r11.terminal
r5 = r11.r5

FINAL_OWNER = (
    "api2/cfb-game-total-native-website-rebuild-v1/"
    "step8-route-pointer-lock-postmerge-r12"
)

_CURRENT_DAY_PATCH = r'''

def _rerender_safe_current_day_result(page, name, artifact_dir, base_url):
    page.goto(
        cert.current_day_route(base_url),
        wait_until="domcontentloaded",
        timeout=120000,
    )
    frame, scans = cert._find_cfb_frame(
        page,
        required_markers=("PHOENIX TIME",),
        required_testids=(cert.PHOENIX_DAY_TESTID,),
        timeout_seconds=30.0,
    )
    cert._visible(frame, cert.PHOENIX_DAY_TESTID)
    deadline = time.monotonic() + 35.0
    body = ""
    while time.monotonic() < deadline:
        try:
            body = frame.locator("body").inner_text(timeout=5000)
            runtime_error = cert._runtime_error(body)
            overflow = cert._horizontal_overflow(frame)
            if runtime_error:
                raise cert.Step8MobileProductionFailure(
                    f"CURRENT_DAY_RUNTIME_ERROR:{name}:{runtime_error}"
                )
            if overflow:
                raise cert.Step8MobileProductionFailure(
                    f"CURRENT_DAY_HORIZONTAL_OVERFLOW:{name}"
                )
            if "TODAY" in body and "PHOENIX TIME" in body:
                screenshot = artifact_dir / f"cfb_game_total_step8_{name}_current_day.png"
                page.screenshot(path=str(screenshot), full_page=True)
                return {
                    "phoenix_day_selector_visible": True,
                    "phoenix_today_visible": True,
                    "authoritative_phoenix_day": cert.authoritative_phoenix_day(),
                    "horizontal_overflow": False,
                    "runtime_error": "",
                    "frame_scan": scans,
                    "screenshot": str(screenshot),
                }
        except cert.Step8MobileProductionFailure:
            raise
        except Exception:
            frame, scans = cert._find_cfb_frame(
                page,
                required_markers=("PHOENIX TIME",),
                required_testids=(cert.PHOENIX_DAY_TESTID,),
                timeout_seconds=30.0,
            )
        time.sleep(0.25)
    raise cert.Step8MobileProductionFailure(
        f"CURRENT_DAY_PHOENIX_TODAY_MISSING:{name}"
    )


cert._current_day_result = _rerender_safe_current_day_result
'''


def _r12_cert_script() -> str:
    script = r11._r11_cert_script()
    marker = "cert._page1_result = _guarded_page1\n"
    if script.count(marker) != 1:
        raise terminal.TerminalFreezeFailure("R12_CERT_SCRIPT_MARKER_DRIFT")
    return script.replace(marker, marker + _CURRENT_DAY_PATCH, 1)


r5._jump_route_cert_script = _r12_cert_script
terminal._cert_script = _r12_cert_script
terminal.FINAL_OWNER = FINAL_OWNER
install_startup = r11.install_startup
