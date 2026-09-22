"""WNBA Daily Picks V3 — Step 3 PRA + Points read-only connectors.

Step 1 isolated the page. Step 2 added passive PRA inspection. Step 3 adds one
more passive connector: Points. Both connectors read only already-completed
same-day Streamlit session payloads and never import production models, launch
simulations, restore snapshots, request sportsbook data, refresh injuries or
lineups, regrade rows, alter projections, or write back into PRA/Points state.
Rebounds remains paused and disconnected. Top-5 ranking remains OFF.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed

MODEL_VERSION = "WNBA DAILY PICKS V3 • STEP 3 PRA + POINTS READ ONLY"
_ET = ZoneInfo("America/New_York")


def _status_card(label: str, status: str, note: str = "") -> str:
    upper = str(status).upper()
    if "CONNECTED" in upper:
        tone, border = "#64e5aa", "rgba(52,211,153,.42)"
    elif "PAUSED" in upper or "NOT RUN" in upper or "CHECK" in upper:
        tone, border = "#fbbf24", "rgba(251,191,36,.34)"
    else:
        tone, border = "#94a3b8", "rgba(56,189,248,.24)"
    return f"""
    <div style="min-height:118px;padding:16px 17px;border:1px solid {border};border-radius:16px;
      background:linear-gradient(180deg,rgba(10,31,47,.98),rgba(7,24,38,.98));box-shadow:0 8px 24px rgba(0,0,0,.12);">
      <div style="color:#8fa1bd;font-size:.68rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;">{escape(label)}</div>
      <div style="margin-top:9px;color:{tone};font-size:1.02rem;font-weight:900;">{escape(status)}</div>
      <div style="margin-top:7px;color:#7f91aa;font-size:.68rem;font-weight:700;line-height:1.35;">{escape(note)}</div>
    </div>
    """


def _fmt_pct(value):
    try:
        x = float(value)
        if pd.isna(x):
            return "—"
        return f"{100*x:.1f}%"
    except Exception:
        return "—"


def _fmt_pp(value):
    try:
        x = float(value)
        if pd.isna(x):
            return "—"
        return f"{100*x:+.1f} pp"
    except Exception:
        return "—"


def _fmt_money(value):
    try:
        x = float(value)
        if pd.isna(x):
            return "—"
        return f"{x:+.1f}"
    except Exception:
        return "—"


def _pra_preview_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    d = frame.copy().rename(columns={
        "player": "Player", "team": "Team", "opponent": "Opponent", "book": "Book",
        "line": "Line", "projection": "Proj PRA", "model_over": "P(Over)",
        "no_vig_over": "No-vig O", "edge": "Edge", "freshness": "Freshness",
        "converged": "Converged", "model_qualified": "Qualified",
        "final_ready": "Final ready", "status": "PRA status", "sims": "Sims",
    })
    if "P(Over)" in d.columns:
        d["P(Over)"] = d["P(Over)"].map(_fmt_pct)
    if "No-vig O" in d.columns:
        d["No-vig O"] = d["No-vig O"].map(_fmt_pct)
    if "Edge" in d.columns:
        d["Edge"] = d["Edge"].map(_fmt_pp)
    if "Sims" in d.columns:
        d["Sims"] = pd.to_numeric(d["Sims"], errors="coerce").map(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
    for c in ("Converged", "Qualified", "Final ready"):
        if c in d.columns:
            d[c] = d[c].map(lambda x: "✅" if bool(x) else "—")
    return d


def _points_preview_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    d = frame.copy().rename(columns={
        "market": "Market", "player": "Player", "team": "Team", "opponent": "Opponent",
        "book": "Book", "line": "Line", "projection": "Proj PTS", "sim_mean": "MC mean",
        "sim_median": "Median", "model_over": "P(Over)", "no_vig_over": "No-vig O",
        "edge": "Edge", "ev100": "EV/$100", "freshness": "Freshness",
        "lineup_ready": "Lineup ready", "converged": "Converged",
        "model_qualified": "Qualified", "final_ready": "Final ready",
        "status": "Points status", "sims": "Sims", "pass_source": "Pass",
    })
    if "P(Over)" in d.columns:
        d["P(Over)"] = d["P(Over)"].map(_fmt_pct)
    if "No-vig O" in d.columns:
        d["No-vig O"] = d["No-vig O"].map(_fmt_pct)
    if "Edge" in d.columns:
        d["Edge"] = d["Edge"].map(_fmt_pp)
    if "EV/$100" in d.columns:
        d["EV/$100"] = d["EV/$100"].map(_fmt_money)
    if "Sims" in d.columns:
        d["Sims"] = pd.to_numeric(d["Sims"], errors="coerce").map(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
    for c in ("Lineup ready", "Converged", "Qualified", "Final ready"):
        if c in d.columns:
            d[c] = d[c].map(lambda x: "✅" if bool(x) else "—")
    return d


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    pra = pra_feed.status(slate_day)
    points = points_feed.status(slate_day)

    st.markdown(
        """
        <style>
        .ks-dp-hero{padding:24px 26px;margin:4px 0 18px;border:1px solid rgba(56,189,248,.34);border-radius:24px;
          background:linear-gradient(135deg,rgba(6,28,44,.99),rgba(10,24,46,.99));box-shadow:0 14px 38px rgba(0,0,0,.16);}
        .ks-dp-kicker{color:#67e8f9;font-size:.69rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase;}
        .ks-dp-title{margin-top:9px;color:#f8fafc;font-size:2.08rem;line-height:1.08;font-weight:950;}
        .ks-dp-sub{margin-top:12px;color:#9fb0c6;font-size:.91rem;line-height:1.6;font-weight:650;}
        .ks-dp-chip{display:inline-block;margin:14px 7px 0 0;padding:7px 10px;border:1px solid rgba(52,211,153,.35);
          border-radius:999px;background:rgba(16,185,129,.09);color:#6ee7b7;font-size:.69rem;font-weight:900;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="ks-dp-hero">
          <div class="ks-dp-kicker">KYRE SPORTS AI • WNBA DAILY PICKS • STEP 3</div>
          <div class="ks-dp-title">🏆 WNBA Daily Picks Command Center</div>
          <div class="ks-dp-sub">
            Independent cross-market workspace. PRA and Points are now visible through passive, read-only connectors.
            Daily Picks cannot run, restore, regrade, refresh, modify or write back to either model.
            Rebounds remains paused. Cross-market Top-5 ranking is still disabled.
          </div>
          <span class="ks-dp-chip">📅 ET slate {slate_day}</span>
          <span class="ks-dp-chip">🔌 2 read-only connectors</span>
          <span class="ks-dp-chip">🚫 zero simulations launched here</span>
          <span class="ks-dp-chip">🔒 zero model writes</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.success(
        "✅ STEP 3 ACTIVE • PRA + Points are connected read-only. Daily Picks can inspect completed outputs without controlling either production model."
    )

    st.markdown("### 🧩 Market Feed Status")
    st.caption("PRA and Points are inspected independently. Rebounds remains deliberately disconnected.")

    pra_note = (
        f"{pra.get('source','NONE')} • {pra.get('unique_distributions',0)} distributions • {pra.get('qualified',0)} qualified"
        if pra.get("connected") else str(pra.get("detail") or "No same-day PRA payload loaded")
    )
    points_note = (
        f"{points.get('source','NONE')} • {points.get('unique_distributions',0)} distributions • {points.get('qualified',0)} qualified"
        if points.get("connected") else str(points.get("detail") or "No same-day Points payload loaded")
    )

    row1 = st.columns(4, gap="small")
    cards1 = [
        ("PRA", str(pra.get("state") or "⏳ NOT RUN"), pra_note),
        ("Points", str(points.get("state") or "⏳ NOT RUN"), points_note),
        ("Rebounds", "⏸ PAUSED", "Existing Rebounds page unchanged"),
        ("Assists", "NEXT", "Future independent feed"),
    ]
    for col, (label, state, note) in zip(row1, cards1):
        with col:
            st.markdown(_status_card(label, state, note), unsafe_allow_html=True)

    row2 = st.columns(3, gap="small")
    for col, item in zip(row2, [
        ("Spread", "NEXT", "Future independent feed"),
        ("Moneyline", "NEXT", "Future independent feed"),
        ("Game Total", "NEXT", "Future independent feed"),
    ]):
        with col:
            st.markdown(_status_card(*item), unsafe_allow_html=True)

    st.markdown("### 🔌 PRA Read-Only Connector")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Connection", "CONNECTED" if pra.get("connected") else "NOT RUN")
    c2.metric("PRA distributions", int(pra.get("unique_distributions", 0)))
    c3.metric("Qualified", int(pra.get("qualified", 0)))
    c4.metric("Final ready", int(pra.get("final_ready", 0)))
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Monitor", int(pra.get("monitor", 0)))
    c6.metric("Converged", f"{int(pra.get('converged',0))}/{int(pra.get('unique_distributions',0))}")
    c7.metric("Completed sims", f"{int(pra.get('completed_sims',0)):,}")
    c8.metric("10M finalist rows", int(pra.get("finalist_rows", 0)))
    st.caption(
        f"PRA slate {pra.get('day') or slate_day} • source {pra.get('source') or 'NONE'} • "
        f"5M ran at {pra.get('ran_at') or '—'} • 10M ran at {pra.get('final_ran_at') or '—'}"
    )
    if pra.get("connected"):
        st.success("✅ PRA READ-ONLY CHECK PASSED • completed, converged same-day PRA output is visible to Daily Picks.")
    else:
        st.info("⏳ PRA NOT RUN / NOT LOADED • Daily Picks remains healthy. PRA can only be run from the PRA page.")
    with st.expander("📋 PRA saved-output preview — display only", expanded=False):
        preview = _pra_preview_display(pra_feed.preview_rows(slate_day, limit=12))
        if preview.empty:
            st.info("No same-day PRA rows are currently loaded in this Streamlit session.")
        else:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        st.caption("Preview only • no Daily Picks ranking or qualification performed here.")

    st.markdown("### 🎯 Points Read-Only Connector")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Connection", "CONNECTED" if points.get("connected") else "NOT RUN")
    p2.metric("Points distributions", int(points.get("unique_distributions", 0)))
    p3.metric("Qualified rows", int(points.get("qualified", 0)))
    p4.metric("Final ready", int(points.get("final_ready", 0)))
    p5, p6, p7, p8 = st.columns(4)
    p5.metric("Monitor", int(points.get("monitor", 0)))
    p6.metric("Converged", f"{int(points.get('converged',0))}/{int(points.get('unique_distributions',0))}")
    p7.metric("Completed sims", f"{int(points.get('completed_sims',0)):,}")
    p8.metric("10M finalist rows", int(points.get("finalist_rows", 0)))
    st.caption(
        f"Points slate {points.get('day') or slate_day} • pass {points.get('source') or 'NONE'} • "
        f"persistence source {points.get('persistence_source') or 'NONE'} • "
        f"5M ran at {points.get('ran_at') or '—'} • 10M ran at {points.get('final_ran_at') or '—'}"
    )
    if points.get("connected"):
        st.success("✅ POINTS READ-ONLY CHECK PASSED • completed, converged same-day Points output is visible to Daily Picks.")
    else:
        st.info("⏳ POINTS NOT RUN / NOT LOADED • Daily Picks remains healthy. Points can only be run or restored from the Points page.")
    with st.expander("📋 Points saved-output preview — display only", expanded=False):
        preview = _points_preview_display(points_feed.preview_rows(slate_day, limit=12))
        if preview.empty:
            st.info("No same-day Points rows are currently loaded in this Streamlit session.")
        else:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        st.caption("Preview only • no Daily Picks ranking • no cross-market comparison • no new qualification performed here.")

    st.markdown("### 🏆 Top 5 WNBA Picks")
    st.info(
        "Step 3 intentionally keeps the Top 5 empty. PRA + Points visibility is being verified first. Rebounds connects next; standardization and ranking come later."
    )

    with st.expander("🛡️ Step-3 isolation diagnostics", expanded=False):
        st.write("• Connected production feeds: PRA read-only + Points read-only")
        st.write("• PRA production-module imports by Daily Picks: 0")
        st.write("• Points production-module imports by Daily Picks: 0")
        st.write("• Sportsbook requests launched by Daily Picks: 0")
        st.write("• Monte Carlo runs launched by Daily Picks: 0")
        st.write("• Restore/regrade calls launched by Daily Picks: 0")
        st.write("• PRA/Points session-state writes by Daily Picks: 0")
        st.write("• Rebounds reads: 0")
        st.write("• Top-5 ranking: OFF")

    st.caption(
        "⚡ WNBA Daily Picks V3 Step 3 • PRA + Points read-only state inspection • Rebounds paused • no ranking yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
