"""MLB Matchup Explorer V5.2 — cleanup Step 7 final visual polish.

Presentation-only wrapper over certified Cleanup Step 6 and Matchup Intelligence
V2. Removes duplicated legacy summary cards, shortens helper/status copy and
strengthens the selected-player result hierarchy while leaving all projection,
probability, calibration and ranking math untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v45 as step4
import mlb_matchup_hub_v46 as step5
import mlb_matchup_hub_v47 as step6
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.2 • Cleanup Step 7"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP1_PRESENTATION = "mlb_matchup_hub_v42"
FROZEN_STEP4_PRESENTATION = "mlb_matchup_hub_v45"
FROZEN_STEP5_PRESENTATION = "mlb_matchup_hub_v46"
FROZEN_STEP6_PRESENTATION = "mlb_matchup_hub_v47"

_STEP7_CSS = r"""
<style>
/* Step 7 is presentation-only: retire duplicated legacy shell cards that are
   already replaced by the compact selection summary + selected-player hero. */
.mh-hero,.mh-game,.mh-player{display:none!important}
.mx46-note,.mx47-helper,.mx45-note{display:none!important}

.mx48-title{margin:2px 0 6px}
.mx48-title h2{font-size:1.12rem;line-height:1.15;margin:0;color:#f7fbff;font-weight:950;letter-spacing:-.015em}
.mx48-title p{font-size:.58rem;line-height:1.35;margin:3px 0 0;color:#718da5}

.mx47-summary{margin:5px 0 7px!important;padding:8px 10px!important;border-radius:13px!important;box-shadow:none!important}
.mx47-kicker{display:none!important}
.mx47-game{font-size:.76rem!important;letter-spacing:-.01em}.mx47-player{font-size:.57rem!important;margin-top:1px!important}

.mx45-hero{margin:7px 0 11px!important;padding:14px 15px!important;border-radius:18px!important;box-shadow:0 8px 24px rgba(0,0,0,.13)!important}
.mx45-kicker{display:none!important}
.mx45-name{font-size:1.58rem!important;letter-spacing:-.025em!important;margin-bottom:5px!important}
.mx45-line{font-size:.70rem!important;line-height:1.42!important}.mx45-status{margin-top:7px!important;padding:4px 8px!important;font-size:.53rem!important}
.mx45-final{gap:7px!important;margin-top:11px!important}.mx45-final-cell{padding:9px 10px!important;border-radius:12px!important}
.mx45-final-cell span{font-size:.47rem!important}.mx45-final-cell b{font-size:1.02rem!important}
.mx45-final-cell.mx45-prob b{font-size:1.38rem!important}
.mx45-season{gap:6px!important;margin-top:7px!important}.mx45-season-cell{padding:7px!important;border-radius:11px!important}
.mx45-season-cell span{font-size:.45rem!important}.mx45-season-cell b{font-size:.84rem!important}

/* Keep optional detail surfaces readable without making them dominate the page. */
div[data-testid="stExpander"]{margin-top:.2rem}

@media(max-width:640px){
  .mx48-title{margin:0 0 4px}.mx48-title h2{font-size:1rem}.mx48-title p{display:none}
  .mx47-summary{padding:7px 8px!important;margin:3px 0 5px!important}.mx47-game{font-size:.70rem!important}.mx47-player{font-size:.53rem!important}
  .mx45-hero{padding:10px!important;margin:5px 0 8px!important;border-radius:15px!important}
  .mx45-main{grid-template-columns:80px 1fr!important;gap:9px!important}.mx45-photo-wrap{width:80px!important;height:80px!important;border-radius:13px!important}
  .mx45-name{font-size:1.12rem!important}.mx45-line{font-size:.59rem!important}.mx45-status{font-size:.49rem!important;padding:3px 7px!important;margin-top:5px!important}
  .mx45-final{gap:5px!important;margin-top:9px!important}.mx45-final-cell{padding:7px!important}.mx45-final-cell span{font-size:.42rem!important}
  .mx45-final-cell b{font-size:.84rem!important}.mx45-final-cell.mx45-prob b{font-size:1.02rem!important}
  .mx45-season{gap:4px!important}.mx45-season-cell{padding:6px 4px!important}.mx45-season-cell span{font-size:.40rem!important}.mx45-season-cell b{font-size:.72rem!important}
}
</style>
"""

_TITLE_HTML = (
    '<div class="mx48-title"><h2>⚾ Matchup Explorer</h2>'
    '<p>Pick a matchup and hitter when needed; the final player result stays front and center.</p></div>'
)


def _polished_hero_html(context: dict[str, Any], final: dict[str, Any] | None = None) -> str:
    """Reuse the certified Step 4 hero data and only shorten visible labels."""
    source = step4._hero_html(context, final)
    replacements = {
        "Selected player • matchup summary": "Player matchup",
        "Final 1+ hit probability": "1+ hit",
        "Expected hits": "Exp. hits",
        "Season AVG": "AVG",
        "Season OPS": "OPS",
        "Season hits": "Hits",
        "Season HR": "HR",
        "Final V2:": "Model:",
    }
    for old, new in replacements.items():
        source = source.replace(old, new)
    if final is None:
        source = source.replace("Model: WAITING", "Model: calculating…")
    return source


def _render_polished_hero(slot, context: dict[str, Any] | None, final: dict[str, Any] | None = None) -> None:
    if not context:
        slot.info("Player result is waiting for a verified selection.")
        return
    slot.markdown(_polished_hero_html(context, final), unsafe_allow_html=True)


def _step12_profile_with_polished_hero(original, slot, context):
    def wrapped(profile: dict[str, Any] | None) -> None:
        _render_polished_hero(slot, context, profile)
        return original(profile)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    st.markdown(_STEP7_CSS + _TITLE_HTML, unsafe_allow_html=True)
    step6._render_compact_controls(games_df)

    context = step4._selected_context(games_df)
    hero_slot = st.empty()
    _render_polished_hero(hero_slot, context, None)

    original_selectbox = st.selectbox
    original_expander = st.expander
    original_step12_profile = final_layer._render_step12_profile

    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    st.expander = step5._collapsed_expander(original_expander)
    final_layer._render_step12_profile = _step12_profile_with_polished_hero(
        original_step12_profile,
        hero_slot,
        context,
    )
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        final_layer._render_step12_profile = original_step12_profile
        st.expander = original_expander
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP1_PRESENTATION",
    "FROZEN_STEP4_PRESENTATION",
    "FROZEN_STEP5_PRESENTATION",
    "FROZEN_STEP6_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_polished_hero_html",
    "_render_polished_hero",
    "render_matchup_hub",
]
