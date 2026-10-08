"""CFB Game Total clean page V16 — Step 4 Matchup V2 activation.

Additive over frozen V164 Page V15. Only the Step 4 presentation owner advances.
Steps 1-3, selector identity, logos, model math, distribution math, qualification,
Top-5 behavior, APIs, and sportsbook projection influence remain frozen.
"""
from __future__ import annotations

from typing import Any, Mapping

import cfb_game_total_clean_page_v15 as prior_v164
import cfb_game_total_step4_matchup_v2 as step4_owner

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V16 • V165 STEP4 MATCHUP BOARD"
MARKET = prior_v164.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v15"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
ACTIVE_MARKER = "CFB GAME TOTAL • V165 STEP4 MATCHUP ACTIVE"
STEP4_PRESENTATION_MARKER = step4_owner.STEP4_PRESENTATION_MARKER
STEP4_DATA_MARKER = step4_owner.STEP4_DATA_MARKER
STEP4_DEPLOYMENT_MARKER = step4_owner.STEP4_DEPLOYMENT_MARKER
STEP4_VISUAL_MARKER = step4_owner.STEP4_VISUAL_MARKER
STEP4_GRADE_MARKER = step4_owner.STEP4_GRADE_MARKER
STEP4_SIDE_MARKET_IDENTITY_BRIDGE = "CFB_GAME_TOTAL_STEP4_CERTIFIED_EVENT_ID_BRIDGE_ACTIVE"
CERTIFIED_RUNTIME_IDENTITY_SOURCE = "Certified Runtime Snapshot V2 exact date + school identity"

# Re-export the V164 identity helpers for source-level certification and rollback.
_resolve_visuals_v164 = prior_v164._resolve_visuals_v164
_team_identity_v164 = prior_v164._team_identity_v164
_reconcile_display_bundle_v164 = prior_v164._reconcile_display_bundle_v164
_selector_payload_for_day = prior_v164._selector_payload_for_day
_selector_payload_for_game = prior_v164._selector_payload_for_game
_query_selected_day = prior_v164._query_selected_day
_FROZEN_RECOVER_RUNTIME_EVENT = prior_v164._recover_exact_runtime_event_v164


def _recover_exact_runtime_event_v165(
    game: Mapping[str, Any],
    selected_day: Any,
) -> dict[str, Any]:
    """Expose the certified ESPN event ID through the legacy generic ID alias."""
    enriched = dict(_FROZEN_RECOVER_RUNTIME_EVENT(game, selected_day) or {})
    espn_event_id = str(enriched.get("espn_event_id") or "").strip()
    generic_event_id = str(enriched.get("event_id") or "").strip()
    identity_source = str(enriched.get("logo_identity_source") or "").strip()
    if (
        espn_event_id.isdigit()
        and not generic_event_id
        and identity_source == CERTIFIED_RUNTIME_IDENTITY_SOURCE
    ):
        enriched["event_id"] = espn_event_id
        enriched["side_market_identity_bridge"] = STEP4_SIDE_MARKET_IDENTITY_BRIDGE
    return enriched


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    original_step4_owner = prior_v164.step4_owner
    original_step4_marker = prior_v164.STEP4_PRESENTATION_MARKER
    original_runtime_recover = prior_v164._recover_exact_runtime_event_v164
    prior_v164.step4_owner = step4_owner
    prior_v164.STEP4_PRESENTATION_MARKER = (
        f"{STEP4_PRESENTATION_MARKER} • {STEP4_DEPLOYMENT_MARKER} • {STEP4_VISUAL_MARKER} • {STEP4_GRADE_MARKER}"
    )
    prior_v164._recover_exact_runtime_event_v164 = _recover_exact_runtime_event_v165
    try:
        return prior_v164.render_game_total_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        prior_v164._recover_exact_runtime_event_v164 = original_runtime_recover
        prior_v164.step4_owner = original_step4_owner
        prior_v164.STEP4_PRESENTATION_MARKER = original_step4_marker


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V165 Game Total V16 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "CERTIFIED_RUNTIME_IDENTITY_SOURCE",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_DATA_MARKER",
    "STEP4_DEPLOYMENT_MARKER",
    "STEP4_GRADE_MARKER",
    "STEP4_PRESENTATION_MARKER",
    "STEP4_SIDE_MARKET_IDENTITY_BRIDGE",
    "STEP4_VISUAL_MARKER",
    "_query_selected_day",
    "_reconcile_display_bundle_v164",
    "_recover_exact_runtime_event_v165",
    "_resolve_visuals_v164",
    "_selector_payload_for_day",
    "_selector_payload_for_game",
    "_team_identity_v164",
    "render_cfb_hub",
    "render_game_total_hub",
]