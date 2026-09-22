"""WNBA Assists V1 — Step 1 isolated foundation.

This page is intentionally display-only. It imports no PRA, Points, Rebounds,
Daily Picks, schedule, roster, injury, sportsbook, projection or Monte Carlo
production modules. The Assists model will be built one verified layer at a time
without changing any existing WNBA production page.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

MODEL_VERSION = "WNBA ASSISTS V1 • STEP 1 ISOLATED FOUNDATION"
_ET = ZoneInfo("America/New_York")


def _layer_card(step: int, label: str, state: str, note: str = "") -> str:
    if "LIVE" in state:
        tone = "#6ee7b7"
        border = "rgba(52,211,153,.34)"
    elif "NEXT" in state:
        tone = "#67e8f9"
        border = "rgba(56,189,248,.30)"
    else:
        tone = "#94a3b8"
        border = "rgba(148,163,184,.22)"
    return f"""
    <div style="
        min-height:118px;
        padding:15px 16px;
        border:1px solid {border};
        border-radius:16px;
        background:linear-gradient(180deg,rgba(10,31,47,.98),rgba(7,24,38,.98));
        box-shadow:0 8px 24px rgba(0,0,0,.12);">
      <div style="color:#7f91aa;font-size:.65rem;font-weight:900;letter-spacing:.10em;text-transform:uppercase;">STEP {step}</div>
      <div style="margin-top:7px;color:#f8fafc;font-size:.90rem;font-weight:900;line-height:1.25;">{label}</div>
      <div style="margin-top:8px;color:{tone};font-size:.78rem;font-weight:950;">{state}</div>
      <div style="margin-top:6px;color:#7f91aa;font-size:.64rem;font-weight:700;line-height:1.35;">{note}</div>
    </div>
    """


def render_wnba_assists_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")

    st.markdown(
        """
        <style>
        .ks-ast-hero{
            padding:25px 27px;
            margin:4px 0 18px;
            border:1px solid rgba(56,189,248,.34);
            border-radius:24px;
            background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(12,22,48,.99));
            box-shadow:0 14px 38px rgba(0,0,0,.16);
        }
        .ks-ast-kicker{
            color:#67e8f9;
            font-size:.69rem;
            font-weight:950;
            letter-spacing:.13em;
            text-transform:uppercase;
        }
        .ks-ast-title{
            margin-top:9px;
            color:#f8fafc;
            font-size:2.05rem;
            line-height:1.08;
            font-weight:950;
        }
        .ks-ast-sub{
            margin-top:12px;
            color:#9fb0c6;
            font-size:.91rem;
            line-height:1.62;
            font-weight:650;
        }
        .ks-ast-chip{
            display:inline-block;
            margin:14px 7px 0 0;
            padding:7px 10px;
            border:1px solid rgba(52,211,153,.35);
            border-radius:999px;
            background:rgba(16,185,129,.09);
            color:#6ee7b7;
            font-size:.69rem;
            font-weight:900;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="ks-ast-hero">
          <div class="ks-ast-kicker">KYRE SPORTS AI • WNBA ASSISTS INTELLIGENCE • STEP 1</div>
          <div class="ks-ast-title">🎯 WNBA Assists Command Center</div>
          <div class="ks-ast-sub">
            New isolated assists-only workspace. PRA, Points, Rebounds and Daily Picks remain frozen exactly where they are.
            Step 1 creates the page and build order only — it does not load a schedule, roster, injury feed, assist projection,
            sportsbook line or simulation.
          </div>
          <span class="ks-ast-chip">📅 ET slate {slate_day}</span>
          <span class="ks-ast-chip">🧱 isolated assists shell</span>
          <span class="ks-ast-chip">🚫 zero network/model calls</span>
          <span class="ks-ast-chip">🚫 zero simulations</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.success(
        "✅ STEP 1 PASSED • Assists now has its own independent WNBA page. Existing PRA, Points, Rebounds and Daily Picks production code is not imported or modified by this page."
    )

    st.markdown("### 🧱 Assists Build Order — Current")
    st.caption(
        "We will unlock one layer at a time. A later step may read verified output from an earlier step, but Step 1 itself is connection-free."
    )

    layers = [
        (1, "Isolated Assists page", "✅ LIVE", "Display shell only"),
        (2, "Verified daily WNBA slate", "➡️ NEXT", "Exact ET date + games"),
        (3, "Current rosters + injuries/status", "🔒 LOCKED", "No unavailable player may enter modeling"),
        (4, "Projected minutes + rotation", "🔒 LOCKED", "Assist opportunity starts with court time"),
        (5, "Assist role + ball-handling / usage", "🔒 LOCKED", "Primary/secondary creation responsibility"),
        (6, "Recent + season assist form", "🔒 LOCKED", "Minute-normalized, regression protected"),
        (7, "Potential assists / passes / creation chances", "🔒 LOCKED", "Opportunity layer before conversion"),
        (8, "Teammate shot-making + lineup conversion", "🔒 LOCKED", "Who finishes the created chances"),
        (9, "Opponent assist environment", "🔒 LOCKED", "Opponent scheme + assists allowed"),
        (10, "Position matchup — Guard / Wing / Big", "🔒 LOCKED", "Role-sensitive matchup context"),
        (11, "Pace + expected possession volume", "🔒 LOCKED", "Possession opportunity adjustment"),
        (12, "Player vs opponent assist history", "🔒 LOCKED", "Descriptive H2H context"),
        (13, "Exact SportsGameOdds assist lines", "🔒 LOCKED", "Exact book / line / side only"),
        (14, "Same-book no-vig", "🔒 LOCKED", "Market math stays separate from projection"),
        (15, "Market-independent assist projection", "🔒 LOCKED", "Expected assists before market grading"),
        (16, "Uncertainty + distribution calibration", "🔒 LOCKED", "Discrete assist count distribution"),
        (17, "5M Monte Carlo + convergence / sensitivity", "🔒 LOCKED", "Actual simulations only"),
        (18, "Line-specific O/U probability + fair odds", "🔒 LOCKED", "Threshold probabilities from model distribution"),
        (19, "Model-vs-market edge + EV", "🔒 LOCKED", "Exact posted price grading"),
        (20, "Risk-adjusted qualification + Top 5", "🔒 LOCKED", "Never force five"),
    ]

    for start in range(0, len(layers), 4):
        cols = st.columns(4, gap="small")
        for col, item in zip(cols, layers[start:start + 4]):
            with col:
                st.markdown(_layer_card(*item), unsafe_allow_html=True)

    st.info(
        "Step 1 stops here on purpose. Step 2 will add only the verified same-day WNBA schedule. No assist projection or sportsbook logic will be introduced until its earlier dependencies are verified."
    )

    with st.expander("🛡️ Step-1 isolation diagnostics", expanded=False):
        st.write("• PRA production imports: 0")
        st.write("• Points production imports: 0")
        st.write("• Rebounds production imports: 0")
        st.write("• Daily Picks imports: 0")
        st.write("• Schedule / roster / injury requests: 0")
        st.write("• Sportsbook requests: 0")
        st.write("• Monte Carlo runs: 0")
        st.write("• Source-model state writes: 0")
        st.write("• Current task: verify the isolated Assists page before adding Step 2")

    st.caption(
        "⚡ WNBA Assists V1 Step 1 • isolated foundation only • PRA/Points/Rebounds/Daily Picks unchanged • no projection, market grading or Monte Carlo yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_assists_hub"]
