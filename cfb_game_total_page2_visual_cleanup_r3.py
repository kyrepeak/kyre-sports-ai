"""MONSTER CFB Game Total Page 2 — visual cleanup R3.

Presentation-only successor to frozen R2. R3 preserves R2's selected-event,
multi-source, model, probability, market, Line Lab, Best Bet, and Stage 6
behavior. It fixes the final public Stage 7 presentation defect by removing the
nested legacy Team Evidence header from the generated HTML and enforcing compact
logo dimensions in markup as well as CSS.
"""
from __future__ import annotations

from collections.abc import Mapping
import re
from threading import RLock
from typing import Any, Callable

import cfb_game_total_page2_visual_cleanup_r2 as prior

MODEL_VERSION = "MONSTER CFB GAME TOTAL PAGE2 VISUAL CLEANUP R3"
ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_VISUAL_CLEANUP_R3_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_VISUAL_CLEANUP_R3_FROZEN"
R2_PARENT = "cfb_game_total_page2_visual_cleanup_r2"
MARKET = prior.MARKET
SELECTED_GAME_ONLY = True
MULTI_SOURCE_REQUIRED = True
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

_PRESENTATION_LOCK = RLock()
_LEGACY_SECTION_HEAD_RE = re.compile(
    r'\s*<div class="gt204-sectionhead">.*?</div>\s*',
    re.DOTALL,
)
_LOGO_BOX_STYLE = (
    "width:46px;height:46px;min-width:46px;max-width:46px;"
    "min-height:46px;max-height:46px;overflow:hidden;display:flex;"
    "align-items:center;justify-content:center;flex:0 0 46px"
)
_LOGO_IMAGE_STYLE = (
    "width:46px!important;height:46px!important;max-width:46px!important;"
    "max-height:46px!important;object-fit:contain!important;display:block"
)


def _compact_stage7_markup(html: str) -> str:
    """Remove the legacy nested heading and bound logos without touching data."""
    cleaned = _LEGACY_SECTION_HEAD_RE.sub("\n", str(html), count=1)
    cleaned = cleaned.replace(
        'data-testid="gtp2r2-team-evidence"',
        'data-testid="gtp2r3-team-evidence"',
        1,
    )
    cleaned = cleaned.replace(
        '<div class="gt204-logo">',
        f'<div class="gt204-logo" style="{_LOGO_BOX_STYLE}">',
    )
    cleaned = re.sub(
        r'<img\b(?![^>]*\bstyle=)',
        f'<img style="{_LOGO_IMAGE_STYLE}"',
        cleaned,
    )
    cleaned = cleaned.replace(
        'class="gt160-evidence-logo-fallback"',
        f'class="gt160-evidence-logo-fallback" style="{_LOGO_IMAGE_STYLE}"',
    )
    return cleaned


def build_stage7_clean_html(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    """Use the frozen R2 evidence contract while removing its legacy subheader."""
    return _compact_stage7_markup(prior.build_stage7_clean_html(identity, away, home))


def _with_r3_stage7(callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    with _PRESENTATION_LOCK:
        original = prior.build_stage7_clean_html
        prior.build_stage7_clean_html = build_stage7_clean_html
        try:
            return callback(*args, **kwargs)
        finally:
            prior.build_stage7_clean_html = original


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _with_r3_stage7(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Page 2 Visual Cleanup R3 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


def render_selected_in_shared_shell() -> Any:
    return _with_r3_stage7(prior.render_selected_in_shared_shell)


__all__ = [
    "ACTIVE_MARKER",
    "FREEZE_TOKEN",
    "MARKET",
    "MODEL_VERSION",
    "MULTI_SOURCE_REQUIRED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_stage7_clean_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_selected_in_shared_shell",
]
