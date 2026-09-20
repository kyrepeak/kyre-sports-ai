"""CFB Game Total clean page V25 — Step 6 runtime-fresh handoff.

No presentation or model-math changes. V25 injects fresh versioned helper
modules into the already-frozen V20/V24 hook points for one normal render.
"""
from __future__ import annotations

from threading import RLock

import streamlit as st

import cfb_game_total_clean_page_v20 as slate_hook_owner
import cfb_game_total_clean_page_v24 as prior
import cfb_game_total_game_evidence_v2 as game_evidence_v2
import cfb_game_total_slate_v3 as slate_v3

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V25 • STEP 6 RUNTIME FRESH HANDOFF"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v24"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • STEP 6 RUNTIME FRESH HANDOFF ACTIVE"
RUNTIME_FRESH_MARKER = "CFB_GAME_TOTAL_PAGE_CLEANUP_STEP6_RUNTIME_FRESH_ACTIVE"

_RUNTIME_LOCK = RLock()


def _render_with_runtime_fresh_helpers(callback, *args, **kwargs):
    with _RUNTIME_LOCK:
        original_slate = slate_hook_owner.slate_v2
        original_game_evidence = prior.game_evidence
        slate_hook_owner.slate_v2 = slate_v3
        prior.game_evidence = game_evidence_v2
        try:
            return callback(*args, **kwargs)
        finally:
            prior.game_evidence = original_game_evidence
            slate_hook_owner.slate_v2 = original_slate


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(
        f'<div data-testid="gt-cleanup-v25-runtime-fresh" '
        f'style="display:none!important">{RUNTIME_FRESH_MARKER}</div>',
        unsafe_allow_html=True,
    )
    return _render_with_runtime_fresh_helpers(
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
        raise ValueError(f"Page V25 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "RUNTIME_FRESH_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_render_with_runtime_fresh_helpers",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
