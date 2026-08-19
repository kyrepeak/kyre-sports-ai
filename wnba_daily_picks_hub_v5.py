"""WNBA Daily Picks V5 — Step 5 common-schema standardization.

Preserves the read-only PRA, Points and Rebounds connectors from Steps 1-4 and
adds one isolated adapter layer that maps already-completed payloads into a common
Daily Picks table. No cross-market ranking, qualification, model writes,
simulations, restores, sportsbook requests, or injury refreshes occur here.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v4 as ui
import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed
import wnba_daily_picks_standardizer_v1 as standardizer

MODEL_VERSION = "WNBA DAILY PICKS V5 • STEP 5 COMMON SCHEMA"
_ET = ZoneInfo("America/New_York")


def _feed_note(feed: dict, fallback: str) -> str:
    if feed.get("connected"):
        return (
            f"{feed.get('source','READ ONLY')} • "
            f"{feed.get('unique_distributions',0)} distributions • "
            f"{feed.get('qualified',0)} qualified"
        )
    return str(feed.get("detail") or fallback)


def _rebounds_preview_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    d = frame.copy()
    for c in ("Model decision probability", "No-vig edge", "Expected ROI"):
        if c in d.columns:
            vals = pd.to_numeric(d[c], errors="coerce")
            d[c] = vals.map(lambda x: f"{100*x:.1f}%" if pd.notna(x) else "—")
    if "MC simulations" in d.columns:
        vals = pd.to_numeric(d["MC simulations"], errors="coerce")
        d["MC simulations"] = vals.map(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
    return d


def _common_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=standardizer.COMMON_COLUMNS)
    d = frame.copy()
    for c in ("Model probability", "No-vig probability", "Edge"):
        if c in d.columns:
            vals = pd.to_numeric(d[c], errors="coerce")
            d[c] = vals.map(lambda x: f"{100*x:.1f}%" if pd.notna(x) else "—")
    if "EV / $100" in d.columns:
        vals = pd.to_numeric(d["EV / $100"], errors="coerce")
        d["EV / $100"] = vals.map(lambda x: f"{x:+.1f}" if pd.notna(x) else "—")
    if "Line" in d.columns:
        vals = pd.to_numeric(d["Line"], errors="coerce")
        d["Line"] = vals.map(lambda x: f"{x:g}" if pd.notna(x) else "—")
    if "Projection" in d.columns:
        vals = pd.to_numeric(d["Projection"], errors="coerce")
        d["Projection"] = vals.map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
    if "Simulation count" in d.columns:
        vals = pd.to_numeric(d["Simulation count"], errors="coerce")
        d["Simulation count"] = vals.map(lambda x: f"{int(x):,}" if pd.notna(x) and x > 0 else "—")
    for c in ("Posted odds", "Fair odds"):
        if c in d.columns:
            d[c] = d[c].map(
                lambda x: f"{int(x):+d}" if isinstance(x, (int, float)) and pd.notna(x)
                else (str(x) if pd.notna(x) else "—")
            )
    if "Converged" in d.columns:
        d["Converged"] = d["Converged"].map(lambda x: "✅" if bool(x) else "—")
    return d


def _render_connector_panels(slate_day: str, pra: dict, points: dict, rebounds: dict) -> None:
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
        st.info("⏳ PRA NOT RUN / NOT LOADED • Daily Picks remains healthy. PRA can only be produced from the PRA page.")
    with st.expander("📋 PRA saved-output preview — display only", expanded=False):
        preview = ui._pra_preview_display(pra_feed.preview_rows(slate_day, limit=12))
        if preview.empty:
            st.info("No same-day PRA rows are currently loaded in this Streamlit session.")
        else:
            st.dataframe(preview, use_container_width=True, hide_index=True)

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

    st.markdown("### 🏀 Rebounds Read-Only Connector")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric(
        "Connection",
        "CONNECTED" if rebounds.get("connected") else (
            "CHECK" if str(rebounds.get("state", "")).startswith("⚠") else "NOT RUN"
        ),
    )
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
        st.success("✅ REBOUNDS READ-ONLY CHECK PASSED • the completed same-day Rebounds production chain is visible to Daily Picks.")
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


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    pra = pra_feed.status(slate_day)
    points = points_feed.status(slate_day)
    rebounds = rebounds_feed.status(slate_day)
    common = standardizer.normalize_all(slate_day)
    diag = standardizer.diagnostics(slate_day)

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
          <div class="ks-dp-kicker">KYRE SPORTS AI • WNBA DAILY PICKS • STEP 5</div>
          <div class="ks-dp-title">🏆 WNBA Daily Picks Command Center</div>
          <div class="ks-dp-sub">
            PRA, Points and Rebounds remain independent production models. Step 5 adds a read-only translation layer
            that maps their already-completed outputs into one common Daily Picks schema. It does not regrade,
            rerank, rerun, restore, refresh or write back to any source model.
          </div>
          <span class="ks-dp-chip">📅 ET slate {slate_day}</span>
          <span class="ks-dp-chip">🔌 3 read-only connectors</span>
          <span class="ks-dp-chip">🧬 {len(standardizer.COMMON_COLUMNS)} common fields</span>
          <span class="ks-dp-chip">🚫 ranking still OFF</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.success(
        "✅ STEP 5 ACTIVE • PRA + Points + Rebounds now share one read-only Daily Picks data contract. Source-model math and state remain untouched."
    )

    st.markdown("### 🧩 Market Feed Status")
    st.caption(
        "The three source markets are still inspected independently. Standardization changes field names/units only; it does not qualify or rank picks."
    )
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

    _render_connector_panels(slate_day, pra, points, rebounds)

    st.markdown("### 🧬 Step 5 — Unified Daily Picks Data Contract")
    st.caption(
        "Every loaded PRA / Points / Rebounds row is copied into the same field layout. Missing source fields stay blank — Step 5 does not invent values."
    )
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Common fields", int(diag.get("schema_columns", 0)))
    s2.metric("Standardized rows", int(diag.get("rows", 0)))
    s3.metric("Feeds with rows", f"{int(diag.get('feeds_with_rows',0))}/3")
    s4.metric("Required-field gaps", int(diag.get("missing_required_cells", 0)))

    counts = diag.get("market_counts", {}) or {}
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("PRA rows", int(counts.get("PRA", 0)))
    q2.metric("Points rows", int(counts.get("POINTS", 0)))
    q3.metric("Rebounds rows", int(counts.get("REBOUNDS", 0)))
    q4.metric("Ranking", "OFF")

    if common.empty:
        st.info(
            "⏳ STANDARDIZER READY • no same-day production payloads are loaded after this reboot. The common schema is installed and will populate automatically when a source model has completed output in this session."
        )
    else:
        st.success(
            f"✅ STANDARDIZATION PASS • {len(common)} source row(s) were normalized into the {len(standardizer.COMMON_COLUMNS)}-field Daily Picks contract. No ranking was performed."
        )
        with st.expander("🧬 Unified PRA + Points + Rebounds rows — read only", expanded=True):
            st.dataframe(_common_display(common).head(100), use_container_width=True, hide_index=True)
            st.caption("Display only • no cross-market score • no best-price selection • no safety-gate rejection yet.")

    with st.expander("📐 Common schema definition", expanded=False):
        st.write(" • ".join(standardizer.COMMON_COLUMNS))
        st.caption(
            "Step 5 preserves source qualification states and probabilities. Blank fields mean the source payload did not explicitly provide that value; nothing is guessed."
        )

    st.markdown("### 🏆 Top 5 WNBA Picks")
    st.info(
        "Step 5 intentionally keeps the Top 5 empty. The three feeds now speak the same data format. Step 6 adds production safety gates; duplicate/correlation protection and ranking come later."
    )

    with st.expander("🛡️ Step-5 isolation diagnostics", expanded=False):
        st.write("• Production feeds: PRA read-only + Points read-only + Rebounds read-only")
        st.write("• New layer: common-schema adapter only")
        st.write("• Production-model imports by Daily Picks adapters: 0")
        st.write("• Simulations launched by Daily Picks: 0")
        st.write("• Sportsbook/network requests launched by Daily Picks: 0")
        st.write("• Snapshot restores/regrades launched by Daily Picks: 0")
        st.write("• Production session-state writes by Daily Picks: 0")
        st.write("• Cross-market Top-5 qualification/ranking: OFF")
        st.write("• PRA / Points / Rebounds production pages: unchanged")

    st.caption(
        "⚡ WNBA Daily Picks V5 Step 5 • common read-only schema • PRA + Points + Rebounds standardized • no ranking yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
