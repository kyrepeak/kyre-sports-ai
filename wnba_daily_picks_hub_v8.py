"""WNBA Daily Picks V8 — Step 8 cross-market ranking preview.

Steps 1-7 remain frozen. Step 8 ranks only Step-6 SAFE candidate families after
Step-7 duplicate/correlation protection. It may select the best existing quote
inside an exact candidate family, but it does not launch simulations, refresh
markets/injuries, modify source models, or publish the visual Top 5. Step 9 owns
final visual card presentation.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v7 as prev
import wnba_daily_picks_pra_connector_v1 as pra_feed
import wnba_daily_picks_points_connector_v1 as points_feed
import wnba_daily_picks_rebounds_connector_v1 as rebounds_feed
import wnba_daily_picks_standardizer_v1 as standardizer
import wnba_daily_picks_safety_v1 as safety
import wnba_daily_picks_protection_v1 as protection
import wnba_daily_picks_ranking_v1 as ranking

MODEL_VERSION = "WNBA DAILY PICKS V8 • STEP 8 CROSS-MARKET RANKING"
_ET = ZoneInfo("America/New_York")


def _ranking_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Rank", "Rank state", "Ranking score", "Market", "Player", "Team", "Opponent",
        "Side", "Line", "Book", "Posted odds", "Projection", "Projection edge",
        "Model probability", "No-vig ranked", "Edge ranked", "EV / $100 ranked",
        "Exposure penalty", "Qualification state", "Freshness", "Quote selection",
        "Protection flags",
    ]
    d = frame[[c for c in keep if c in frame.columns]].copy()
    for col in ("Model probability", "No-vig ranked", "Edge ranked"):
        if col in d.columns:
            vals = pd.to_numeric(d[col], errors="coerce")
            d[col] = vals.map(lambda x: f"{100*x:.1f}%" if pd.notna(x) else "—")
    for col in ("Ranking score", "Projection edge", "EV / $100 ranked", "Exposure penalty"):
        if col in d.columns:
            vals = pd.to_numeric(d[col], errors="coerce")
            d[col] = vals.map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
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
    ranked = ranking.rank_candidates(protected)
    rdiag = ranking.diagnostics(ranked)

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
          <div class="ks-dp-kicker">KYRE SPORTS AI • WNBA DAILY PICKS • STEP 8</div>
          <div class="ks-dp-title">🏆 WNBA Daily Picks Command Center</div>
          <div class="ks-dp-sub">
            Steps 1–7 remain frozen. Step 8 activates the first cross-market ranking layer over SAFE,
            de-duplicated PRA / Points / Rebounds candidate families. The ranking is an audit preview only;
            Step 9 will turn eligible leaders into the visual Top-5 cards.
          </div>
          <span class="ks-dp-chip">📅 ET slate {slate_day}</span>
          <span class="ks-dp-chip">🔌 3 read-only connectors</span>
          <span class="ks-dp-chip">🛡️ safety preserved</span>
          <span class="ks-dp-chip">🧷 protection preserved</span>
          <span class="ks-dp-chip">🏁 ranking ACTIVE</span>
          <span class="ks-dp-chip">🚫 Top 5 publishing OFF</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.success(
        "✅ STEP 8 ACTIVE • SAFE candidate families can now be compared across PRA + Points + Rebounds. No source model is controlled by Daily Picks."
    )

    st.markdown("### 🧩 Market Feed Status")
    st.caption("The three production markets remain independent. Daily Picks only reads already-completed same-day outputs.")
    row1 = st.columns(4, gap="small")
    cards1 = [
        ("PRA", str(pra.get("state") or "⏳ NOT RUN"), prev.base._feed_note(pra, "No same-day PRA payload loaded")),
        ("Points", str(points.get("state") or "⏳ NOT RUN"), prev.base._feed_note(points, "No same-day Points payload loaded")),
        ("Rebounds", str(rebounds.get("state") or "⏳ NOT RUN"), prev.base._feed_note(rebounds, "No same-day Rebounds payload loaded")),
        ("Assists", "NEXT", "Future independent feed"),
    ]
    for col, (label, state, note) in zip(row1, cards1):
        with col:
            st.markdown(prev.base._ui._status_card(label, state, note), unsafe_allow_html=True)
    row2 = st.columns(3, gap="small")
    for col, item in zip(row2, [
        ("Spread", "NEXT", "Future independent feed"),
        ("Moneyline", "NEXT", "Future independent feed"),
        ("Game Total", "NEXT", "Future independent feed"),
    ]):
        with col:
            st.markdown(prev.base._ui._status_card(*item), unsafe_allow_html=True)

    prev.base.base._render_connector_panels(slate_day, pra, points, rebounds)

    st.markdown("### 🧬 Step 5 — Unified Daily Picks Data Contract")
    st.caption("Frozen. PRA / Points / Rebounds outputs share the same 22-field read-only contract.")
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
    c8.metric("Model writes", "0")
    if common.empty:
        st.info("⏳ STANDARDIZER READY • no same-day source payloads are loaded.")
    else:
        st.success(f"✅ STEP-5 CONTRACT PASS • {len(common)} row(s) normalized.")
        with st.expander("🧬 Unified source rows — read only", expanded=False):
            st.dataframe(prev.base.base._common_display(common).head(150), use_container_width=True, hide_index=True)

    st.markdown("### 🛡️ Step 6 — Production Safety Gates")
    st.caption("Frozen. Only SAFE rows can move forward; HOLD / REJECT remain blocked.")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Rows audited", int(sdiag.get("rows", 0)))
    g2.metric("SAFE", int(sdiag.get("safe", 0)))
    g3.metric("HOLD", int(sdiag.get("hold", 0)))
    g4.metric("REJECT", int(sdiag.get("reject", 0)))
    g5, g6, g7, g8 = st.columns(4)
    g5.metric("Quote max age", f"{int(safety.MAX_QUOTE_AGE_MIN)}m")
    g6.metric("Minimum sims", f"{int(safety.STANDARD_SIMS/1_000_000)}M")
    g7.metric("Model writes", "0")
    g8.metric("Safety", "ACTIVE")
    if audit.empty:
        st.info("⏳ SAFETY ENGINE ARMED • no standardized rows exist yet.")
    else:
        with st.expander("🛡️ Row-by-row safety audit — display only", expanded=False):
            st.dataframe(prev.base._safety_display(audit).head(150), use_container_width=True, hide_index=True)

    st.markdown("### 🧷 Step 7 — Duplicate + Correlation Protection")
    st.caption("Frozen. Equivalent sportsbook quotes are one candidate family; alternate-line / player / game / team exposure remains tagged.")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("SAFE source rows", int(pdiag.get("safe_rows", 0)))
    p2.metric("Candidate groups", int(pdiag.get("candidate_groups", 0)))
    p3.metric("Duplicate quote groups", int(pdiag.get("duplicate_quote_groups", 0)))
    p4.metric("Extra quote rows", int(pdiag.get("extra_quote_rows", 0)))
    p5, p6, p7, p8 = st.columns(4)
    p5.metric("Alternate-line groups", int(pdiag.get("alternate_line_groups", 0)))
    p6.metric("Player-correlation groups", int(pdiag.get("player_correlation_groups", 0)))
    p7.metric("Same-game groups", int(pdiag.get("game_exposure_groups", 0)))
    p8.metric("Protection", "ACTIVE")
    if protected.empty:
        st.info("⏳ PROTECTION ENGINE ARMED • no Step-6 rows exist yet.")
    else:
        with st.expander("🧷 Candidate-group / exposure audit — display only", expanded=False):
            st.dataframe(prev._protection_display(protected).head(200), use_container_width=True, hide_index=True)

    st.markdown("### 🏁 Step 8 — Cross-Market Ranking Preview")
    st.caption(
        "Ranking compares one best existing quote per SAFE candidate family. Score = model probability + no-vig edge + EV + projection cushion + freshness + source quality, minus a bounded Step-7 exposure penalty. This is not the visual Top 5 yet."
    )
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Candidate families", int(rdiag.get("candidate_groups", 0)))
    r2.metric("Ranked", int(rdiag.get("ranked", 0)))
    r3.metric("Score holds", int(rdiag.get("score_holds", 0)))
    r4.metric("Markets represented", int(rdiag.get("markets", 0)))
    r5, r6, r7, r8 = st.columns(4)
    r5.metric("Best quotes selected", int(rdiag.get("quotes_selected", 0)))
    r6.metric("Ranking", "ACTIVE")
    r7.metric("New simulations", "0")
    r8.metric("Top 5 publishing", "OFF")

    if ranked.empty:
        st.info(
            "⏳ RANKING ENGINE ARMED • no SAFE candidate families exist yet. Ranking will populate automatically after a source model produces same-day output that clears Steps 5–7."
        )
    else:
        n_ranked = int(rdiag.get("ranked", 0))
        n_hold = int(rdiag.get("score_holds", 0))
        if n_ranked:
            st.success(
                f"✅ STEP-8 RANKING PASS • {n_ranked} candidate family/families ranked; {n_hold} score hold(s). Exact duplicate quotes were collapsed before scoring."
            )
        else:
            st.warning(
                f"⚠️ STEP-8 SCORE HOLD • candidate families exist, but none has enough verified ranking inputs yet. Holds: {n_hold}."
            )
        with st.expander("🏁 Cross-market ranking audit — NOT final cards", expanded=True):
            st.dataframe(_ranking_display(ranked).head(100), use_container_width=True, hide_index=True)

    with st.expander("🧪 Step-8 ranking methodology / diagnostics", expanded=False):
        st.write("• Only Step-6 SAFE rows can rank")
        st.write("• Exact same player + market + side + line across books collapses to one candidate family")
        st.write("• Best existing quote is chosen by EV, then posted American price")
        st.write("• Model probability contributes up to 40 ranking points")
        st.write("• No-vig edge contributes up to 25 ranking points")
        st.write("• Expected value contributes up to 15 ranking points")
        st.write("• Projection cushion contributes up to 10 ranking points")
        st.write("• Freshness and source quality contribute the final 10 ranking points")
        st.write("• Step-7 alternate-line / same-player / same-game / same-team exposure can subtract at most 8 points")
        st.write("• Missing no-vig / edge evidence creates SCORE HOLD rather than a guessed ranking")
        st.write("• If source EV is absent, EV may be calculated mathematically from model probability + the already-posted price")
        st.write("• Simulations launched by Daily Picks: 0")
        st.write("• Sportsbook/network requests launched by Daily Picks: 0")
        st.write("• Production-model/session writes by Daily Picks: 0")
        st.write("• Final visual Top-5 publishing: OFF until Step 9")

    st.markdown("### 🏆 Top 5 WNBA Picks")
    st.info(
        "Step 8 ranks eligible candidate families but intentionally does NOT publish the Top 5 cards yet. Step 9 will apply the presentation/selection layer to this ranking output."
    )
    st.caption("⚡ WNBA Daily Picks V8 Step 8 • Steps 1–7 preserved • cross-market ranking ACTIVE • visual Top 5 OFF")


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
