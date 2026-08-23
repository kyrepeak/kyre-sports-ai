"""MLB Pitcher Strikeouts O/U V1.0.16 — final renderer-order repair.

Presentation-only repair on top of V1.0.15/V1.0.14.

Root cause fixed here: V1.0.15 installed its Supports/Concerns card renderer, but
V1.0.14 delegates through V1.0.13, whose render function re-installed the older
V1.0.13 card renderer immediately before the Top-5 cards were drawn. That import/
render-order overwrite made Supports/Concerns disappear even though the rest of
the V1.0.11 evidence block rendered correctly.

V1.0.16 temporarily replaces that exact V1.0.13 installer during rendering so the
final card symbol always points to V1.0.15's fail-safe card renderer at draw time.
Sportsbook transport remains V1.0.14 (SportsGameOdds primary, Odds-API.io fallback
and same-slate real-line cache). Projection math, Monte Carlo, evidence score,
market grading, candidate pool and Top-5 ordering are unchanged.
"""
from __future__ import annotations

import streamlit as st

import mlb_pitcher_k_hub_v1015 as v1015
import mlb_pitcher_k_hub_v1014 as v1014
import mlb_pitcher_k_hub_v1013 as v1013
import mlb_pitcher_k_hub_v101 as v101

engine = v1015.engine
MODEL_VERSION = "Pitcher K V1.0.16"


def _install_final_renderer():
    """Install the two owners that must be live at draw time."""
    engine._fetch_market_lines = v1014._fetch_market_lines_multi
    v101._card = v1015._card


_install_final_renderer()


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    # Preserve the V1.0.15 reason styling.
    st.markdown(v1015._REASON_CSS, unsafe_allow_html=True)

    # V1.0.13 calls this installer immediately before delegating to the original
    # Top-5 renderer. Override that exact seam for this render so it cannot replace
    # V1.0.15's final card renderer with the older V1.0.13 renderer.
    original_v1013_installer = v1013._install_card_renderer

    def _v1016_installer():
        _install_final_renderer()

    v1013._install_card_renderer = _v1016_installer
    _install_final_renderer()

    original_markdown = st.markdown

    def _version_markdown(body, *args, **kwargs):
        if isinstance(body, str):
            for old in (
                "V1.0.15", "V1.0.14", "V1.0.13", "V1.0.12",
                "V1.0.11", "V1.0.10", "V1.0.9", "V1.0.8", "V1.0.7",
                "V1.0.6", "V1.0.5", "V1.0.4", "V1.0.3", "V1.0.2",
                "V1.0.1", "V1.0",
            ):
                body = body.replace(
                    f"Pitcher Strikeouts O/U — {old}",
                    "Pitcher Strikeouts O/U — V1.0.16",
                )
        return original_markdown(body, *args, **kwargs)

    st.markdown = _version_markdown
    try:
        # Use V1.0.14 as the transport owner. Its call into V1.0.13 now reaches
        # the patched installer above, so V1.0.15's Supports/Concerns renderer is
        # guaranteed to be the final renderer used for the ranked Top-5 cards.
        return v1014.render_pitcher_k_hub(
            games_df, section_header, status_info, team_logo, h
        )
    finally:
        st.markdown = original_markdown
        v1013._install_card_renderer = original_v1013_installer
        # Leave the active card/transport symbols in the desired state for any
        # immediate Streamlit rerun within the same interpreter.
        _install_final_renderer()
