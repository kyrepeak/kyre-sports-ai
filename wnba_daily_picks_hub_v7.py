"""WNBA Daily Picks V7 — Step 7 duplicate/correlation protection.

Steps 1-6 remain unchanged. This view adds a read-only protection layer over the
Step-6 safety audit. It groups equivalent quotes and tags correlated exposure,
but does not rank, choose winners, simulate, refresh, regrade, or write back to
PRA, Points, Rebounds, or any other production model.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v6 as base
import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed
import wnba_daily_picks_standardizer_v1 as standardizer
import wnba_daily_picks_safety_v1 as safety
import wnba_daily_picks_protection_v1 as protection

MODEL_VERSION = "WNBA DAILY PICKS V7 • STEP 7 DUPLICATE/CORRELATION PROTECTION"
_ET = ZoneInfo("America/New_York")


def _protection_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Protection state", "Safety state", "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
        "Posted odds", "Model probability", "Candidate key", "Quote group size", "Alternate lines",
        "Player candidate groups", "Player markets", "Game candidate groups", "Team candidate groups",
        "Protection flags",
    ]
    d = frame[[c for c in keep if c in frame.columns]].copy()
    if "Model probability" in d.columns:
        vals = pd.to_numeric(d["Model probability"], errors="coerce")
        d["Model probability"] = vals.map(lambda x: f"{100*x:.1f}%" if pd.notna(x) else "—")
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
    protected = protection.annotate(audit)
    pdiag = protection.diagnostics(protected)

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
          <div class="ks-dp-kicker">KYRE SPORTS AI • WNBA DAILY PICKS • STEP 7</div>
          <div class="ks-dp-title">🏆 WNBA Daily Picks Command Center</div>
          <div class="ks-dp-sub">
            Steps 1–6 remain frozen. Step 7 identifies duplicate quotes, alternate-line relationships,
            same-player cross-market correlation, and same-game/team exposure before ranking is ever allowed.
            It does not choose a best quote or a best pick; Step 8 will handle ranking later.
          </div>
          <span class="ks-dp-chip">📅 ET slate {slate_day}</span>
          <span class="ks-dp-chip">🔌 3 read-only connectors</span>
          <span class="ks-dp-chip">🛡️ Step-6 safety preserved</span>
          <span class="ks-dp-chip">🧷 protection ACTIVE</span>
          <span class="ks-dp-chip">🚫 ranking still OFF</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.success(
        "✅ STEP 7 ACTIVE • equivalent quotes and correlated exposure are now grouped/tagged before future ranking. Source models remain untouched."
    )

    st.markdown("### 🧩 Market Feed Status")
    st.caption("PRA, Points and Rebounds remain independent production feeds. Daily Picks reads completed state only.")
    row1 = st.columns(4, gap="small")
    cards1 = [
        ("PRA", str(pra.get("state") or "⏳ NOT RUN"), base._feed_note(pra, "No same-day PRA payload loaded")),
        ("Points", str(points.get("state") or "⏳ NOT RUN"), base._feed_note(points, "No same-day Points payload loaded")),
        ("Rebounds", str(rebounds.get("state") or "⏳ NOT RUN"), base._feed_note(rebounds, "No same-day Rebounds payload loaded")),
        ("Assists", "NEXT", "Future independent feed"),
    ]
    for col, (label, state, note) in zip(row1, cards1):
        with col:
            st.markdown(base._ui._status_card(label, state, note), unsafe_allow_html=True)
    row2 = st.columns(3, gap="small")
    for col, item in zip(row2, [
        ("Spread", "NEXT", "Future independent feed"),
        ("Moneyline", "NEXT", "Future independent feed"),
        ("Game Total", "NEXT", "Future independent feed"),
    ]):
        with col:
            st.markdown(base._ui._status_card(*item), unsafe_allow_html=True)

    base.base._render_connector_panels(slate_day, pra, points, rebounds)

    st.markdown("### 🧬 Step 5 — Unified Daily Picks Data Contract")
    st.caption("Step 5 is frozen. Source outputs are translated into one common 22-field read-only schema.")
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
        st.info("⏳ STANDARDIZER READY • no same-day source payloads are loaded. Step 5 will populate automatically after a source model completes output.")
    else:
        st.success(f"✅ STEP-5 CONTRACT PASS • {len(common)} row(s) normalized. No ranking performed.")
        with st.expander("🧬 Unified source rows — read only", expanded=False):
            st.dataframe(base.base._common_display(common).head(150), use_container_width=True, hide_index=True)

    st.markdown("### 🛡️ Step 6 — Production Safety Gates")
    st.caption("Step 6 is frozen. Only SAFE rows can participate in Step-7 candidate grouping; HOLD/REJECT remain blocked.")
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
        st.info("⏳ SAFETY ENGINE ARMED • no standardized rows exist yet.")
    else:
        with st.expander("🛡️ Row-by-row safety audit — display only", expanded=False):
            st.dataframe(base._safety_display(audit).head(150), use_container_width=True, hide_index=True)

    st.markdown("### 🧷 Step 7 — Duplicate + Correlation Protection")
    st.caption(
        "Protection does not score or rank. It turns repeated sportsbook quotes into one candidate family and tags alternate-line, same-player, same-game and same-team exposure so Step 8 cannot count correlated rows as independent picks."
    )
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("SAFE source rows", int(pdiag.get("safe_rows", 0)))
    p2.metric("Candidate groups", int(pdiag.get("candidate_groups", 0)))
    p3.metric("Duplicate quote groups", int(pdiag.get("duplicate_quote_groups", 0)))
    p4.metric("Extra quote rows", int(pdiag.get("extra_quote_rows", 0)))
    p5, p6, p7, p8 = st.columns(4)
    p5.metric("Alternate-line groups", int(pdiag.get("alternate_line_groups", 0)))
    p6.metric("Player-correlation groups", int(pdiag.get("player_correlation_groups", 0)))
    p7.metric("Same-game groups", int(pdiag.get("game_exposure_groups", 0)))
    p8.metric("Ranking", "OFF")

    if protected.empty:
        st.info(
            "⏳ PROTECTION ENGINE ARMED • no Step-6 rows exist yet. Duplicate/correlation groups will appear automatically after source models produce same-day output."
        )
    else:
        safe_rows = int(pdiag.get("safe_rows", 0))
        candidate_groups = int(pdiag.get("candidate_groups", 0))
        blocked = int(pdiag.get("blocked_rows", 0))
        st.success(
            f"✅ STEP-7 PROTECTION PASS • {safe_rows} SAFE row(s) map to {candidate_groups} underlying candidate group(s); {blocked} Step-6 blocked row(s) remain excluded. No winner was selected."
        )
        with st.expander("🧷 Candidate-group / exposure audit — display only", expanded=True):
            st.dataframe(_protection_display(protected).head(200), use_container_width=True, hide_index=True)

    with st.expander("🧪 Step-7 protection methodology / diagnostics", expanded=False):
        st.write("• Same player + market + side + exact line across books = ONE candidate family")
        st.write("• Different lines for the same player/market/side are tagged as alternate-line correlation")
        st.write("• PRA / Points / Rebounds rows for the same player are tagged as cross-market player correlation")
        st.write("• Multiple candidate families from the same matchup are tagged as same-game exposure")
        st.write("• Multiple candidate families from the same team are tagged as same-team exposure")
        st.write("• HOLD/REJECT rows from Step 6 remain blocked and cannot be promoted by Step 7")
        st.write("• Step 7 does NOT choose the best sportsbook quote — that requires Step-8 ranking logic")
        st.write("• Simulations launched by Daily Picks: 0")
        st.write("• Sportsbook/network requests launched by Daily Picks: 0")
        st.write("• Production-model/session writes by Daily Picks: 0")
        st.write("• Cross-market ranking: OFF")

    st.markdown("### 🏆 Top 5 WNBA Picks")
    st.info(
        "Step 7 intentionally keeps the Top 5 empty. The page now knows what is safe, what is the same underlying wager, and what is correlated. Step 8 is where ranking begins."
    )
    st.caption("⚡ WNBA Daily Picks V7 Step 7 • Steps 1–6 preserved • duplicate/correlation protection ACTIVE • ranking OFF")


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
