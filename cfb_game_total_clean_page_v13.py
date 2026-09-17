"""CFB Game Total Clean Page V13 — V162 fresh presentation boundary.

Additive successor to frozen V161/V12. V13 intentionally introduces a fresh
module name so the production router can evict stale Game Total page modules
and reload the certified V161 presentation chain from disk. No projection,
distribution, qualification, ranking, API/model, or sportsbook-influence
behavior is changed.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v12 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V13 • V162 FRESH PRESENTATION BOUNDARY"
MARKET = prior.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v12"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V162 ACTIVE"


def _render_v162_identity() -> None:
    st.markdown(
        '<div data-testid="cfb-game-total-v162-active" '
        'style="position:absolute;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none">'
        f'{ACTIVE_MARKER} • V161 presentation reloaded fresh • sportsbook 0.0%</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    _render_v162_identity()
    return prior.render_game_total_hub(section_header, status_info, team_logo, h)


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V162 Game Total V13 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_hub",
]
