"""MLB Matchup Explorer V5.0 — cleanup Step 5 collapsed research.

Presentation-only wrapper over certified Cleanup Step 4 and Matchup Intelligence
V2. The selected-player hero/final result remains above the fold while detailed
Steps 1-12, frozen V1 audit and rankings stay collapsed until the user asks for
them. No projection, probability, calibration or ranking math is changed.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v43 as step2
import mlb_matchup_hub_v44 as step3
import mlb_matchup_hub_v45 as step4
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.0 • Cleanup Step 5"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP1_PRESENTATION = "mlb_matchup_hub_v42"
FROZEN_STEP2_PRESENTATION = "mlb_matchup_hub_v43"
FROZEN_STEP3_PRESENTATION = "mlb_matchup_hub_v44"
FROZEN_STEP4_PRESENTATION = "mlb_matchup_hub_v45"

DEEP_RESEARCH_LABEL = "🔬 Deep Matchup Research — Steps 1–12"
LEGACY_RESEARCH_LABEL = "🧊 Legacy V1 Audit — optional"

_STEP5_CSS = r"""
<style>
.mx46-note{border:1px solid #243f56;background:#09141f;border-radius:12px;padding:8px 10px;margin:-7px 0 12px;font-size:.59rem;color:#7f98ae;line-height:1.4}
.mx46-note b{color:#c8d8e6;font-weight:850}
@media(max-width:640px){.mx46-note{font-size:.55rem;padding:7px 9px}}
</style>
"""


def _force_collapsed(original, label: str, replacement: str | None, args: tuple[Any, ...], kwargs: dict[str, Any]):
    call_args = list(args)
    call_kwargs = dict(kwargs)
    if call_args and isinstance(call_args[0], bool):
        call_args[0] = False
        call_kwargs.pop("expanded", None)
    else:
        call_kwargs["expanded"] = False
    return original(replacement or label, *call_args, **call_kwargs)


def _collapsed_expander(original):
    """Collapse only deep/optional Matchup sections; preserve every other expander."""
    def wrapped(label: Any, *args: Any, **kwargs: Any):
        text = str(label or "")
        if text == final_layer.V2_INTELLIGENCE_LABEL:
            return _force_collapsed(original, text, DEEP_RESEARCH_LABEL, args, kwargs)
        if text == final_layer.LEGACY_AUDIT_LABEL:
            return _force_collapsed(original, text, LEGACY_RESEARCH_LABEL, args, kwargs)
        if "Daily Top 5" in text:
            return _force_collapsed(original, text, None, args, kwargs)
        return original(label, *args, **kwargs)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    # Keep certified Cleanup Steps 2-4 above the deep research surface.
    game_index = step2._render_game_cards(games_df)
    step3._render_roster_groups(games_df, game_index)

    context = step4._selected_context(games_df)
    hero_slot = st.empty()
    step4._render_hero(hero_slot, context, None)
    st.markdown(
        _STEP5_CSS
        + '<div class="mx46-note"><b>Final result stays up top.</b> Open Deep Matchup Research only when you want the full Steps 1–12 breakdown; Legacy V1 and Daily Top 5 remain optional.</div>',
        unsafe_allow_html=True,
    )

    original_selectbox = st.selectbox
    original_expander = st.expander
    original_step12_profile = final_layer._render_step12_profile

    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    st.expander = _collapsed_expander(original_expander)
    final_layer._render_step12_profile = step4._step12_profile_with_hero(
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
    "DEEP_RESEARCH_LABEL",
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP1_PRESENTATION",
    "FROZEN_STEP2_PRESENTATION",
    "FROZEN_STEP3_PRESENTATION",
    "FROZEN_STEP4_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "LEGACY_RESEARCH_LABEL",
    "VERSION",
    "_collapsed_expander",
    "render_matchup_hub",
]
