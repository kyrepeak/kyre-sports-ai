"""WNBA Daily Picks V6 — Step 6 read-only production safety gates.

Steps 1-5 remain unchanged. This view consumes only the passive connector metadata
and the Step-5 standardized table, then classifies each already-loaded row SAFE,
HOLD or REJECT. It does not rank picks or control any production model.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v5 as base
import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed
import wnba_daily_picks_standardizer_v1 as standardizer
import wnba_daily_picks_safety_v1 as safety

MODEL_VERSION = "WNBA DAILY PICKS V6 • STEP 6 SAFETY GATES"
_ET = ZoneInfo("America/New_York")

# Step 5's connector renderer reaches the original Step-3 presentation helpers
# through its nested Step-4 UI module. Promote only those display helpers here so
# V6 remains cache/reboot safe without importing or modifying production models.
_ui = getattr(base, "ui", None)
_nested_ui = getattr(_ui, "ui", None) if _ui is not None else None
for _helper in ("_status_card", "_pra_preview_display", "_points_preview_display"):
    if _ui is not None and not hasattr(_ui, _helper) and _nested_ui is not None and hasattr(_nested_ui, _helper):
        setattr(_ui, _helper, getattr(_nested_ui, _helper))


def _feed_note(feed: dict, fallback: str) -> str:
    return base._feed_note(feed, fallback)


def _safety_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Safety state", "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
        "Posted odds", "Projection", "Model probability", "Simulation count", "Converged",
        "Qualification state", "Freshness", "Slate gate", "Identity gate", "Market gate",
        "Simulation gate", "Convergence gate", "Availability gate", "Game-state gate",
        "Freshness gate", "Hard failures", "Holds",
    ]
    d = frame[[c for c in keep if c in frame.columns]].copy()
    if "Model probability" in d.columns:
        vals = pd.to_numeric(d["Model probability"], errors="coerce")
        d["Model probability"] = vals.map(lambda x: f"{100*x:.1f}%" if pd.notna(x) else "—")
    if "Simulation count" in d.columns:
        vals = pd.to_numeric(d["Simulation count"], errors="coerce")
        d["Simulation count"] = vals.map(lambda x: f"{int(x):,}" if pd.notna(x) and x > 0 else "—")
    if "Converged" in d.columns:
        d["Converged"] = d["Converged"].map(lambda x: "✅" if bool(x) else "—")
    return d


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    pra = pra_feed.status(slate_day)
    points = points_feed.status(slate_day)
    rebounds = rebounds_feed.status(slate_day)
    common = standardizer.normalize_all(slate_day)
    diag = standardizer.diagnostics(slate_day)
    feeds = {"PRA": pra, "POINTS": points, "REBOUNDS": rebounds}
    audit = safety.evaluate(common, slate_day, feeds=feeds)
    sdiag = safety.diagnostics(audit)

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
          <div class="ks-dp-kicker">KYRE SPORTS AI • WNBA DAILY PICKS • STEP 6</div>
          <div class="ks-dp-title">🏆 WNBA Daily Picks Command Center</div>
          <div class="ks-dp-sub">
            PRA, Points and Rebounds remain independent. Step 6 adds a fail-safe, read-only production gate over the
            Step-5 common schema. Explicit stale/invalid/OUT/started evidence is rejected; uncertain evidence is held.
            No row is ranked yet, and no source model is changed or launched from this page.
          </div>
          <span class="ks-dp-chip">📅 ET slate {slate_day}</span>
          <span class="ks-dp-chip">🔌 3 read-only connectors</span>
          <span class="ks-dp-chip">🛡️ safety gates ACTIVE</span>
          <span class="ks-dp-chip">🚫 ranking still OFF</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.success(
        "✅ STEP 6 ACTIVE • standardized PRA + Points + Rebounds rows are now safety-audited before any future cross-market ranking."
    )

    st.markdown("### 🧩 Market Feed Status")
    st.caption(
        "The three production markets are still inspected independently. Daily Picks reads completed state only; it cannot run or modify a source model."
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
            st.markdown(_ui._status_card(label, state, note), unsafe_allow_html=True)

    row2 = st.columns(3, gap="small")
    for col, item in zip(row2, [
        ("Spread", "NEXT", "Future independent feed"),
        ("Moneyline", "NEXT", "Future independent feed"),
        ("Game Total", "NEXT", "Future independent feed"),
    ]):
        with col:
            st.markdown(_ui._status_card(*item), unsafe_allow_html=True)

    base._render_connector_panels(slate_day, pra, points, rebounds)

    st.markdown("### 🧬 Step 5 — Unified Daily Picks Data Contract")
    st.caption(
        "Step 5 remains frozen: source rows are copied into one common field layout, and missing values are never invented."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Common fields", int(diag.get("schema_columns", 0)))
    c2.metric("Standardized rows", int(diag.get("rows", 0)))
    c3.metric("Feeds with rows", f"{int(diag.get('feeds_with_rows',0))}/3")
    c4.metric("Required-field gaps", int(diag.get("missing_required_cells", 0)))
    counts = diag.get("market_counts", {}) or {}
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("PRA rows", int(counts.get("PRA", 0)))
    c6.metric("Points rows", int(counts.get("POINTS", 0)))
    c7.metric("Rebounds rows", int(counts.get("REBOUNDS", 0)))
    c8.metric("Ranking", "OFF")

    if common.empty:
        st.info(
            "⏳ STANDARDIZER READY • no same-day source payloads are loaded in this Streamlit session. Step 5 will populate automatically when a source model has completed output."
        )
    else:
        st.success(f"✅ STEP-5 CONTRACT PASS • {len(common)} row(s) normalized. Safety classification is shown below; ranking remains OFF.")
        with st.expander("🧬 Unified PRA + Points + Rebounds rows — read only", expanded=False):
            st.dataframe(base._common_display(common).head(100), use_container_width=True, hide_index=True)

    with st.expander("📐 Common schema definition", expanded=False):
        st.write(" • ".join(standardizer.COMMON_COLUMNS))

    st.markdown("### 🛡️ Step 6 — Production Safety Gates")
    st.caption(
        "Safety is classification only. SAFE means the row cleared all available Step-6 checks; HOLD means evidence is uncertain/incomplete; REJECT means an explicit hard gate failed."
    )
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Rows audited", int(sdiag.get("rows", 0)))
    g2.metric("SAFE", int(sdiag.get("safe", 0)))
    g3.metric("HOLD", int(sdiag.get("hold", 0)))
    g4.metric("REJECT", int(sdiag.get("reject", 0)))
    g5, g6, g7, g8 = st.columns(4)
    g5.metric("Quote max age", f"{int(safety.MAX_QUOTE_AGE_MIN)}m")
    g6.metric("Minimum sims", f"{int(safety.STANDARD_SIMS/1_000_000)}M")
    g7.metric("Model writes", "0")
    g8.metric("Ranking", "OFF")

    if audit.empty:
        st.info(
            "⏳ SAFETY ENGINE ARMED • there are no standardized rows to audit yet. Nothing is passed, held, rejected or ranked until a source model produces same-day output."
        )
    else:
        safe_n, hold_n, reject_n = int(sdiag.get("safe", 0)), int(sdiag.get("hold", 0)), int(sdiag.get("reject", 0))
        if reject_n:
            st.warning(
                f"🛡️ STEP-6 AUDIT • {safe_n} SAFE • {hold_n} HOLD • {reject_n} REJECT. Rejected rows are blocked from every later ranking step."
            )
        elif hold_n:
            st.info(
                f"🛡️ STEP-6 AUDIT • {safe_n} SAFE • {hold_n} HOLD • 0 REJECT. HOLD rows cannot enter ranking until their uncertainty clears."
            )
        else:
            st.success(f"✅ STEP-6 SAFETY PASS • all {safe_n} loaded row(s) cleared the current production gates.")
        with st.expander("🛡️ Row-by-row safety audit — display only", expanded=True):
            st.dataframe(_safety_display(audit).head(150), use_container_width=True, hide_index=True)

    with st.expander("🧪 Step-6 gate methodology / diagnostics", expanded=False):
        st.write("• Exact Eastern slate-date check")
        st.write("• Player / team / opponent identity completeness")
        st.write("• Exact side / line / book / posted odds / projection / probability completeness")
        st.write("• Standard 5M simulation proof, with passive connector metadata fallback")
        st.write("• Monte Carlo convergence proof")
        st.write("• Source qualification state preserved; OUT/INACTIVE/VOID-style states can only downgrade")
        st.write("• Existing same-session injury/availability evidence is inspected read-only when exposed")
        st.write("• Existing same-session schedule/game-state evidence blocks started/final games when exposed")
        st.write(f"• Explicit quote freshness older than {int(safety.MAX_QUOTE_AGE_MIN)} minutes is rejected")
        st.write("• Missing freshness/uncertain status becomes HOLD instead of being guessed")
        st.write("• Network/sportsbook requests launched by Daily Picks: 0")
        st.write("• Simulations launched by Daily Picks: 0")
        st.write("• Production session-state writes by Daily Picks: 0")
        st.write("• Cross-market ranking: OFF")

    st.markdown("### 🏆 Top 5 WNBA Picks")
    st.info(
        "Step 6 intentionally keeps the Top 5 empty. Safety gates are now installed. Step 7 adds duplicate/correlation protection; ranking does not begin until Step 8."
    )

    st.caption(
        "⚡ WNBA Daily Picks V6 Step 6 • Step-5 schema preserved • read-only safety gates ACTIVE • no ranking yet"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
