from __future__ import annotations

from . import cfb_step8_terminal_route_lock_low_mem_r9 as r9

terminal = r9.terminal
r5 = r9.r5

_original_script = r9._r9_cert_script

_RERENDER_SAFE_VISIBLE = r'''

import time


def _rerender_safe_visible(frame, testid, timeout_ms=90000):
    deadline = time.monotonic() + (int(timeout_ms) / 1000.0)
    last_error = ""
    while time.monotonic() < deadline:
        try:
            locator = frame.locator(f'[data-testid="{testid}"]').first
            if locator.count() > 0 and locator.is_visible(timeout=1500):
                return None
        except Exception as exc:
            last_error = type(exc).__name__
        time.sleep(0.25)
    raise cert.Step8MobileProductionFailure(
        f"TESTID_NOT_VISIBLE_AFTER_RERENDER_SAFE_WAIT:{testid}:{last_error or 'timeout'}"
    )


cert._visible = _rerender_safe_visible
'''


def _r10_cert_script() -> str:
    script = _original_script()
    marker = "_original_page1 = cert._page1_result"
    if script.count(marker) != 1:
        raise terminal.TerminalFreezeFailure("R10_CERT_SCRIPT_MARKER_DRIFT")
    return script.replace(marker, _RERENDER_SAFE_VISIBLE + "\n" + marker, 1)


r5._jump_route_cert_script = _r10_cert_script
terminal._cert_script = _r10_cert_script
terminal.FINAL_OWNER = (
    "api2/cfb-game-total-native-website-rebuild-v1/"
    "step8-route-pointer-lock-postmerge-r10"
)
install_startup = r9.install_startup
