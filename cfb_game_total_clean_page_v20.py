"""CFB Game Total clean page V20 — page cleanup Step 1 data contract.

Additive successor to V19. V20 changes only the selected Game Total slate data
owner so the page can use the normalized field-level fallback in Slate V2.
V19 Step 6 visuals/data and all frozen Step-11/Step-12 math remain unchanged.
"""
from __future__ import annotations

from threading import RLock

import cfb_game_total_clean_page_v9 as compact_owner
import cfb_game_total_clean_page_v19 as prior
import cfb_game_total_slate_v2 as slate_v2

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V20 • PAGE CLEANUP STEP 1 DATA"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v19"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE CLEANUP STEP 1 DATA ACTIVE"

STEP5_PRESENTATION_MARKER = prior.STEP5_PRESENTATION_MARKER
STEP5_DATA_MARKER = prior.STEP5_DATA_MARKER
STEP5_VISUAL_MARKER = prior.STEP5_VISUAL_MARKER
STEP6_PRESENTATION_MARKER = prior.STEP6_PRESENTATION_MARKER
STEP6_DATA_MARKER = prior.STEP6_DATA_MARKER
STEP6_VISUAL_MARKER = prior.STEP6_VISUAL_MARKER
STEP6_DEPLOYMENT_MARKER = prior.STEP6_DEPLOYMENT_MARKER
STEP6_VISUAL_PARITY_MARKER = prior.STEP6_VISUAL_PARITY_MARKER
STEP6_CERT_SURFACE_MARKER = prior.STEP6_CERT_SURFACE_MARKER

_step6_snapshot_row = prior._step6_snapshot_row
_step6_snapshot_bundle = prior._step6_snapshot_bundle

_DATA_OWNER_LOCK = RLock()


def _render_with_v20_slate(callback, *args, **kwargs):
    """Temporarily route only the compact page's slate owner to additive V2."""
    with _DATA_OWNER_LOCK:
        original_slate = compact_owner.frozen_page.slate
        compact_owner.frozen_page.slate = slate_v2
        try:
            return callback(*args, **kwargs)
        finally:
            compact_owner.frozen_page.slate = original_slate


def render_step6_cert_surface() -> None:
    # Step 6 certification is already frozen/green and does not need Slate V2.
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _render_with_v20_slate(
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
        raise ValueError(
            f"Page V20 received unsupported market: {market}"
        )
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP5_DATA_MARKER",
    "STEP5_PRESENTATION_MARKER",
    "STEP5_VISUAL_MARKER",
    "STEP6_CERT_SURFACE_MARKER",
    "STEP6_DATA_MARKER",
    "STEP6_DEPLOYMENT_MARKER",
    "STEP6_PRESENTATION_MARKER",
    "STEP6_VISUAL_MARKER",
    "STEP6_VISUAL_PARITY_MARKER",
    "_step6_snapshot_bundle",
    "_step6_snapshot_row",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
