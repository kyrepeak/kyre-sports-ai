"""NFL Game Totals V10 — Step 10 final page certification layer.

V10 preserves V9 model-vs-market logic and V8.1 mobile controls. It changes no
projection, market, selection, or wager math; it only marks the connected page
build complete and renders the final integrity state.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v9 as v9

MODEL_VERSION = "NFL GAME TOTALS V10 • PAGE STEP 10 FINAL CERTIFICATION"
PAGE_BUILD_STEP = 10
PAGE_BUILD_TOTAL = 10
FINAL_CERTIFICATION_ENABLED = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = True
TOTAL_PROJECTION_ENABLED = True
MARKET_COMPARISON_ENABLED = True
LIVE_MARKET_ENABLED = True
OFFENSE_DEFENSE_ENABLED = True
PACE_POSSESSION_ENABLED = True
EXPLOSIVE_SCORING_ENABLED = True
RED_ZONE_DRIVE_SUSTAINABILITY_ENABLED = True
GAME_ENVIRONMENT_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

_STEP10_CSS = r'''
<style>
.kgt-fill.step10{width:100%}
.kgt-cert{margin:10px 0;border:1px solid #326b59;border-radius:12px;background:linear-gradient(180deg,#0c1b16,#09120f);padding:10px}.kgt-cert b{color:#8ef0c5;font-size:.62rem}.kgt-cert span{display:block;margin-top:4px;color:#8fb4a5;font-size:.44rem;line-height:1.45}
</style>
'''


def _progress_html() -> str:
    stages = (
        ("1", "VERIFIED SLATE", True),
        ("2", "LIVE TOTAL", True),
        ("3", "OFFENSE VS DEFENSE", True),
        ("4", "PACE + POSSESSION", True),
        ("5", "EXPLOSIVE SCORING", True),
        ("6", "RED ZONE + DRIVES", True),
        ("7", "GAME ENVIRONMENT", True),
        ("8", "TOTAL PROJECTION", True),
        ("9", "MARKET + FINAL READ", True),
        ("10", "FINAL CERTIFICATION", True),
    )
    stage_html = "".join(
        f'<div class="kgt-stage{" on" if active else ""}">{number} • {label}</div>'
        for number, label, active in stages
    )
    return (
        '<div class="kgt-progress">'
        '<div class="kgt-progress-top"><b>🏟️ Game Totals connected page build</b><span>STEP 10 OF 10 • FINAL CERTIFICATION</span></div>'
        '<div class="kgt-track"><div class="kgt-fill step10"></div></div>'
        f'<div class="kgt-rail-wrap"><div class="kgt-rail">{stage_html}</div></div>'
        '</div>'
    )


def _render_hero() -> None:
    css = (
        v9.v8.v7.v6.v5.v4.v3.v2.foundation._GAME_TOTALS_CSS
        + v9.v8.v7.v6.v5.v4.v3.v2._STEP2_CSS
        + v9.v8.v7.v6.v5.v4.v3._STEP3_CSS
        + v9.v8.v7.v6.v5.v4._STEP4_CSS
        + v9.v8.v7.v6.v5._STEP5_CSS
        + v9.v8.v7.v6._STEP6_CSS
        + v9.v8.v7._STEP7_CSS
        + v9.v8._STEP8_CSS
        + v9._STEP9_CSS
        + _STEP10_CSS
    )
    st.markdown(
        css
        + '<div class="kgt-page"><div class="kgt-hero">'
        + '<div class="kgt-kicker">NFL GAME TOTALS • FINAL CONNECTED BUILD</div>'
        + '<div class="kgt-title">🏟️ Game Totals <span class="over">Over</span> / <span class="under">Under Lab</span></div>'
        + '<div class="kgt-sub">Step 10 certifies the full connected page: verified slate, exact live total, certified football context, sportsbook-free model total, and comparison-only OVER / UNDER / PASS final read.</div>'
        + '<div class="kgt-chiprow"><span class="kgt-chip teal">10 / 10 CONNECTED</span><span class="kgt-chip teal">FINAL READ LIVE</span><span class="kgt-chip lock">SPORTSBOOK INFLUENCE 0.0%</span><span class="kgt-chip lock">WAGER ACTIONS OFF</span></div>'
        + '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(_progress_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="kgt-cert"><b>✅ FINAL PAGE INTEGRITY</b><span>Projection remains independent from sportsbook data • FanDuel is comparison-only • ambiguous inputs fail closed • stake sizing OFF • wager actions OFF • V8.1 mobile navigation preserved.</span></div>',
        unsafe_allow_html=True,
    )


def render_nfl_game_totals_hub() -> None:
    _render_hero()
    today = pd.Timestamp.now(tz=v9.v8.v7.v6.v5.v4.v3.v2.foundation.ET).date()
    v9.mobile._apply_pending_date(today)
    selected = v9.mobile._initial_date(today)
    selected = v9.mobile._auto_surface_next_slate(selected, today)
    selected = st.date_input("📅 NFL Game Totals slate date", value=selected, key=v9.mobile._WIDGET_DATE_KEY)
    selected = v9.mobile._as_date(selected, today)
    v9.mobile._sync_game_totals_date(selected)
    feedback = st.session_state.pop(v9.mobile._FEEDBACK_KEY, None)
    if feedback:
        st.info(str(feedback))
    v9.mobile._render_mobile_controls(selected)
    day_str = selected.isoformat()
    with st.spinner("🏈 Verifying NFL Game Totals slate…"):
        games, diag = v9.v8.v7.v6.v5.v4.v3.v2.foundation.load_nfl_slate(day_str)
    v9._render_schedule(games, day_str, diag)
    if isinstance(diag, dict) and diag.get("request_ok") is True and games.empty:
        st.info("No verified NFL games were returned for this date. Tap **Next Game Day** above or **Reload Data** to refresh without rebooting Streamlit.")
    st.caption(f"{MODEL_VERSION} • 10/10 connected • sportsbook projection influence {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}% • final read ON • stake sizing OFF • wager actions OFF")


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V10 only renders the Game Total market.")
    return render_nfl_game_totals_hub()
