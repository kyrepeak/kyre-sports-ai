"""WNBA Daily Picks V1 — Step 1 isolated dashboard shell.

This page intentionally imports no PRA, Points, Rebounds, sportsbook, schedule,
injury, projection or Monte Carlo modules. It is a display-only shell so the
cross-market Daily Picks architecture can be built one verified section at a
time without changing any existing production model.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

MODEL_VERSION = "WNBA DAILY PICKS V1 • STEP 1 ISOLATED SHELL"
_ET = ZoneInfo("America/New_York")


def _status_card(label: str, status: str, note: str = "") -> str:
    tone = "#fbbf24" if "PAUSED" in status else "#94a3b8"
    return f"""
    <div style="
        min-height:112px;
        padding:16px 17px;
        border:1px solid rgba(56,189,248,.24);
        border-radius:16px;
        background:linear-gradient(180deg,rgba(10,31,47,.98),rgba(7,24,38,.98));
        box-shadow:0 8px 24px rgba(0,0,0,.12);">
      <div style="color:#8fa1bd;font-size:.68rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;">{label}</div>
      <div style="margin-top:9px;color:{tone};font-size:1.02rem;font-weight:900;">{status}</div>
      <div style="margin-top:7px;color:#7f91aa;font-size:.68rem;font-weight:700;">{note}</div>
    </div>
    """


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")

    st.markdown(
        """
        <style>
        .ks-dp-hero{
            padding:24px 26px;
            margin:4px 0 18px;
            border:1px solid rgba(56,189,248,.34);
            border-radius:24px;
            background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(10,24,46,.99));
            box-shadow:0 14px 38px rgba(0,0,0,.16);
        }
        .ks-dp-kicker{
            color:#67e8f9;
            font-size:.69rem;
            font-weight:950;
            letter-spacing:.13em;
            text-transform:uppercase;
        }
        .ks-dp-title{
            margin-top:9px;
            color:#f8fafc;
            font-size:2.08rem;
            line-height:1.08;
            font-weight:950;
        }
        .ks-dp-sub{
            margin-top:12px;
            color:#9fb0c6;
            font-size:.91rem;
            line-height:1.6;
            font-weight:650;
        }
        .ks-dp-chip{
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
        <div class="ks-dp-hero">
          <div class="ks-dp-kicker">KYRE SPORTS AI • WNBA DAILY PICKS • STEP 1</div>
          <div class="ks-dp-title">🏆 WNBA Daily Picks Command Center</div>
          <div class="ks-dp-sub">
            New isolated cross-market workspace. PRA, Points and Rebounds remain paused exactly where they are.
            This page does not read, run, patch, restore, regrade or modify any production model yet.
          </div>
          <span class="ks-dp-chip">📅 ET slate {slate_day}</span>
          <span class="ks-dp-chip">🧱 isolated shell</span>
          <span class="ks-dp-chip">🚫 zero model connectors</span>
          <span class="ks-dp-chip">🚫 zero simulations</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.success(
        "✅ STEP 1 PASSED • Daily Picks now has its own independent page. No PRA, Points or Rebounds model code is imported by this page."
    )

    st.markdown("### 🧩 Market Feed Status")
    st.caption("Step 1 is intentionally connection-free. These are architecture placeholders only; they do not inspect model state.")

    row1 = st.columns(4, gap="small")
    cards1 = [
        ("PRA", "⏸ PAUSED", "Existing PRA page unchanged"),
        ("Points", "⏸ PAUSED", "Existing Points page unchanged"),
        ("Rebounds", "⏸ PAUSED", "Existing Rebounds page unchanged"),
        ("Assists", "NEXT", "Future independent feed"),
    ]
    for col, (label, status, note) in zip(row1, cards1):
        with col:
            st.markdown(_status_card(label, status, note), unsafe_allow_html=True)

    row2 = st.columns(3, gap="small")
    cards2 = [
        ("Spread", "NEXT", "Future independent feed"),
        ("Moneyline", "NEXT", "Future independent feed"),
        ("Game Total", "NEXT", "Future independent feed"),
    ]
    for col, (label, status, note) in zip(row2, cards2):
        with col:
            st.markdown(_status_card(label, status, note), unsafe_allow_html=True)

    st.markdown("### 🏆 Top 5 WNBA Picks")
    st.info(
        "Step 1 shell only — no picks are connected yet. We will add one read-only market connector at a time after this page is verified."
    )

    with st.expander("🛡️ Step-1 isolation diagnostics", expanded=False):
        st.write("• Production model imports: 0")
        st.write("• Sportsbook requests: 0")
        st.write("• Monte Carlo runs: 0")
        st.write("• Session-state writes to PRA/Points/Rebounds: 0")
        st.write("• Current task: verify the new Daily Picks page renders cleanly before adding any connector")

    st.caption(
        "⚡ WNBA Daily Picks V1 Step 1 • isolated shell only • existing PRA/Points/Rebounds pages unchanged • no cross-market ranking yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
