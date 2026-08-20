"""WNBA Daily Picks V15 — Assists Connector Step 5 cross-market ranking.

Preserves the complete Daily Picks V14 page (existing Steps 1–10 + Assists
Connector Steps 1–4) and appends only a four-market ranking verification panel.

SAFE protected Assists candidate families may now enter the same existing ranking
engine as PRA, Points and Rebounds. This remains a ranking preview only: final
Top-5 selection is still OFF for Assists until Connector Step 6, and the final
production guard remains OFF until Step 7.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v14 as v14
import wnba_daily_picks_ranking_v2 as ranking_v2

MODEL_VERSION = "WNBA DAILY PICKS V15 • ASSISTS CONNECTOR STEP 5 CROSS-MARKET RANKING"
_ET = ZoneInfo("America/New_York")


def _pct(value) -> str:
    try:
        x = float(value)
        return f"{100.0*x:.1f}%"
    except Exception:
        return "—"


def _ranking_view(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Rank", "Rank state", "Ranking score", "Market", "Player", "Team", "Opponent",
        "Side", "Line", "Book", "Posted odds", "Projection", "Projection edge",
        "Model probability", "No-vig ranked", "Edge ranked", "EV / $100 ranked",
        "Exposure penalty", "Qualification state", "Freshness", "Quote selection",
        "Protection flags",
    ]
    out = frame[[c for c in keep if c in frame.columns]].copy()
    for col in ("Model probability", "No-vig ranked", "Edge ranked"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(
                lambda x: "—" if pd.isna(x) else f"{100.0*x:.1f}%"
            )
    for col in ("Ranking score", "Projection edge", "EV / $100 ranked", "Exposure penalty"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").map(
                lambda x: "—" if pd.isna(x) else f"{x:.2f}"
            )
    if "Posted odds" in out.columns:
        out["Posted odds"] = pd.to_numeric(out["Posted odds"], errors="coerce").map(
            lambda x: "—" if pd.isna(x) else f"{int(x):+d}"
        )
    return out


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Freeze all prior Daily Picks + Assists Connector work first.
    v14.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )

    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    bundle = ranking_v2.build_four_market_ranking(slate_day)
    ranked = bundle.get("ranked", pd.DataFrame())
    diag = ranking_v2.diagnostics(bundle)
    counts = dict(diag.get("market_counts") or {})
    ranked_counts = dict(diag.get("ranked_counts") or {})

    st.markdown("---")
    st.markdown("## 🏁 Assists Connector — Step 5: Cross-Market Ranking")
    st.caption(
        "Ranking integration only. SAFE protected Assists candidate families can now compete in the same existing Daily Picks score as PRA, Points and Rebounds. Exact duplicate quotes collapse to one best quote before scoring. Final Top-5 publishing is still OFF until Connector Step 6."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Common rows", int(diag.get("common_rows", 0)))
    c2.metric("SAFE rows", int(diag.get("safe_rows", 0)))
    c3.metric("Candidate families", int(diag.get("candidate_groups", 0)))
    c4.metric("Ranked", int(diag.get("ranked", 0)))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("PRA ranked", int(ranked_counts.get("PRA", 0)))
    d2.metric("Points ranked", int(ranked_counts.get("POINTS", 0)))
    d3.metric("Rebounds ranked", int(ranked_counts.get("REBOUNDS", 0)))
    d4.metric("Assists ranked", int(ranked_counts.get("ASSISTS", 0)))

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Markets represented", int(diag.get("markets_represented", 0)))
    e2.metric("Score holds", int(diag.get("score_holds", 0)))
    e3.metric("Assists ranking coverage", "PASS" if diag.get("assists_coverage") else "CHECK")
    e4.metric("Top 5 publishing", "OFF")

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("New simulations", "0")
    f2.metric("Network requests", "0")
    f3.metric("Production writes", "0")
    f4.metric("Final guard", "OFF")

    coverage = bool(diag.get("assists_coverage"))
    if coverage:
        assists_input = int(diag.get("assists_input", 0))
        assists_rank_rows = int(diag.get("assists_rank_rows", 0))
        assists_ranked = int(diag.get("assists_ranked", 0))
        if assists_input == 0:
            st.success(
                "✅ ASSISTS CONNECTOR STEP 5 PASSED • the Assists source is connected with a valid 0/5 result, so it contributes zero ranking candidates and nothing is forced."
            )
        else:
            st.success(
                f"✅ ASSISTS CONNECTOR STEP 5 PASSED • all {assists_input} standardized Assists row(s) reached the four-market ranking pipeline: {assists_ranked} RANKED and {max(0, assists_rank_rows-assists_ranked)} SCORE HOLD. Top-5 publishing remains OFF."
            )
    else:
        st.warning(
            "⚠️ ASSISTS CONNECTOR STEP 5 CHECK • Assists source rows did not fully reconcile into the ranking output. Final Top-5 publishing remains disabled for Assists."
        )

    st.caption(
        "Loaded common-schema rows • "
        f"PRA {int(counts.get('PRA',0))} • Points {int(counts.get('POINTS',0))} • "
        f"Rebounds {int(counts.get('REBOUNDS',0))} • Assists {int(counts.get('ASSISTS',0))}. "
        "A market with 0 simply has no same-session production output loaded."
    )

    with st.expander("🏁 Four-market ranking audit — NOT final Top 5", expanded=False):
        view = _ranking_view(ranked)
        if view.empty:
            st.info("No SAFE candidate family is currently rankable.")
        else:
            st.dataframe(view.head(150), use_container_width=True, hide_index=True)
        st.caption("Read-only ranking preview • one best quote per candidate family • no Top-5 publication • no production writeback.")

    with st.expander("🧬 Assists Connector Step-5 ranking diagnostics", expanded=False):
        st.write("• Same frozen Daily Picks Ranking V1 scoring formula is used for all four player-prop markets")
        st.write("• Only Step-3 SAFE rows may reach ranking")
        st.write("• Combined protection is recomputed read-only so cross-market same-player/game/team exposure is visible")
        st.write("• Exact same wager across books collapses to one candidate family before scoring")
        st.write("• Score inputs: model probability + no-vig edge + EV + projection cushion + freshness + source quality")
        st.write("• Exposure penalty remains bounded by the existing Daily Picks ranking contract")
        st.write("• Missing ranking evidence becomes SCORE HOLD; values are not invented")
        st.write("• PRA/Points/Rebounds behavior is not modified; Assists is appended to the same read-only pipeline")
        st.write("• New simulations: 0")
        st.write("• Network/sportsbook/injury requests: 0")
        st.write("• Source-model / Daily Picks production writes: 0")
        st.write("• Final Top 5: OFF until Connector Step 6")
        st.write("• Final production-ready guard: OFF until Connector Step 7")

    st.info(
        "➡️ NEXT: Assists Connector Step 6 will allow this four-market ranked board to enter the existing Daily Picks Top-5 selection layer. It will still never force five, and Step 7 will remain the final production-ready guard."
    )
    st.caption(
        "⚡ WNBA Daily Picks V15 • Assists Connector Step 5 • four-market ranking ACTIVE • Top 5 OFF • existing Daily Picks Steps 1–10 preserved"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
