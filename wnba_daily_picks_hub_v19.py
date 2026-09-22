"""WNBA Daily Picks V19 — Spread Step-8 read-only integration.

Renders the complete V18 production/verification chain, then appends a five-market
integration layer for PRA + Points + Rebounds + Assists + Spread. Spread is consumed
only from its completed same-session Step-7 payload. No source model is run or written.

Display-only repair: the legacy V9 Market Feed Status panel originally hard-coded
Assists and Spread as NEXT / Future independent feed. V19 now substitutes the
existing read-only Assists/Spread connector status during that legacy render so the
panel reports NOT RUN / CHECK / CONNECTED truthfully. No source-model, simulation,
ranking, safety, guard or persistence behavior is changed.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v18 as v18
import wnba_daily_picks_hub_v9 as legacy_v9
import wnba_daily_picks_selection_v3 as selection_v3
import wnba_daily_picks_guard_v3 as guard_v3
import wnba_daily_picks_assists_connector_v1 as assists_feed
import wnba_daily_picks_spread_connector_v1 as spread_feed

MODEL_VERSION = "WNBA DAILY PICKS V19 • SPREAD STEP-8 FIVE-MARKET INTEGRATION"
_ET = ZoneInfo("America/New_York")
_MARKETS=("PRA","POINTS","REBOUNDS","ASSISTS","SPREAD")


def _count(frame: pd.DataFrame, market: str) -> int:
    if frame is None or not isinstance(frame,pd.DataFrame) or frame.empty or "Market" not in frame.columns: return 0
    return int(frame["Market"].astype(str).str.upper().eq(market).sum())


def _render_v18_with_live_feed_tiles(section_header=None,status_info=None,team_logo=None,h=None):
    """Render frozen V18 while repairing only stale legacy status-card text."""
    now=datetime.now(_ET)
    day=now.strftime("%Y-%m-%d")
    assists=assists_feed.status(day)
    spread=spread_feed.status(day)

    ui=legacy_v9.prev.base._ui
    original_card=ui._status_card
    original_caption=st.caption
    original_markdown=st.markdown

    def live_status_card(label, state, note):
        key=str(label or "").strip().upper()
        if key=="ASSISTS":
            return original_card(
                label,
                str(assists.get("state") or ("✅ CONNECTED" if assists.get("connected") else "⏳ NOT RUN")),
                str(assists.get("detail") or "No completed same-day Assists Step-20 production payload is present in this session."),
            )
        if key=="SPREAD":
            return original_card(
                label,
                str(spread.get("state") or ("✅ CONNECTED" if spread.get("connected") else "⏳ NOT RUN")),
                str(spread.get("detail") or "No completed same-day Spread Step-7 payload is present in this session."),
            )
        return original_card(label,state,note)

    def live_caption(body,*args,**kwargs):
        text=str(body)
        if text=="PRA, Points and Rebounds remain independent read-only feeds. Assists and game markets remain future connectors.":
            body="PRA, Points, Rebounds, Assists and Spread are independent read-only feeds. Moneyline and Game Total remain future connectors."
        return original_caption(body,*args,**kwargs)

    def live_markdown(body,*args,**kwargs):
        if isinstance(body,str) and "KYRE SPORTS AI • WNBA DAILY PICKS • STEP 9" in body:
            body=body.replace("🔌 3 read-only connectors","🔌 5 read-only connectors")
        return original_markdown(body,*args,**kwargs)

    ui._status_card=live_status_card
    st.caption=live_caption
    st.markdown=live_markdown
    try:
        return v18.render_wnba_daily_picks_hub(
            section_header=section_header,
            status_info=status_info,
            team_logo=team_logo,
            h=h,
        )
    finally:
        ui._status_card=original_card
        st.caption=original_caption
        st.markdown=original_markdown


def render_wnba_daily_picks_hub(section_header=None,status_info=None,team_logo=None,h=None):
    _render_v18_with_live_feed_tiles(section_header=section_header,status_info=status_info,team_logo=team_logo,h=h)

    now=datetime.now(_ET); day=now.strftime("%Y-%m-%d")
    bundle=selection_v3.build_five_market_selection(day)
    feeds=bundle.get("feeds",{}) if isinstance(bundle,dict) else {}
    common=bundle.get("common") if isinstance(bundle,dict) else pd.DataFrame()
    audit=bundle.get("audit") if isinstance(bundle,dict) else pd.DataFrame()
    ranked=bundle.get("ranked") if isinstance(bundle,dict) else pd.DataFrame()
    selected=bundle.get("selected") if isinstance(bundle,dict) else pd.DataFrame()
    for name,val in (("common",common),("audit",audit),("ranked",ranked),("selected",selected)):
        if not isinstance(val,pd.DataFrame):
            if name=="common": common=pd.DataFrame()
            elif name=="audit": audit=pd.DataFrame()
            elif name=="ranked": ranked=pd.DataFrame()
            else: selected=pd.DataFrame()

    guarded=guard_v3.evaluate_five_market(selected,day,feeds=feeds,now_et=now)
    ready=guard_v3.ready_rows(guarded)
    gdiag=guard_v3.diagnostics(guarded,selected)
    spread=spread_feed.status(day)
    spread_common=_count(common,"SPREAD")
    spread_safe=_count(audit.loc[audit.get("Safety state",pd.Series("",index=audit.index)).astype(str).str.upper().eq("SAFE")].copy() if not audit.empty else pd.DataFrame(),"SPREAD")
    spread_ranked=_count(ranked.loc[ranked.get("Rank state",pd.Series("",index=ranked.index)).astype(str).str.upper().eq("RANKED")].copy() if not ranked.empty else pd.DataFrame(),"SPREAD")
    spread_selected=_count(selected,"SPREAD")
    spread_ready=_count(ready,"SPREAD")

    connected={m:bool((feeds.get(m,{}) or {}).get("connected")) for m in _MARKETS}
    connected_n=sum(int(v) for v in connected.values())
    all5=connected_n==5
    coverage=bool(gdiag.get("coverage_pass"))
    top5_ok=len(selected)<=5
    pipeline=bool(coverage and top5_ok)

    st.markdown("---")
    st.markdown("## 🏀 Step 8 — Spread → Daily Picks Integration")
    st.caption("Read-only connector → common schema → safety → cross-market protection/ranking → Top-5 selection → final production guard. No new simulations, network requests, source writes or forced picks.")

    a1,a2,a3,a4=st.columns(4)
    a1.metric("Spread connector","CONNECTED" if spread.get("connected") else "CHECK")
    a2.metric("Spread source picks",int(spread.get("production_picks") or 0))
    a3.metric("Spread common rows",spread_common)
    a4.metric("Spread SAFE",spread_safe)

    b1,b2,b3,b4=st.columns(4)
    b1.metric("Spread RANKED",spread_ranked)
    b2.metric("Spread SELECTED",spread_selected)
    b3.metric("Spread FINAL READY",spread_ready)
    b4.metric("Five-market feeds",f"{connected_n}/5")

    connector_pass=bool(spread.get("connected") and spread_common==int(spread.get("production_picks") or 0) and spread_safe==spread_common and spread_ranked==spread_common)
    if connector_pass:
        st.success("✅ SPREAD CONNECTOR STEP 8 PASSED • completed Spread Step-7 output is entering Daily Picks read-only and reconciles through schema, safety and ranking with no source-model changes.")
    elif spread.get("connected") and int(spread.get("production_picks") or 0)==0:
        st.success("✅ SPREAD CONNECTOR STEP 8 PASSED • Spread is connected with 0 qualified production picks; Daily Picks correctly adds no forced Spread row.")
    else:
        st.warning("⚠️ SPREAD CONNECTOR CHECK • the same-day Spread Step-7 source is missing or a row failed schema/safety/ranking reconciliation.")

    if not selected.empty:
        show=selected.copy()
        show["Candidate"]=show.apply(lambda r: f"{r.get('Team')} {float(r.get('Line')):+g}" if str(r.get("Market")).upper()=="SPREAD" and pd.notna(pd.to_numeric(pd.Series([r.get('Line')]),errors='coerce').iloc[0]) else f"{r.get('Player')} {r.get('Side')} {r.get('Line')}",axis=1)
        cols=[c for c in ("Daily rank","Market","Candidate","Book","Posted odds","Model probability","Edge","Ranking score") if c in show.columns]
        st.markdown("### 🏆 Five-Market Overall Top 5 — pre-guard")
        st.dataframe(show[cols],use_container_width=True,hide_index=True)

    st.markdown("### 🛡️ Five-Market Final Production Guard")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Selected",len(selected))
    c2.metric("READY",int(gdiag.get("ready",0)))
    c3.metric("MONITOR",int(gdiag.get("monitor",0)))
    c4.metric("BLOCKED",int(gdiag.get("blocked",0)))
    if isinstance(guarded,pd.DataFrame) and not guarded.empty:
        g=guarded.copy()
        cols=[c for c in ("Daily rank","Market","Player","Team","Side","Line","Book","Guard state","Guard reasons") if c in g.columns]
        st.dataframe(g[cols],use_container_width=True,hide_index=True)

    d1,d2,d3=st.columns(3)
    d1.metric("Five-market pipeline","PASS" if pipeline else "CHECK")
    d2.metric("All feeds connected",f"{connected_n}/5")
    d3.metric("Final READY",f"{len(ready)}/5")

    if all5 and pipeline:
        st.success("✅ FIVE-MARKET END-TO-END PASS • PRA + Points + Rebounds + Assists + Spread reconcile through one guarded Daily Picks Top-5 pipeline.")
    elif pipeline:
        missing=[m.title() for m in _MARKETS if not connected[m]]
        st.info("ℹ️ Spread Step 8 is live. Full five-market end-to-end verification is waiting on: "+", ".join(missing)+".")
    else:
        st.warning("⚠️ FIVE-MARKET PIPELINE CHECK • inspect the guard table before changing any source model. No backfill is performed.")

    st.caption(f"⚡ Daily Picks V19 • live Assists/Spread feed tiles • Spread Step 8 read-only • checked {now.strftime('%Y-%m-%d %I:%M:%S %p ET')} • new simulations 0 • network requests 0 • source writes 0")


__all__=["MODEL_VERSION","render_wnba_daily_picks_hub"]
