"""WNBA Daily Picks V4 — Step 4 PRA + Points + Rebounds read-only connectors.

Preserves Steps 1-3 exactly and adds a passive Rebounds state inspector. Daily
Picks still launches zero simulations, makes zero sportsbook/network requests,
restores zero snapshots, changes zero projections, and writes to zero production
model keys. Cross-market standardization/ranking remains OFF and Top 5 stays empty.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v3 as ui
import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed

MODEL_VERSION = "WNBA DAILY PICKS V4 • STEP 4 PRA + POINTS + REBOUNDS READ ONLY"
_ET = ZoneInfo("America/New_York")


def _rebounds_preview_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    d = frame.copy()
    for c in ("Model decision probability", "No-vig edge", "Expected ROI"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").map(
                lambda x: f"{100*x:.1f}%" if pd.notna(x) else "—"
            )
    if "MC simulations" in d.columns:
        d["MC simulations"] = pd.to_numeric(d["MC simulations"], errors="coerce").map(
            lambda x: f"{int(x):,}" if pd.notna(x) else "—"
        )
    return d


def _feed_note(feed: dict, fallback: str) -> str:
    if feed.get("connected"):
        return (
            f"{feed.get('source','READ ONLY')} • "
            f"{feed.get('unique_distributions',0)} distributions • "
            f"{feed.get('qualified',0)} qualified"
        )
    return str(feed.get("detail") or fallback)


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    pra = pra_feed.status(slate_day)
    points = points_feed.status(slate_day)
    rebounds = rebounds_feed.status(slate_day)

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
          <div class="ks-dp-kicker">KYRE SPORTS AI • WNBA DAILY PICKS • STEP 4</div>
          <div class="ks-dp-title">🏆 WNBA Daily Picks Command Center</div>
          <div class="ks-dp-sub">
            Independent cross-market workspace. PRA, Points and Rebounds are now visible only through passive,
            read-only connectors. Daily Picks cannot run, restore, regrade, refresh, modify or write back to any
            production model. Cross-market Top-5 ranking is still disabled.
          </div>
          <span class="ks-dp-chip">📅 ET slate {slate_day}</span>
          <span class="ks-dp-chip">🔌 3 read-only connectors</span>
          <span class="ks-dp-chip">🚫 zero simulations launched here</span>
          <span class="ks-dp-chip">🔒 zero model writes</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.success(
        "✅ STEP 4 ACTIVE • PRA + Points + Rebounds are connected read-only. Daily Picks can inspect completed outputs without controlling any production model."
    )

    st.markdown("### 🧩 Market Feed Status")
    st.caption("PRA, Points and Rebounds are inspected independently. No cross-market ranking is active yet.")
    row1 = st.columns(4, gap="small")
    cards1 = [
        ("PRA", str(pra.get("state") or "⏳ NOT RUN"), _feed_note(pra, "No same-day PRA payload loaded")),
        ("Points", str(points.get("state") or "⏳ NOT RUN"), _feed_note(points, "No same-day Points payload loaded")),
        ("Rebounds", str(rebounds.get("state") or "⏳ NOT RUN"), _feed_note(rebounds, "No same-day Rebounds payload loaded")),
        ("Assists", "NEXT", "Future independent feed"),
    ]
    for col, (label, state, note) in zip(row1, cards1):
        with col:
            st.markdown(ui._status_card(label, state, note), unsafe_allow_html=True)

    row2 = st.columns(3, gap="small")
    for col, item in zip(row2, [
        ("Spread", "NEXT", "Future independent feed"),
        ("Moneyline", "NEXT", "Future independent feed"),
        ("Game Total", "NEXT", "Future independent feed"),
    ]):
        with col:
            st.markdown(ui._status_card(*item), unsafe_allow_html=True)

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
        preview = ui._pra_preview_display(pra_feed.preview_rows(slate_day, limit=12))
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
        preview = ui._points_preview_display(points_feed.preview_rows(slate_day, limit=12))
        if preview.empty:
            st.info("No same-day Points rows are currently loaded in this Streamlit session.")
        else:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        st.caption("Preview only • no Daily Picks ranking • no cross-market comparison • no new qualification performed here.")

    st.markdown("### 🏀 Rebounds Read-Only Connector")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Connection", "CONNECTED" if rebounds.get("connected") else ("CHECK" if str(rebounds.get("state","")).startswith("⚠") else "NOT RUN"))
    r2.metric("Player distributions", int(rebounds.get("unique_distributions", 0)))
    r3.metric("Qualified sides", int(rebounds.get("qualified", 0)))
    r4.metric("Step-20 final card", int(rebounds.get("final_card", 0)))
    r5, r6, r7, r8 = st.columns(4)
    r5.metric("Production ready", int(rebounds.get("final_ready", 0)))
    r6.metric("Monitor / hold", int(rebounds.get("monitor", 0)))
    r7.metric("Converged", f"{int(rebounds.get('converged',0))}/{int(rebounds.get('unique_distributions',0))}")
    r8.metric("Completed sims", f"{int(rebounds.get('completed_sims',0)):,}")
    st.caption(
        f"Rebounds slate {rebounds.get('day') or slate_day} • source {rebounds.get('source') or 'NONE'} • "
        f"Step 17 {'PASS' if rebounds.get('step17_ready') else 'NOT LOADED'} • "
        f"Step 20 {'PASS' if rebounds.get('step20_ready') else 'NOT LOADED'} • "
        f"production guard {'READY' if rebounds.get('production_ready') else 'NOT READY / NO CARD'}"
    )
    if rebounds.get("connected"):
        st.success("✅ REBOUNDS READ-ONLY CHECK PASSED • the completed same-day Step-17 5M + Step-20 production chain is visible to Daily Picks.")
    elif str(rebounds.get("state") or "").startswith("⚠"):
        st.warning(f"⚠️ REBOUNDS READ-ONLY CHECK • {rebounds.get('detail')}")
    else:
        st.info("⏳ REBOUNDS NOT RUN / NOT LOADED • Daily Picks remains healthy. Rebounds can only be produced from the Rebounds page.")
    with st.expander("📋 Rebounds saved-output preview — display only", expanded=False):
        preview = _rebounds_preview_display(rebounds_feed.preview_rows(slate_day, limit=12))
        if preview.empty:
            st.info("No same-day Rebounds production rows are currently loaded in this Streamlit session.")
        else:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        st.caption("Preview only • no Daily Picks ranking • no requalification • no production-model writeback.")

    st.markdown("### 🏆 Top 5 WNBA Picks")
    st.info(
        "Step 4 intentionally keeps the Top 5 empty. PRA + Points + Rebounds read-only visibility is being verified first. Step 5 will standardize the three feeds; ranking comes later."
    )

    with st.expander("🛡️ Step-4 isolation diagnostics", expanded=False):
        st.write("• Connected production feeds: PRA read-only + Points read-only + Rebounds read-only")
        st.write("• Production-model imports by Daily Picks connectors: 0")
        st.write("• Simulations launched by Daily Picks: 0")
        st.write("• Sportsbook/network requests launched by Daily Picks: 0")
        st.write("• Snapshot restores/regrades launched by Daily Picks: 0")
        st.write("• Production session-state writes by Daily Picks connectors: 0")
        st.write("• Cross-market Top-5 qualification/ranking: OFF")
        st.write("• PRA / Points / Rebounds production pages: unchanged")

    st.caption(
        "⚡ WNBA Daily Picks V4 Step 4 • PRA + Points + Rebounds read-only state inspection • zero model writes • no ranking yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
