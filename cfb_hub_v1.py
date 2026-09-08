"""College Football hub V1 — Step 1 section + page foundation.

This module intentionally contains no CFB projection/model math yet.

Step 1 contract
---------------
- add a dedicated College Football section,
- expose exactly three initial pages:
  * Moneyline
  * Over/Under
  * Game Total
- keep each page isolated and ready for later schedule/data/model steps,
- make no changes to MLB, WNBA, or NFL model behavior.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

MODEL_VERSION = "CFB HUB V1 • STEP 1 SECTION FOUNDATION"

CFB_MARKETS = [
    "Moneyline",
    "Over/Under",
    "Game Total",
]

_PAGE_PLAN = {
    "Moneyline": {
        "icon": "🏆",
        "title": "College Football Moneyline",
        "subtitle": "Winner probability and team-vs-team game analysis.",
        "next_step": "Schedule/game identity → team data → Moneyline model.",
    },
    "Over/Under": {
        "icon": "↕️",
        "title": "College Football Over/Under",
        "subtitle": "Sportsbook total-line analysis and Over/Under probability.",
        "next_step": "Schedule/game identity → scoring environment → O/U model.",
    },
    "Game Total": {
        "icon": "🧮",
        "title": "College Football Game Total",
        "subtitle": "Independent projected combined score and total distribution.",
        "next_step": "Schedule/game identity → scoring projection → total distribution.",
    },
}


def _page_card(market: str) -> str:
    cfg = _PAGE_PLAN[market]
    return f"""
<div class="cfb1-card">
  <div class="cfb1-kicker">CFB STEP 1 • FOUNDATION ACTIVE</div>
  <div class="cfb1-title">{cfg['icon']} {cfg['title']}</div>
  <div class="cfb1-sub">{cfg['subtitle']}</div>
  <div class="cfb1-status">
    <span>ROUTE ✅</span>
    <span>PAGE ✅</span>
    <span>MODEL ⏳</span>
    <span>LIVE DATA ⏳</span>
  </div>
  <div class="cfb1-next"><b>Next:</b> {cfg['next_step']}</div>
</div>
"""


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    """Render the isolated CFB Step-1 shell for one selected market."""
    if market not in CFB_MARKETS:
        st.error(f"Unknown College Football market: {market}")
        return

    st.caption("🏈 COLLEGE FOOTBALL • Step 1 section/router foundation ACTIVE")
    st.markdown(
        """
<style>
.cfb1-card{border:1px solid rgba(56,189,248,.24);border-radius:16px;padding:16px;
background:linear-gradient(145deg,#0b1724,#09111a);margin-top:8px}
.cfb1-kicker{color:#65d7ff;font-size:.68rem;font-weight:950;letter-spacing:.10em}
.cfb1-title{color:#f8fbff;font-size:1.45rem;font-weight:950;margin-top:4px}
.cfb1-sub{color:#98aabd;font-size:.82rem;margin-top:4px}
.cfb1-status{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
.cfb1-status span{border:1px solid #2b465a;border-radius:999px;background:#0a1a27;
padding:5px 8px;color:#a9c4d6;font-size:.62rem;font-weight:850}
.cfb1-next{margin-top:12px;border-top:1px solid #1c3344;padding-top:9px;
color:#7f99ab;font-size:.72rem}.cfb1-next b{color:#d7edf9}
@media(max-width:700px){.cfb1-card{padding:13px}.cfb1-title{font-size:1.22rem}}
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(_page_card(market), unsafe_allow_html=True)

    st.info(
        "Step 1 is intentionally navigation-only. No College Football "
        "probabilities, picks, totals, sportsbook prices, or simulations are "
        "being generated yet."
    )


__all__ = ["CFB_MARKETS", "MODEL_VERSION", "render_cfb_hub"]
