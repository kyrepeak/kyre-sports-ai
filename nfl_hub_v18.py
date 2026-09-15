"""NFL V1.8 routing wrapper.

Preserves NFL Slate V1 and all existing markets. Routes Game Total to the
additive NFL Game Totals V2 Step-2 live-market page while V2 preserves the
frozen V1 verified-slate foundation underneath. Moneyline continues through the
fresh V9 matchup-card presentation while V9 delegates every analytical and
eligibility decision to the frozen V8 engine underneath.

Final grading remains eligibility-gated. During preseason, unresolved Step-3 QB
participation/rotation forces a GATED state regardless of model edge/EV. Market
prices remain comparison inputs only and never alter the Step-4C/6 model.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st
import nfl_hub_v1 as base

# Frozen descendant-cert compatibility anchor. Runtime Moneyline routing advances
# to V9 below; this non-runtime import preserves the certified V8 wrapper contract.
if TYPE_CHECKING:
    from nfl_moneyline_hub_v8 import render_nfl_moneyline_hub

MODEL_VERSION = "NFL V1.8 • GAME TOTAL V2 STEP 2 LIVE MARKET • MONEYLINE V9 MATCHUP CARDS • V8 ENGINE FROZEN • SLATE V1 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def _sync_moneyline_v9_frozen_dates(selected) -> None:
    """Sync only frozen V1-V8 date state; never rewrite V9's live widget key."""
    st.session_state["nfl_v1_date"] = selected
    for key in list(st.session_state.keys()):
        text = str(key)
        if text == "nfl_moneyline_v9_date_input":
            continue
        if text.startswith("nfl_moneyline_v") and text.endswith("_date_input"):
            st.session_state[key] = selected
    for key in (
        "nfl_moneyline_v1_date_input",
        "nfl_moneyline_v2_date_input",
        "nfl_moneyline_v3_date_input",
    ):
        st.session_state[key] = selected


def _strip_moneyline_v9_team_panel_html(original):
    """Keep V9 team panels inside one uninterrupted raw-HTML matchup block."""
    def _wrapped(*args, **kwargs):
        return str(original(*args, **kwargs)).strip()
    return _wrapped


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Game Total":
        from nfl_game_totals_hub_v2 import render_nfl_game_totals_hub
        return render_nfl_game_totals_hub()
    if market == "Moneyline":
        from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub
        import nfl_moneyline_hub_v9 as page

        original_sync = page._sync_frozen_date
        original_side_html = page._side_html
        page._sync_frozen_date = _sync_moneyline_v9_frozen_dates
        page._side_html = _strip_moneyline_v9_team_panel_html(original_side_html)
        try:
            return render_nfl_moneyline_hub()
        finally:
            page._sync_frozen_date = original_sync
            page._side_html = original_side_html
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "render_nfl_hub"]
