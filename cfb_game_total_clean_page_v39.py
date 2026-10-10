"""CFB Game Total clean page V39 — native website routing Step 1.

Additive successor to the current V38 Page-1 presentation. The exact
CFB -> Game Total Page-1 route keeps the full V38/V36/V35 chain and frozen
analytics while bypassing only V33's legacy in-page "Jump to a Sport Page"
navigator. Site-level navigation remains owned by the existing KYRE SPORTS AI
shell.

No model, projection, probability, market-ownership, sportsbook-influence,
network-provider, event-identity, schedule, or Page-2 behavior is changed.
"""
from __future__ import annotations

from threading import RLock
from typing import Any

import cfb_game_total_clean_page_v28 as frozen_content
import cfb_game_total_clean_page_v33 as legacy_nav
import cfb_game_total_clean_page_v38 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V39 • NATIVE WEBSITE ROUTING STEP 1"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v38"
ACTIVE_MARKER = "CFB GAME TOTAL • NATIVE WEBSITE ROUTING STEP 1 ACTIVE"
NATIVE_ROUTE_MARKER = "CFB_GAME_TOTAL_NATIVE_WEBSITE_ROUTING_STEP1_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PAGE2 = False
NETWORK_CALLS_ADDED = 0

_NATIVE_ROUTE_LOCK = RLock()


def _native_content_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Render the frozen Game Total body without V33's in-page sport jump."""
    return frozen_content.render_game_total_hub(
        section_header,
        status_info,
        team_logo,
        h,
    )


def _render_without_legacy_sport_jump(callback, *args: Any, **kwargs: Any):
    """Bypass only the legacy navigator for one render, then restore it exactly."""
    with _NATIVE_ROUTE_LOCK:
        original = legacy_nav.render_game_total_hub
        legacy_nav.render_game_total_hub = _native_content_hub
        try:
            return callback(*args, **kwargs)
        finally:
            legacy_nav.render_game_total_hub = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _render_without_legacy_sport_jump(
        prior.render_game_total_hub,
        section_header,
        status_info,
        team_logo,
        h,
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V39 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NATIVE_ROUTE_MARKER",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_native_content_hub",
    "_render_without_legacy_sport_jump",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
