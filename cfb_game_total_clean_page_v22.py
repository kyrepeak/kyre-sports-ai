"""CFB Game Total clean page V22 — page cleanup Step 3 Team Evidence data.

Additive data-handoff successor to V21. V22 does not redesign Team Evidence.
It preserves the verified Step-1 completed-game sample when V164's display
reconciliation returns a non-empty but scoring-incomplete profile.
"""
from __future__ import annotations

from threading import RLock
from typing import Any, Mapping

import cfb_game_total_clean_page_v15 as handoff_owner
import cfb_game_total_clean_page_v21 as prior
import cfb_game_total_team_evidence_data_v1 as team_evidence_data

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V22 • PAGE CLEANUP STEP 3 TEAM EVIDENCE DATA"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v21"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • PAGE CLEANUP STEP 3 TEAM EVIDENCE DATA ACTIVE"
STEP3_TEAM_EVIDENCE_DATA_MARKER = "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP3_TEAM_EVIDENCE_DATA_ACTIVE"

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

_HANDOFF_LOCK = RLock()
_FROZEN_V164_RECONCILE = handoff_owner._reconcile_display_bundle_v164


def _reconcile_display_bundle_v22(
    game: Mapping[str, Any],
    selected_day: Any,
    step1_away: Mapping[str, Any],
    step1_home: Mapping[str, Any],
):
    display_game, display_away, display_home, diag = _FROZEN_V164_RECONCILE(
        game,
        selected_day,
        step1_away,
        step1_home,
    )
    repaired_away, repaired_home, repair_diag = (
        team_evidence_data.repair_team_evidence_bundle(
            display_away,
            display_home,
            step1_away,
            step1_home,
        )
    )
    out_diag = dict(diag or {})
    out_diag["step3_team_evidence"] = repair_diag
    out_diag["step3_team_evidence_data_green"] = bool(
        repair_diag.get("data_green")
    )
    return display_game, repaired_away, repaired_home, out_diag


def _render_with_step3_team_evidence_data(callback, *args, **kwargs):
    """Patch only V164's display handoff while the normal page renders."""
    with _HANDOFF_LOCK:
        original = handoff_owner._reconcile_display_bundle_v164
        handoff_owner._reconcile_display_bundle_v164 = _reconcile_display_bundle_v22
        try:
            return callback(*args, **kwargs)
        finally:
            handoff_owner._reconcile_display_bundle_v164 = original


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return _render_with_step3_team_evidence_data(
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
        raise ValueError(f"Page V22 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_TEAM_EVIDENCE_DATA_MARKER",
    "_reconcile_display_bundle_v22",
    "_render_with_step3_team_evidence_data",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
