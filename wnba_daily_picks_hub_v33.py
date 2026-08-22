"""WNBA Daily Picks V33 — true source-market winners + diversified overall board.

V33 preserves V32 Step 11 finalization, all seven source models, all native
qualification rules, all Monte Carlo outputs, and the existing Daily Picks
safety/ranking/final guard. It changes presentation/aggregation only:

1) The market-best section reads source-qualified rows from the common schema,
   so a source-qualified pick can be shown even when Daily Picks later places it
   on HOLD/MONITOR.
2) The overall board admits at most the single best SAFE/RANKED candidate from
   each market before the existing Top-5 selection and final production guard.
   One market can no longer fill every overall slot.
3) No pick is forced. A market with zero source-qualified rows still displays
   NO QUALIFIED PICK.

The V1.1 common-schema repair supplies exact PRA/Points over_odds/fair_over fields,
preserves source qualification labels, and maps Rebounds Market no-vig probability.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v32 as v32
import wnba_daily_picks_selection_v1 as selection

MODEL_VERSION = "WNBA DAILY PICKS V33 • SOURCE MARKET WINNERS + DIVERSIFIED OVERALL TOP 5"
_ET = v32._ET


def _source_qualified_state(value: Any) -> bool:
    text = str(value or "").strip().upper()
    if not text or any(token in text for token in ("UNQUALIFIED", "NO EDGE", "AVOID", "REJECT")):
        return False
    if "FINAL READY" in text or "PRODUCTION READY" in text:
        return True
    return bool(re.search(r"(?:^|\s•\s)QUALIFIED(?:$|\s•\s)", text))


def _row_key(row: pd.Series) -> tuple:
    line = v32._num(row.get("Line"))
    line_key = round(float(line), 6) if np.isfinite(line) else None
    market = str(row.get("Market") or "").strip().upper()
    identity = str(row.get("Player") or row.get("Team") or "").strip().lower()
    return (
        market,
        identity,
        str(row.get("Team") or "").strip().lower(),
        str(row.get("Opponent") or "").strip().lower(),
        str(row.get("Side") or "").strip().upper(),
        line_key,
        str(row.get("Book") or "").strip().lower(),
    )


def _source_best(common: pd.DataFrame, market: str) -> pd.DataFrame:
    if common is None or common.empty or "Market" not in common.columns:
        return pd.DataFrame()
    d = common.loc[common["Market"].astype(str).str.upper().eq(market)].copy()
    if d.empty or "Qualification state" not in d.columns:
        return pd.DataFrame()
    d = d.loc[d["Qualification state"].map(_source_qualified_state)].copy()
    if d.empty:
        return d

    # Source modules already publish rows in their own native best-first order.
    # Keep that order; only collapse duplicate exact quotes defensively.
    keys = [c for c in ("Market", "Player", "Team", "Side", "Line", "Book") if c in d.columns]
    if keys:
        d = d.drop_duplicates(keys, keep="first")
    return d.head(1).copy()


def _market_winners(ranked: pd.DataFrame) -> pd.DataFrame:
    """One SAFE/RANKED winner per market, then preserve cross-market score order."""
    if ranked is None or ranked.empty or "Market" not in ranked.columns:
        return pd.DataFrame()
    d = ranked.copy()
    if "Rank state" in d.columns:
        d = d.loc[d["Rank state"].astype(str).str.upper().eq("RANKED")].copy()
    if "Safety state" in d.columns:
        d = d.loc[d["Safety state"].astype(str).str.upper().eq("SAFE")].copy()
    if d.empty:
        return d

    sort_cols = [c for c in (
        "Ranking score", "Model probability", "Edge ranked", "Edge", "EV / $100 ranked", "EV / $100"
    ) if c in d.columns]
    if sort_cols:
        d = d.sort_values(sort_cols, ascending=[False] * len(sort_cols), na_position="last", kind="mergesort")

    winners = d.drop_duplicates(subset=["Market"], keep="first").copy()
    if sort_cols:
        winners = winners.sort_values(sort_cols, ascending=[False] * len(sort_cols), na_position="last", kind="mergesort")
    winners["Rank"] = np.arange(1, len(winners) + 1)
    return winners.reset_index(drop=True)


def _visual_bundle(day: str):
    bundle = v32.seven.build_seven_market_selection(day)
    feeds = bundle.get("feeds", {}) if isinstance(bundle, dict) else {}
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()
    common = bundle.get("common") if isinstance(bundle, dict) else pd.DataFrame()
    audit = bundle.get("audit") if isinstance(bundle, dict) else pd.DataFrame()

    if not isinstance(ranked, pd.DataFrame):
        ranked = pd.DataFrame()
    if not isinstance(common, pd.DataFrame):
        common = pd.DataFrame()
    if not isinstance(audit, pd.DataFrame):
        audit = pd.DataFrame()

    winners = _market_winners(ranked)
    selected, skipped = selection.select_top5(winners)
    guarded = v32.seven.evaluate_seven_market(
        selected,
        day,
        feeds=feeds,
        now_et=datetime.now(_ET),
    )
    if not isinstance(guarded, pd.DataFrame):
        guarded = pd.DataFrame()
    ready = v32.seven.ready_rows(guarded)
    if not isinstance(ready, pd.DataFrame):
        ready = pd.DataFrame()
    return bundle, common, audit, ranked, winners, selected, skipped, guarded, ready


def _audit_state(audit: pd.DataFrame, row: pd.Series) -> str:
    if audit is None or audit.empty:
        return "SOURCE QUALIFIED"
    target = _row_key(row)
    for _, candidate in audit.iterrows():
        if _row_key(candidate) == target:
            state = str(candidate.get("Safety state") or "").strip().upper()
            if state:
                return f"SOURCE QUALIFIED • DAILY {state}"
    return "SOURCE QUALIFIED"


def _render_visual_board(day: str):
    feeds = v32._status_snapshot(day)
    connected = sum(int(bool(s.get("connected"))) for s in feeds.values())

    st.markdown("## 🏆 Daily Picks Visual Command Center")
    st.caption(
        "The first board mirrors the best source-qualified pick from each market page. "
        "The Overall board then allows at most one SAFE/RANKED winner per market through the existing final production guard. "
        "No source model, threshold, probability or simulation is changed."
    )

    if connected < 7:
        missing = [m.title() for m, s in feeds.items() if not s.get("connected")]
        st.info("Visual publishing is waiting for all seven source connectors: " + ", ".join(missing) + ".")
        return

    try:
        bundle, common, audit, ranked, winners, selected, skipped, guarded, ready = _visual_bundle(day)
    except Exception as exc:
        st.error(f"⛔ VISUAL BOARD CHECK • {type(exc).__name__}: {exc}")
        return

    ids = v32._player_id_index()
    source_markets = 0
    for market in v32._MARKET_ORDER:
        if not _source_best(common, market).empty:
            source_markets += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Connected markets", f"{connected}/7")
    c2.metric("Markets with qualified pick", f"{source_markets}/7")
    c3.metric("SAFE market winners", int(len(winners)))
    c4.metric("FINAL READY", f"{int(len(ready))}/5")

    st.markdown("### ⭐ Best Source-Qualified Pick From Each Market")
    st.caption(
        "QUALIFIED here means the pick passed that market page's own native qualification. "
        "A source-qualified card may still be DAILY HOLD/MONITOR and therefore stay out of the Overall board. Nothing is invented to fill a market."
    )
    st.markdown("""
    <style>
    .dp32-card{margin:12px 0;padding:17px;border:1px solid rgba(34,211,238,.28);border-radius:20px;background:linear-gradient(135deg,rgba(7,24,42,.98),rgba(8,34,50,.98));box-shadow:0 10px 24px rgba(0,0,0,.16)}
    .dp32-kicker{font-size:.72rem;font-weight:950;letter-spacing:.09em;color:#67e8f9;margin-bottom:9px}.dp32-main{display:flex;align-items:center;gap:13px}.dp32-photo{width:78px;height:78px;border-radius:50%;overflow:hidden;border:1px solid rgba(103,232,249,.32);display:flex;align-items:center;justify-content:center;background:rgba(15,23,42,.6)}.dp32-head{width:78px;height:78px;object-fit:cover;object-position:center top}.dp32-logohead{object-fit:contain;padding:9px;box-sizing:border-box}.dp32-sil{font-size:42px;color:#64748b}.dp32-who{flex:1}.dp32-name{font-size:1.2rem;font-weight:950;color:#f8fafc}.dp32-match{display:flex;align-items:center;gap:6px;color:#94a3b8;font-weight:750;margin:3px 0 8px}.dp32-logo{width:22px;height:22px;object-fit:contain}.dp32-pick{font-weight:950;color:#e2e8f0}.dp32-pick span{display:inline-block;margin-left:7px;border-radius:999px;padding:4px 8px;background:rgba(148,163,184,.12);color:#cbd5e1;font-size:.72rem}.dp32-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:13px}.dp32-grid div{padding:9px 6px;border:1px solid rgba(148,163,184,.12);border-radius:11px;text-align:center;background:rgba(15,23,42,.35)}.dp32-grid b{display:block;color:#f8fafc;font-size:.92rem}.dp32-grid span{display:block;color:#7f91aa;font-size:.62rem;margin-top:2px}@media(max-width:760px){.dp32-grid{grid-template-columns:repeat(3,1fr)}}
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(2)
    for idx, market in enumerate(v32._MARKET_ORDER):
        best = _source_best(common, market)
        with cols[idx % 2]:
            if best.empty:
                st.info(f"{v32._MARKET_ICONS[market]} {market.title()} • NO QUALIFIED PICK")
            else:
                row = best.iloc[0]
                st.markdown(v32._card(row, ids, _audit_state(audit, row)), unsafe_allow_html=True)

    st.markdown("### 🏁 Overall Daily Picks — One Market Winner Max + Final Production Guard")
    st.caption(
        "Each market contributes at most its single best SAFE/RANKED candidate before the existing Top-5 selection and final guard. "
        "If fewer than five market winners are FINAL READY, fewer than five are shown."
    )

    if ready.empty:
        st.info("No diversified cross-market selection is FINAL READY right now. The system will not force a Top 5.")
    else:
        d = ready.copy()
        rank_col = "Daily rank" if "Daily rank" in d.columns else ("Rank" if "Rank" in d.columns else None)
        if rank_col:
            d = d.sort_values(rank_col, ascending=True, na_position="last", kind="mergesort")
        for i, (_, row) in enumerate(d.head(5).iterrows(), start=1):
            st.markdown(
                v32._card(row, ids, "BEST OVERALL" if i == 1 else f"OVERALL #{i}"),
                unsafe_allow_html=True,
            )

    with st.expander("🔎 Cross-market aggregation audit"):
        market_rows = []
        for market in v32._MARKET_ORDER:
            src = _source_best(common, market)
            safe = winners.loc[winners["Market"].astype(str).str.upper().eq(market)] if not winners.empty else pd.DataFrame()
            final = ready.loc[ready["Market"].astype(str).str.upper().eq(market)] if not ready.empty else pd.DataFrame()
            market_rows.append({
                "Market": market,
                "Source qualified winner": "YES" if not src.empty else "NO",
                "SAFE/RANKED winner": "YES" if not safe.empty else "NO",
                "FINAL READY overall": "YES" if not final.empty else "NO",
            })
        st.dataframe(pd.DataFrame(market_rows), use_container_width=True, hide_index=True)
        if not skipped.empty:
            st.caption("Selection diversity/cap audit")
            st.dataframe(skipped, use_container_width=True, hide_index=True)
        if not guarded.empty:
            cols_show = [c for c in (
                "Daily rank", "Rank", "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
                "Model probability", "Edge", "Ranking score", "Guard state", "Guard reasons"
            ) if c in guarded.columns]
            st.caption("Final-guard audit")
            st.dataframe(guarded[cols_show], use_container_width=True, hide_index=True)


# V32 Step 11 resolves its visual renderer through the V32 module global at run
# time. Replace only that presentation/aggregation hook; Step 10/11 execution and
# every source/finalization function remain exactly V32.
v32._render_visual_board = _render_visual_board


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption(
        "🧩 Daily Picks V33 • source-schema repair + one qualified winner per market • "
        "existing safety/ranking/final guard preserved • source model math unchanged"
    )
    return v32.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
