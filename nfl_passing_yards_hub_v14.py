"""NFL Passing Yards V14 — cleanup step 2: signal-first page density.

Presentation-only wrapper over certified V13. It removes repetitive green success
alerts and model-version footer captions, keeps warnings/errors/info visible,
compacts methodology expanders and alerts, and forces analytical cards to stack
cleanly on phones. No data loader, model, probability, market, or sportsbook
logic is changed.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v13 as prior

MODEL_VERSION = "NFL PASSING YARDS V14 • CLEANUP STEP 2 • SIGNAL-FIRST DENSITY"

_CLEANUP_STEP2_CSS = r"""
<style>
/* Cleanup Step 2: preserve the analysis, remove production-page noise. */

/* Alerts that still matter (warning/info/error) should be compact and readable. */
div[data-testid="stAlert"]{border-radius:10px!important;padding:.48rem .62rem!important;margin:.3rem 0 .5rem!important}
div[data-testid="stAlert"] p{font-size:.76rem!important;line-height:1.42!important;margin:0!important}

/* Methodology/detail rows stay available, but stop dominating the mobile page. */
div[data-testid="stExpander"]{margin:.22rem 0!important;border-radius:10px!important}
div[data-testid="stExpander"] details summary{min-height:0!important;padding:.38rem .55rem!important}
div[data-testid="stExpander"] details summary p{font-size:.72rem!important;font-weight:760!important;line-height:1.25!important}
div[data-testid="stExpander"] details[open] summary{margin-bottom:.15rem!important}
div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p{font-size:.72rem!important;line-height:1.46!important}

/* Reduce vertical dead space between the certified analytical layers. */
.kpy-step{padding:9px 10px!important;margin:10px 0 6px!important}
.kpy-step-title{font-size:.84rem!important}.kpy-step-sub{font-size:.5rem!important}
.kpy-qbgrid,.kpy-pgrid,.kpy-dgrid,.kpy-xgrid,.kpy-igrid,.kpy-envteams,.kpy-projgrid,.kpy8-grid,.kpy9-grid,.kpy10-grid{margin-top:5px!important;margin-bottom:7px!important}
.kpy-personnel,.kpy-env,.kpy-proj,.kpy8-card,.kpy9-card,.kpy10-card{padding:9px!important;border-radius:12px!important}

/* Keep market-input controls visually grouped rather than giant mobile blocks. */
div[data-testid="stTextInput"]{margin-bottom:.1rem!important}
div[data-testid="stTextInput"] label p{font-size:.69rem!important}
div[data-testid="stTextInput"] input{min-height:2.35rem!important;padding:.42rem .58rem!important}

/* Tables are details, not the page headline. */
div[data-testid="stDataFrame"]{margin:.25rem 0 .35rem!important}

@media(max-width:700px){
  /* One readable card per row on phones. */
  .kpy-qbgrid,.kpy-pgrid,.kpy-dgrid,.kpy-xgrid,.kpy-igrid,.kpy-envteams,.kpy-projgrid,.kpy8-grid,.kpy9-grid,.kpy10-grid{grid-template-columns:1fr!important}
  .kpy-step{padding:8px 9px!important;margin-top:9px!important}
  .kpy-step-title{font-size:.8rem!important}
  .kpy-step-sub{font-size:.48rem!important}
  .kpy-personnel,.kpy-env,.kpy-proj,.kpy8-card,.kpy9-card,.kpy10-card{padding:8px!important}
  div[data-testid="stAlert"]{padding:.42rem .52rem!important}
  div[data-testid="stAlert"] p{font-size:.72rem!important}
  div[data-testid="stExpander"] details summary{padding:.34rem .48rem!important}
  div[data-testid="stExpander"] details summary p{font-size:.68rem!important}
}
</style>
"""


def _is_build_footer_caption(body: Any) -> bool:
    """Identify repeated version/footer captions, not evidence/detail captions."""
    text = str(body if body is not None else "").strip().upper()
    return text.startswith("NFL PASSING YARDS V")


def render_nfl_passing_yards_hub() -> None:
    """Render certified V13 while suppressing repetitive production chrome."""
    st.markdown(_CLEANUP_STEP2_CSS, unsafe_allow_html=True)

    original_success = st.success
    original_caption = st.caption

    def quiet_success(*args, **kwargs):
        # Step cards already expose their state. Repeating ten large green alert
        # boxes adds scroll length without adding decision information.
        return None

    def clean_caption(body, *args, **kwargs):
        if _is_build_footer_caption(body):
            return None
        return original_caption(body, *args, **kwargs)

    st.success = quiet_success
    st.caption = clean_caption
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        # Never leak presentation overrides into any other page/market.
        st.success = original_success
        st.caption = original_caption


__all__ = [
    "MODEL_VERSION",
    "_CLEANUP_STEP2_CSS",
    "_is_build_footer_caption",
    "render_nfl_passing_yards_hub",
]
