"""CFB Game Total clean page V24 — page cleanup Step 5 Game Evidence data.

Data-only successor to V23. Steps 1-4 remain frozen. V24 enriches only the
display game environment fields using the certified exact-event environment
engine when the existing display evidence is incomplete.
"""
from __future__ import annotations

from threading import RLock
from typing import Any, Mapping

import cfb_game_total_clean_page_v22 as handoff_owner
import cfb_game_total_clean_page_v23 as prior
import cfb_game_total_game_evidence_v1 as game_evidence

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V24 • PAGE CLEANUP STEP 5 GAME EVIDENCE DATA"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v23"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE CLEANUP STEP 5 GAME EVIDENCE DATA ACTIVE"
STEP5_GAME_EVIDENCE_DATA_MARKER = "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP5_GAME_EVIDENCE_DATA_ACTIVE"

_HANDOFF_LOCK = RLock()
_FROZEN_V22_RECONCILE = handoff_owner._reconcile_display_bundle_v22


def _reconcile_display_bundle_v24(
    game: Mapping[str, Any],
    selected_day: Any,
    step1_away: Mapping[str, Any],
    step1_home: Mapping[str, Any],
):
    display_game, away, home, diag = _FROZEN_V22_RECONCILE(
        game,
        selected_day,
        step1_away,
        step1_home,
    )
    enriched_game, evidence_diag = game_evidence.enrich_game_evidence(
        display_game,
        game,
    )
    out_diag = dict(diag or {})
    out_diag["step5_game_evidence"] = evidence_diag
    out_diag["step5_game_evidence_data_green"] = bool(
        evidence_diag.get("data_green")
    )
    return enriched_game, away, home, out_diag


def _render_with_step5_game_evidence_data(callback, *args, **kwargs):
    with _HANDOFF_LOCK:
        original = handoff_owner._reconcile_display_bundle_v22
        handoff_owner._reconcile_display_bundle_v22 = _reconcile_display_bundle_v24
        try:
            return callback(*args, **kwargs)
        finally:
            handoff_owner._reconcile_display_bundle_v22 = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _render_with_step5_game_evidence_data(
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
        raise ValueError(f"Page V24 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP5_GAME_EVIDENCE_DATA_MARKER",
    "_reconcile_display_bundle_v24",
    "_render_with_step5_game_evidence_data",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
