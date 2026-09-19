"""CFB Game Total clean page V16 — Step 4 Matchup V2 activation.

Additive over frozen V164 Page V15. Only the Step 4 presentation owner advances.
Steps 1-3, selector identity, logos, model math, distribution math, qualification,
Top-5 behavior, APIs, and sportsbook projection influence remain frozen.
"""
from __future__ import annotations

import cfb_game_total_clean_page_v15 as prior_v164
import cfb_game_total_step4_matchup_v2 as step4_owner

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V16 • V165 STEP4 MATCHUP BOARD"
MARKET = prior_v164.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v15"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • V165 STEP4 MATCHUP ACTIVE"
STEP4_PRESENTATION_MARKER = step4_owner.STEP4_PRESENTATION_MARKER
STEP4_DATA_MARKER = step4_owner.STEP4_DATA_MARKER
STEP4_DEPLOYMENT_MARKER = step4_owner.STEP4_DEPLOYMENT_MARKER

# Re-export the V164 identity helpers for source-level certification and rollback.
_resolve_visuals_v164 = prior_v164._resolve_visuals_v164
_team_identity_v164 = prior_v164._team_identity_v164
_reconcile_display_bundle_v164 = prior_v164._reconcile_display_bundle_v164
_selector_payload_for_day = prior_v164._selector_payload_for_day
_selector_payload_for_game = prior_v164._selector_payload_for_game
_query_selected_day = prior_v164._query_selected_day


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    original_step4_owner = prior_v164.step4_owner
    original_step4_marker = prior_v164.STEP4_PRESENTATION_MARKER
    prior_v164.step4_owner = step4_owner
    prior_v164.STEP4_PRESENTATION_MARKER = (
        f"{STEP4_PRESENTATION_MARKER} • {STEP4_DEPLOYMENT_MARKER}"
    )
    try:
        return prior_v164.render_game_total_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        prior_v164.step4_owner = original_step4_owner
        prior_v164.STEP4_PRESENTATION_MARKER = original_step4_marker


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V165 Game Total V16 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_DATA_MARKER",
    "STEP4_DEPLOYMENT_MARKER",
    "STEP4_PRESENTATION_MARKER",
    "_query_selected_day",
    "_reconcile_display_bundle_v164",
    "_resolve_visuals_v164",
    "_selector_payload_for_day",
    "_selector_payload_for_game",
    "_team_identity_v164",
    "render_cfb_hub",
    "render_game_total_hub",
]
