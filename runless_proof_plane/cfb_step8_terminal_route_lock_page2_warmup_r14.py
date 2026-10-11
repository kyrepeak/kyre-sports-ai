from __future__ import annotations

from . import cfb_step8_terminal_route_lock_screenshot_nonfatal_r13 as r13

terminal = r13.terminal
r5 = r13.r5
r11 = r13.r12.r11

PAGE2_FRAME_TIMEOUT_SECONDS = 100.0
FINAL_OWNER = (
    "api2/cfb-game-total-native-website-rebuild-v1/"
    "step8-route-pointer-lock-postmerge-r14"
)


def _r14_cert_script() -> str:
    r11.PAGE2_FRAME_TIMEOUT_SECONDS = PAGE2_FRAME_TIMEOUT_SECONDS
    return r13._r13_cert_script()


r5._jump_route_cert_script = _r14_cert_script
terminal._cert_script = _r14_cert_script
terminal.FINAL_OWNER = FINAL_OWNER
install_startup = r13.install_startup
