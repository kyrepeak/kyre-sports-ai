"""CFB Game Total Page 1 visual cleanup Step 2 activation.

Uses the existing unfrozen CFB Game Total theme seam during V34 render. V160 may
purge/reimport CFB modules before each exact Game Total render; by the time the
CFB-only theme builder runs, the fresh Step-3 presentation module is loaded.
This installer swaps only that presentation builder for the current render
session. Frozen routers/pages/shells remain byte-identical.
"""
from __future__ import annotations

import importlib
from threading import RLock

from cfb_game_total_page1_visual_cleanup_step2_top_shell_v1 import build_top_shell_html

MODEL_VERSION = "CFB GAME TOTAL PAGE1 VISUAL CLEANUP • STEP 2 CFB-THEME ACTIVATION V2"
PRESENTATION_MODULE = "cfb_game_total_page1_step3_presentation_v1"
PROOF_MARKER = "CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_STEP2_TOP_SHELL_ACTIVE"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0
FROZEN_SOURCE_MUTATIONS = 0

_INSTALL_ATTR = "_cfb_game_total_visual_cleanup_step2_installed"
_LOCK = RLock()


def install_step2_top_shell() -> bool:
    """Bind the Step-2 hero builder onto the fresh frozen Step-3 presentation seam."""
    with _LOCK:
        presentation = importlib.import_module(PRESENTATION_MODULE)
        current = getattr(presentation, "build_matchup_hero_html", None)
        if current is build_top_shell_html:
            return True
        if current is None:
            raise RuntimeError("Step-2 presentation seam is unavailable")

        setattr(build_top_shell_html, _INSTALL_ATTR, True)
        setattr(build_top_shell_html, "_cfb_gt_step2_original", current)
        presentation.build_matchup_hero_html = build_top_shell_html
        return True


__all__ = [
    "FROZEN_SOURCE_MUTATIONS",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "PRESENTATION_MODULE",
    "PROOF_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "install_step2_top_shell",
]
