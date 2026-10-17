"""MONSTER CFB Game Total Page 2 — purge-safe visual cleanup R4.

R4 replaces the fragile R2/R3 monkey-patch chain with a self-contained page
owner that survives the shared-shell CFB module purge. It preserves the frozen
R1 selected-event, multi-source, model, probability, market, Line Lab, Best Bet,
and recommendation logic while rendering Stage 6/7 directly.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
import re
from typing import Any

import streamlit as st

import cfb_game_total_clean_page_v23 as team_evidence_ui
import cfb_game_total_page2_complete_repair_r1 as base
import cfb_game_total_page2_visual_cleanup_r2 as r2
import streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as cfb_router

MODEL_VERSION = "MONSTER CFB GAME TOTAL PAGE2 VISUAL CLEANUP R4"
ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_VISUAL_CLEANUP_R4_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_VISUAL_CLEANUP_R4_FROZEN"
SAME_PAGE_ROUTE = "cfb_game_total_page2_visual_cleanup_r4"
MARKET = base.MARKET
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


def build_stage7_clean_html(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> str:
    """Build compact Stage 7 without monkey-patching any predecessor module."""
    cleaned = r2.build_stage7_clean_html(identity, away, home)
    cleaned = _LEGACY_SECTION_HEAD_RE.sub("\n", cleaned, count=1)
    cleaned = cleaned.replace(
        'data-testid="gtp2r2-team-evidence"',
        'data-testid="gtp2r4-team-evidence"',
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


def _render_matchup_and_team_evidence(payload: Mapping[str, Any]) -> None:
    identity, away, home, display_game, _, _, _, _ = base._profile_values(payload)
    matchup = base.page2._matchup_contract(identity, away, home, display_game)
    st.markdown(team_evidence_ui.STEP4_TEAM_EVIDENCE_CSS + r2.CLEANUP_CSS, unsafe_allow_html=True)
    st.markdown(r2.build_stage6_clean_html(matchup), unsafe_allow_html=True)
    st.markdown(build_stage7_clean_html(identity, away, home), unsafe_allow_html=True)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Render the frozen R1 analysis flow with purge-safe R4 Stage 6/7 ownership."""
    selected = base._selected_identity()
    if selected is None:
        st.error("Selected-game identity is incomplete. Return to CFB Game Totals and tap a game again.")
        st.markdown('<a href="?sport=cfb&market=game-total" target="_self">← Back to CFB Game Totals</a>', unsafe_allow_html=True)
        return None

    day, event_id = selected
    game, diagnostics = base._selected_game(day, event_id)
    if game is None:
        st.error("That exact selected game is not present in the verified slate. Page 2 will not substitute another matchup.")
        st.markdown(
            f'<a href="?sport=cfb&market=game-total&date={escape(day, quote=True)}" target="_self">← Back to CFB Game Totals</a>',
            unsafe_allow_html=True,
        )
        return None

    payload = base._build_payload(game, day)
    if base._event_id(base._mapping(payload.get("display_game"))) != event_id:
        st.error("Selected-event identity verification failed. No alternate game was rendered.")
        return None

    st.markdown(base._header_html(payload, day), unsafe_allow_html=True)
    base._render_source_strip(base._mapping(payload.get("display_game")))
    base._render_outlook_snapshot_trends(payload, day)
    base._render_line_lab(payload, event_id)
    base._render_best_bet(payload)
    _render_matchup_and_team_evidence(payload)
    st.markdown(
        '<div class="gtp2r1-cert" data-testid="gtp2r1-cert" data-event-id="'
        + escape(event_id, quote=True)
        + '">EXACT SELECTED GAME • MULTI-SOURCE VERIFIED DISPLAY • FROZEN MODEL • SPORTSBOOK PROJECTION INFLUENCE 0.0%</div>',
        unsafe_allow_html=True,
    )
    return {"event_id": event_id, "date": day, "diagnostics": diagnostics}


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None):
    if market != MARKET:
        raise ValueError(f"Page 2 Visual Cleanup R4 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


def render_selected_in_shared_shell():
    """Make the post-purge page owner R4 itself, then restore the prior route."""
    with cfb_router._ROUTE_POINTER_LOCK:
        original_page1 = cfb_router.PAGE1_NATIVE_ROUTE
        cfb_router.PAGE1_NATIVE_ROUTE = SAME_PAGE_ROUTE
        try:
            return cfb_router._render_page1_in_shared_shell()
        finally:
            cfb_router.PAGE1_NATIVE_ROUTE = original_page1


__all__ = [
    "ACTIVE_MARKER",
    "FREEZE_TOKEN",
    "MARKET",
    "MODEL_VERSION",
    "MULTI_SOURCE_REQUIRED",
    "SAME_PAGE_ROUTE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_stage7_clean_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_selected_in_shared_shell",
]
