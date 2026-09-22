"""CFB Game Total clean page V34 — universal black + glacier-blue wrapper.

Presentation-only successor to frozen V33. V33/V28 and their ancestors retain
ownership of navigation, data, model, market, Steps 1-12, and interaction logic.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v33 as prior
from kyre_game_total_theme_v1 import build_game_total_theme_css

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V34 • UNIVERSAL BLACK + GLACIER BLUE"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v33"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True
ACTIVE_MARKER = "CFB GAME TOTAL • UNIVERSAL BLACK + GLACIER BLUE ACTIVE"

def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()

def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    css = build_game_total_theme_css()
    st.markdown(css, unsafe_allow_html=True)
    result = prior.render_game_total_hub(section_header, status_info, team_logo, h)
    # Re-emit after frozen page CSS so the universal skin stays the final visual owner.
    st.markdown(css, unsafe_allow_html=True)
    return result

def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Page V34 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)

__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
