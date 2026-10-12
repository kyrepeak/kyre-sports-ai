"""NBA Spread Page 1 — Step 2 reachable production shell.

This step activates only the website surface. Data sourcing, schedule assembly,
market consensus, injuries, model projection, cover probability and ranking are
owned by later certified steps.
"""
from __future__ import annotations

import streamlit as st

MODEL_VERSION = "NBA_SPREAD_PAGE_V1_STEP2_SITE_ACTIVATION"
PAGE_HEARTBEAT = "NBA_SPREAD_STEP2_SITE_ACTIVATION_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False


def render_nba_spread_page() -> None:
    st.markdown(
        f'<div data-testid="nba-spread-step2-active" '
        f'data-heartbeat="{PAGE_HEARTBEAT}" style="display:none!important"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div style="border:1px solid rgba(56,189,248,.32);border-radius:24px;padding:22px 24px;
background:linear-gradient(135deg,rgba(8,13,22,.98),rgba(15,36,60,.96));margin:8px 0 16px">
  <div style="font-size:.72rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#67d8ff">
    KYRE SPORTS AI • NBA
  </div>
  <div style="font-size:clamp(2rem,6vw,3.1rem);font-weight:950;letter-spacing:-.045em;color:#f8fafc;margin-top:5px">
    🏀 NBA Spread
  </div>
  <div style="font-size:.88rem;color:#a9b8c8;margin-top:7px">
    Phoenix, Arizona time • two-page spread intelligence experience
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div style="border:1px solid rgba(148,163,184,.18);border-radius:18px;padding:16px 18px;background:#0b1422">
  <div style="font-weight:850;color:#f8fafc">NBA Spread foundation is active.</div>
  <div style="font-size:.8rem;color:#94a3b8;margin-top:5px">
    The protected Page 1 data, market-intelligence and model layers are added in the next certified build steps.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


__all__ = [
    "MODEL_VERSION",
    "PAGE_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "render_nba_spread_page",
]
