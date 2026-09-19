"""CFB Game Total clean page V19 — V185 Step 6 visual parity.

Additive presentation-only successor to permanently frozen V184 Page V18.
The V184 Step 6 normalized data contract, snapshot routing, source behavior,
model math, projection math, probabilities, APIs, and sportsbook influence
remain unchanged. Only the Step 6 HTML renderer is temporarily substituted
with the V185 visual-parity owner during render.
"""
from __future__ import annotations

import cfb_game_total_clean_page_v18 as prior_v184
import cfb_game_total_step6_visual_v2 as step6_visual

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V19 • V185 STEP6 VISUAL PARITY"
MARKET = prior_v184.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v18"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • V185 STEP6 VISUAL PARITY ACTIVE"

STEP5_PRESENTATION_MARKER = prior_v184.STEP5_PRESENTATION_MARKER
STEP5_DATA_MARKER = prior_v184.STEP5_DATA_MARKER
STEP5_VISUAL_MARKER = prior_v184.STEP5_VISUAL_MARKER

STEP6_PRESENTATION_MARKER = step6_visual.STEP6_PRESENTATION_MARKER
STEP6_DATA_MARKER = step6_visual.STEP6_DATA_MARKER
STEP6_VISUAL_MARKER = step6_visual.STEP6_VISUAL_MARKER
STEP6_DEPLOYMENT_MARKER = step6_visual.STEP6_DEPLOYMENT_MARKER
STEP6_VISUAL_PARITY_MARKER = step6_visual.STEP6_VISUAL_PARITY_MARKER
STEP6_CERT_SURFACE_MARKER = prior_v184.STEP6_CERT_SURFACE_MARKER

_step6_snapshot_row = prior_v184._step6_snapshot_row
_step6_snapshot_bundle = prior_v184._step6_snapshot_bundle


def _render_with_v185_visual(callback, *args, **kwargs):
    original = prior_v184.step6_owner.render_step6_html
    prior_v184.step6_owner.render_step6_html = step6_visual.render_step6_html
    try:
        return callback(*args, **kwargs)
    finally:
        prior_v184.step6_owner.render_step6_html = original


def render_step6_cert_surface() -> None:
    return _render_with_v185_visual(prior_v184.render_step6_cert_surface)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _render_with_v185_visual(
        prior_v184.render_game_total_hub,
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
            f"V185 Game Total V19 page received unsupported market: {market}"
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
