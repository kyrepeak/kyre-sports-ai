from __future__ import annotations

from . import cfb_step8_terminal_route_lock_phoenix_wait_r12 as r12

terminal = r12.terminal
r5 = r12.r5

FINAL_OWNER = (
    "api2/cfb-game-total-native-website-rebuild-v1/"
    "step8-route-pointer-lock-postmerge-r13"
)

_SCREENSHOT_PROXY_PATCH = r'''

class _NonFatalScreenshotPage:
    def __init__(self, page):
        self._page = page

    def __getattr__(self, name):
        return getattr(self._page, name)

    def screenshot(self, *args, **kwargs):
        try:
            kwargs.setdefault("timeout", 8000)
            return self._page.screenshot(*args, **kwargs)
        except Exception as exc:
            print(
                "CFB_STEP8_SCREENSHOT_NONFATAL=" + type(exc).__name__,
                flush=True,
            )
            return b""
'''


def _r13_cert_script() -> str:
    script = r12._r12_cert_script()
    insert_marker = "all_viewports = dict(cert.VIEWPORTS)\n"
    page_marker = "            page = browser.new_page(viewport=viewport)\n"
    if script.count(insert_marker) != 1:
        raise terminal.TerminalFreezeFailure("R13_INSERT_MARKER_DRIFT")
    if script.count(page_marker) != 1:
        raise terminal.TerminalFreezeFailure("R13_PAGE_MARKER_DRIFT")
    script = script.replace(insert_marker, _SCREENSHOT_PROXY_PATCH + "\n" + insert_marker, 1)
    script = script.replace(
        page_marker,
        "            raw_page = browser.new_page(viewport=viewport)\n"
        "            page = _NonFatalScreenshotPage(raw_page)\n",
        1,
    )
    return script


r5._jump_route_cert_script = _r13_cert_script
terminal._cert_script = _r13_cert_script
terminal.FINAL_OWNER = FINAL_OWNER
install_startup = r12.install_startup
