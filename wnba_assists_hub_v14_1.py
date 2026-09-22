"""WNBA Assists V14.1 — dependency correction before Step 15.

This is a presentation/routing correction only. It preserves the complete V14
runtime and changes one dependency in the visible build graph:

MODEL BRANCH:  Steps 1–12 -> Step 15 -> Step 16 -> Step 17
MARKET BRANCH: Steps 13–14 ---------------------> Step 18/19

Therefore Step 15 never depends on SportsGameOdds availability or no-vig rows.
No projection math is implemented here and no existing Step 1–14 calculation is
changed.
"""
from __future__ import annotations

import streamlit as st

import wnba_assists_hub_v14 as v14

MODEL_VERSION = "WNBA ASSISTS V14.1 • INDEPENDENT MODEL/MARKET BRANCH CORRECTION"


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Render V14 unchanged except for the corrected Step-15 dependency display."""
    original_card = v14.step3._layer_card
    original_info = st.info
    original_warning = st.warning
    state = {"step12_live": False}

    def _corrected_card(step, label, card_state, note=""):
        # Build cards are emitted in numeric order. Capture the actual Step-12
        # runtime result, then use it as the ONLY unlock prerequisite for Step 15.
        if int(step) == 12:
            state["step12_live"] = "LIVE" in str(card_state).upper()
        if int(step) == 15 and state["step12_live"]:
            card_state = "➡️ NEXT"
            note = "Independent model branch • verified Steps 1–12 only"
        return original_card(step, label, card_state, note)

    def _corrected_info(body, *args, **kwargs):
        text = str(body)
        text = text.replace(
            "The layer is armed and Step 15 remains locked until a real same-day market exists.",
            "The market branch is armed. Step 15 is independent and may proceed from verified Steps 1–12 even when no pregame sportsbook market exists.",
        )
        return original_info(text, *args, **kwargs)

    def _corrected_warning(body, *args, **kwargs):
        text = str(body)
        text = text.replace(
            "Step 15 remains locked.",
            "This does not lock Step 15; the projection branch depends on verified Steps 1–12, not sportsbook availability.",
        )
        return original_warning(text, *args, **kwargs)

    v14.step3._layer_card = _corrected_card
    st.info = _corrected_info
    st.warning = _corrected_warning
    try:
        v14.render_wnba_assists_hub(section_header, status_info, team_logo, h)
    finally:
        v14.step3._layer_card = original_card
        st.info = original_info
        st.warning = original_warning

    if state["step12_live"]:
        st.success(
            "✅ DEPENDENCY CORRECTED • Step 15 is now unlocked by the independent model branch (Steps 1–12). Steps 13–14 remain a separate sportsbook/no-vig branch and will rejoin only when line-specific probabilities and market grading are needed later."
        )
    else:
        st.warning(
            "⚠️ MODEL BRANCH LOCKED • Step 15 still requires Step 12 to pass. Sportsbook/no-vig availability is not part of that requirement."
        )

    st.caption(
        "🧭 Assists architecture V14.1 • model: Steps 1–12 → 15 → 16 → 17 • market: Steps 13–14 → join at 18/19 • zero new projection math • zero new simulations"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
