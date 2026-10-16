"""CFB Game Total Page 2 — clean slate presentation V1.

The unselected CFB Game Total route is the game-selection slate (Page 2 of 2).
It reuses frozen V45 routing/data truth and removes the dense selected-game
analysis wall from this surface. Selecting a game still uses the existing exact
ESPN event handoff; model/projection/probability/provider behavior is untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import cfb_game_total_clean_page_v45 as prior

MODEL_VERSION = "CFB GAME TOTAL PAGE2 CLEAN SLATE V1"
MARKET = prior.MARKET
FROZEN_PRODUCT_OWNER = "cfb_game_total_clean_page_v45"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE2_CLEAN_SLATE_V1_ACTIVE"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
NEW_PROVIDER_PATHS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

PAGE2_SLATE_CSS = r"""
<style id="cfb-game-total-page2-clean-slate-v1">
/* Page 2 is for choosing a game, not duplicating Page 1's deep analysis. */
.gtvc2-tabs,
.gt159-total,
.gt227-section,
.gt159-section,
.gt159-final,
.gt159-top5{display:none!important}

.cfbgt-page2-heading{max-width:900px;margin:10px auto 12px;padding:14px 16px;
 border:1px solid rgba(75,197,255,.28);border-radius:16px;
 background:linear-gradient(145deg,#071a27,#07131f);box-sizing:border-box}
.cfbgt-page2-heading b{display:block;color:#f7fbff;font-size:18px;font-weight:1000}
.cfbgt-page2-heading span{display:block;margin-top:5px;color:#8ca8bc;font-size:10px;font-weight:800}
.cfbgt-page2-heading strong{color:#6edcff}

/* Restore readable native mobile behavior; do not squeeze two full team cards
   into a phone-width three-column grid. */
@media(max-width:560px){
 .cfbgt-page2-heading{margin-top:8px;padding:12px 13px;border-radius:14px}
 .cfbgt-page2-heading b{font-size:16px}
 .cfbgt-page2-heading span{font-size:9px}
}
</style>
"""


def render_step6_cert_surface() -> None:
    return prior.render_step6_cert_surface()


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> Any:
    st.markdown(PAGE2_SLATE_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="cfbgt-page2-heading" data-testid="cfbgt-page2-heading">'
        '<b>Choose a Game</b>'
        '<span>CFB Game Total Slate &nbsp;•&nbsp; <strong>Page 2 of 2</strong> &nbsp;•&nbsp; Tap a matchup to open Page 1</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    return prior.render_game_total_hub(section_header, status_info, team_logo, h)


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Clean Page 2 slate received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRODUCT_OWNER",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "NEW_PROVIDER_PATHS_ADDED",
    "PAGE2_SLATE_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
