from __future__ import annotations

from . import cfb_step8_terminal_route_lock_progressive_page2_r8 as r8

terminal = r8.terminal
fast = r8.fast

patch = r8._PROGRESSIVE_PAGE2_PATCH
patch = patch.replace(
    "frame, scans = cert._find_cfb_frame(",
    "frame, scans = _original_find(",
    1,
)
patch = patch.replace("timeout_seconds=25.0", "timeout_seconds=90.0", 1)
patch = patch.replace("timeout_ms=45000", "timeout_ms=60000", 1)
r8._PROGRESSIVE_PAGE2_PATCH = patch

terminal.FINAL_OWNER = (
    "api2/cfb-game-total-native-website-rebuild-v1/"
    "step8-route-pointer-lock-postmerge-r9"
)
install_startup = r8.install_startup
