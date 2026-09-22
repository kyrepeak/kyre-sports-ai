"""MLB Matchup Explorer V5.4 — cleanup Step 10 mobile layout cleanup.

Presentation-only wrapper over certified Cleanup Step 9. Tightens the real
Streamlit mobile layout, keeps roster search with player controls, removes blank
legacy shell spacing, and improves the V2 calculating state. Model math remains
fully delegated to the frozen/current intelligence chain.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v44 as step3
import mlb_matchup_hub_v45 as step4
import mlb_matchup_hub_v46 as step5
import mlb_matchup_hub_v47 as step6
import mlb_matchup_hub_v49 as step9
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.4 • Cleanup Step 10"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP9_PRESENTATION = "mlb_matchup_hub_v49"

_STEP10_CSS = r"""
<style>
/* Remove outer Streamlit containers whose contents earlier cleanup steps hid.
   This gets rid of the large blank mobile gaps those empty containers left. */
div[data-testid="stElementContainer"]:has(.mx47-helper),
div[data-testid="stElementContainer"]:has(.mx44-selected),
div[data-testid="stElementContainer"]:has(.mh-hero),
div[data-testid="stElementContainer"]:has(.mh-game),
div[data-testid="stElementContainer"]:has(.mh-player),
div[data-testid="stElementContainer"]:has(.mx45-hero){display:none!important}

/* Player-button metadata is folded into the button label for a cleaner roster. */
.mx44-meta{display:none!important}
.mx44-group{margin:7px 0 4px!important}
.mx44-team{margin:1px 0 3px!important}
.mx44-counts{margin:2px 0 4px!important}

/* Pull the selected-player card closer to the controls and research accordion. */
.mx49-section{margin:2px 0 5px!important}
.mx49-card{margin-bottom:5px!important}
div[data-testid="stExpander"]{margin-top:.1rem!important;margin-bottom:.15rem!important}

/* Cleaner loading state than three loose bullet glyphs. */
.mx50-load{display:flex!important;align-items:center;gap:4px;min-height:1.35rem}
.mx50-load span{width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.35;animation:mx50pulse 1.05s ease-in-out infinite}
.mx50-load span:nth-child(2){animation-delay:.15s}.mx50-load span:nth-child(3){animation-delay:.30s}
@keyframes mx50pulse{0%,70%,100%{opacity:.28;transform:translateY(0)}35%{opacity:1;transform:translateY(-2px)}}

@media(max-width:640px){
  .mx49-section{margin:0 0 4px!important}
  .mx49-card{margin-bottom:4px!important;padding:11px!important}
  .mx44-group{margin-top:5px!important}
  div[data-testid="stExpander"]{margin-top:0!important;margin-bottom:.1rem!important}
}
</style>
"""


def _compact_roster_button_label(original):
    def wrapped(player: dict[str, Any], selected: bool = False) -> str:
        base = original(player, selected)
        position = str(player.get("position") or "").strip()
        return f"{base} • {position}" if position else base
    return wrapped


def _clean_loading_spotlight_html(context: dict[str, Any], final: dict[str, Any] | None = None) -> str:
    source = step9._spotlight_html(context, final)
    if final is None:
        loading = '<div class="value mx50-load"><span></span><span></span><span></span></div>'
        source = source.replace('<div class="value">…</div>', loading)
        source = source.replace("V2 calculating…", "Analyzing matchup…")
    return source


def _render_spotlight(slot, context: dict[str, Any] | None, final: dict[str, Any] | None = None) -> None:
    if not context:
        slot.info("Player spotlight is waiting for a verified selection.")
        return
    slot.markdown(_clean_loading_spotlight_html(context, final), unsafe_allow_html=True)


def _step12_profile_with_spotlight(original, slot, context):
    def wrapped(profile: dict[str, Any] | None) -> None:
        _render_spotlight(slot, context, profile)
        return original(profile)
    return wrapped


def _legacy_text_input_passthrough(original):
    """Suppress only downstream duplicate Search player widgets.

    The real roster search is rendered earlier inside the Change player controls;
    any later Search player input belongs to a legacy surface and would otherwise
    appear below Deep Matchup Research on mobile.
    """
    def wrapped(label, *args, **kwargs):
        if str(label or "").strip().lower() == "search player":
            key = kwargs.get("key")
            return str(st.session_state.get(key, "")) if key else ""
        return original(label, *args, **kwargs)
    return wrapped


def _legacy_markdown_passthrough(original):
    """Do not create hidden legacy shell elements at all, avoiding blank gaps."""
    markers = ('class="mh-hero"', 'class="mh-game"', 'class="mh-player"')

    def wrapped(body, *args, **kwargs):
        text = str(body or "")
        if any(marker in text for marker in markers):
            return None
        return original(body, *args, **kwargs)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    st.markdown(step9._STEP9_CSS + _STEP10_CSS, unsafe_allow_html=True)

    # Keep Search player inside Change player, but make roster buttons self-contained
    # so no detached "Team • Position" crumbs remain between groups.
    original_button_label = step3._button_label
    step3._button_label = _compact_roster_button_label(original_button_label)
    try:
        step6._render_compact_controls(games_df)
    finally:
        step3._button_label = original_button_label

    context = step4._selected_context(games_df)
    hero_slot = st.empty()
    _render_spotlight(hero_slot, context, None)

    original_selectbox = st.selectbox
    original_text_input = st.text_input
    original_markdown = st.markdown
    original_expander = st.expander
    original_caption = st.caption
    original_step12_profile = final_layer._render_step12_profile

    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    st.text_input = _legacy_text_input_passthrough(original_text_input)
    st.markdown = _legacy_markdown_passthrough(original_markdown)
    st.expander = step5._collapsed_expander(original_expander)
    st.caption = step9._clean_engine_caption(original_caption)
    final_layer._render_step12_profile = _step12_profile_with_spotlight(
        original_step12_profile,
        hero_slot,
        context,
    )
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        final_layer._render_step12_profile = original_step12_profile
        st.caption = original_caption
        st.expander = original_expander
        st.markdown = original_markdown
        st.text_input = original_text_input
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP9_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_clean_loading_spotlight_html",
    "_legacy_text_input_passthrough",
    "render_matchup_hub",
]
