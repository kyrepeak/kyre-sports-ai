"""CFB Game Total clean page V45 — unified Page-1 day ownership repair.

Additive successor to frozen V43. V41 remains the only visible Phoenix-local day
selector, V42 remains the one selected-day snapshot owner, V43 remains the game-
card owner, and the existing V44 runtime bridge still owns stale-date fail-soft
behavior outside this page owner.

The repaired seam is V36's presentation wrapper. V36 may still temporarily own
kickoff text and matchup-hero presentation, but it must not retake the legacy day
strip after V41 has already installed its authoritative passthrough. This prevents
the obsolete Tomorrow+ strip from rendering, prevents a second date control, and
prevents a mid-render date rewrite from diverging from the pinned V42 snapshot.
"""
from __future__ import annotations

from threading import RLock
from typing import Any

import cfb_game_total_clean_page_v36 as v36
import cfb_game_total_clean_page_v43 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V45 • UNIFIED PAGE1 DAY OWNERSHIP REPAIR V1"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v43"
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE1 UNIFIED DAY OWNERSHIP REPAIR V1 ACTIVE"
UNIFIED_REPAIR_MARKER = "CFB_GAME_TOTAL_PAGE1_UNIFIED_REPAIR_V1_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PAGE2 = False
MAY_MODIFY_CARD_UI = False
NETWORK_CALLS_ADDED = 0
NEW_PROVIDER_PATHS_ADDED = 0
PHOENIX_DAY_OWNER = "cfb_game_total_clean_page_v41"
LEGACY_TOMORROW_STRIP_DISABLED = True
V44_RUNTIME_REPAIR_PRESERVED = True

_OWNER_LOCK = RLock()


def _render_v36_without_day_override(callback, *args: Any, **kwargs: Any):
    """Reuse V36 kickoff/hero presentation without touching V41's day seam."""
    with v36._LOCK:
        original_kickoff = v36.selector_owner._kickoff_text
        original_hero = v36.hero_owner._matchup_header_html_v25
        v36.selector_owner._kickoff_text = v36._kickoff_text_v36
        v36.hero_owner._matchup_header_html_v25 = v36._matchup_header_html_v36
        try:
            return callback(*args, **kwargs)
        finally:
            v36.selector_owner._kickoff_text = original_kickoff
            v36.hero_owner._matchup_header_html_v25 = original_hero


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Keep V41 as sole day owner while the frozen V43 product chain renders."""
    with _OWNER_LOCK:
        original_wrapper = v36._render_with_step3_presentation
        v36._render_with_step3_presentation = _render_v36_without_day_override
        try:
            return prior.render_game_total_hub(
                section_header,
                status_info,
                team_logo,
                h,
            )
        finally:
            v36._render_with_step3_presentation = original_wrapper


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V45 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "LEGACY_TOMORROW_STRIP_DISABLED",
    "MARKET",
    "MAY_MODIFY_CARD_UI",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "NEW_PROVIDER_PATHS_ADDED",
    "PHOENIX_DAY_OWNER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "UNIFIED_REPAIR_MARKER",
    "V44_RUNTIME_REPAIR_PRESERVED",
    "_render_v36_without_day_override",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
