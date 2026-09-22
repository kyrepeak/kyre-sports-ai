"""NFL Passing Yards V46 — compact top control deck.

Presentation-only wrapper over frozen V45. Step 1 of the Passing Yards visual
upgrade. It groups the slate date and verified matchup into one compact top
control deck, suppresses only the duplicate legacy date widget later in the
frozen pipeline, and tightens Passing Yards-only vertical spacing.

No schedule-provider ownership, identity, projection, probability, market,
edge, routing outside Passing Yards, or sportsbook influence changes.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v41 as rolling
import nfl_passing_yards_hub_v42 as navigation
import nfl_passing_yards_hub_v45 as prior

MODEL_VERSION = "NFL PASSING YARDS V46 • COMPACT TOP CONTROL DECK"
FROZEN_PRIOR = "nfl_passing_yards_hub_v45"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

TOP_CONTAINER_KEY = "kyre_passing_yards_top_v46"
TOP_DATE_KEY = "nfl_passing_yards_v46_slate_date"

_TOP_CSS = r"""
<style data-passing-yards-top-polish="v46">
.st-key-kyre_passing_yards_top_v46{
  margin:.15rem 0 .55rem!important;
  padding:.72rem .82rem .8rem!important;
  border:1px solid rgba(88,201,255,.22)!important;
  border-radius:16px!important;
  background:
    linear-gradient(145deg,rgba(12,29,45,.96),rgba(7,17,27,.96))!important;
  box-shadow:0 10px 30px rgba(0,0,0,.18),0 0 24px rgba(46,168,255,.06)!important;
}
.st-key-kyre_passing_yards_top_v46 [data-testid="stVerticalBlock"]{
  gap:.38rem!important;
}
.st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"]{
  gap:.7rem!important;
  align-items:end!important;
}
.st-key-kyre_passing_yards_top_v46 [data-testid="stDateInput"],
.st-key-kyre_passing_yards_top_v46 [data-testid="stSelectbox"]{
  margin:0!important;
}
.st-key-kyre_passing_yards_top_v46 label{
  color:#bfeaff!important;
  font-size:.68rem!important;
  font-weight:850!important;
  letter-spacing:.025em!important;
}
.st-key-kyre_passing_yards_top_v46 [data-baseweb="input"],
.st-key-kyre_passing_yards_top_v46 [data-baseweb="select"]>div{
  min-height:46px!important;
  background:#091521!important;
  border-color:rgba(88,201,255,.18)!important;
  border-radius:12px!important;
}
[data-testid="stAppViewContainer"] .main .block-container > [data-testid="stVerticalBlock"]{
  gap:.72rem!important;
}
[data-testid="stAppViewContainer"] .main .block-container
[data-testid="stElementContainer"]:has(> div:empty){
  min-height:0!important;
  height:auto!important;
  margin:0!important;
  padding:0!important;
}
@media(max-width:720px){
  .st-key-kyre_passing_yards_top_v46{
    padding:.62rem!important;
    border-radius:14px!important;
  }
  .st-key-kyre_passing_yards_top_v46 [data-testid="stHorizontalBlock"]{
    gap:.5rem!important;
  }
}
</style>
"""

def _safe(value: Any) -> str:
    return str(value if value is not None else "").strip()

def _compact_navigation(original_selectbox) -> str | None:
    selected_day = rolling._selected_date()

    if TOP_DATE_KEY not in st.session_state:
        st.session_state[TOP_DATE_KEY] = selected_day

    shell = st.container(key=TOP_CONTAINER_KEY)
    with shell:
        st.caption("🏈 PASSING YARDS CONTROL DECK")
        date_col, matchup_col = st.columns([0.82, 2.18], gap="small")

        with date_col:
            chosen_day = st.date_input(
                "Slate date",
                key=TOP_DATE_KEY,
                label_visibility="visible",
            )

        if chosen_day != selected_day:
            st.session_state[rolling.V8_DATE_KEY] = chosen_day
            st.session_state.pop(rolling.V8_MATCHUP_KEY, None)
            st.session_state.pop(navigation.VISIBLE_MATCHUP_KEY, None)

        labels, _diag = navigation._verified_matchup_labels(chosen_day)

        with matchup_col:
            if not labels:
                st.warning("No verified NFL games available for this slate date.")
                return None

            legacy_value = _safe(st.session_state.get(rolling.V8_MATCHUP_KEY))
            visible_value = _safe(st.session_state.get(navigation.VISIBLE_MATCHUP_KEY))
            if visible_value not in labels:
                st.session_state.pop(navigation.VISIBLE_MATCHUP_KEY, None)
                if legacy_value in labels:
                    st.session_state[navigation.VISIBLE_MATCHUP_KEY] = legacy_value

            chosen = original_selectbox(
                f"Matchup • {len(labels)} verified games",
                labels,
                key=navigation.VISIBLE_MATCHUP_KEY,
                format_func=lambda option: navigation.phoenix_display._phoenix_matchup_option(
                    option,
                    chosen_day,
                ),
                label_visibility="visible",
            )

        st.session_state[rolling.V8_DATE_KEY] = chosen_day
        st.session_state[rolling.V8_MATCHUP_KEY] = chosen
        return chosen

def _suppress_duplicate_date_proxy(original_factory):
    def factory(resolved_day, original_date_input):
        frozen_proxy = original_factory(resolved_day, original_date_input)

        def wrapped(label, *args, **kwargs):
            if str(label) == "NFL Passing Yards slate date":
                return resolved_day
            return frozen_proxy(label, *args, **kwargs)

        return wrapped

    return factory

def render_nfl_passing_yards_hub() -> None:
    original_navigation = navigation._render_visible_matchup_navigation
    original_date_factory = rolling._date_input_proxy

    st.markdown(_TOP_CSS, unsafe_allow_html=True)
    navigation._render_visible_matchup_navigation = _compact_navigation
    rolling._date_input_proxy = _suppress_duplicate_date_proxy(original_date_factory)

    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        navigation._render_visible_matchup_navigation = original_navigation
        rolling._date_input_proxy = original_date_factory

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V46 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "TOP_CONTAINER_KEY",
    "TOP_DATE_KEY",
    "_compact_navigation",
    "_suppress_duplicate_date_proxy",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
