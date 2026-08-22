"""WNBA Daily Picks V20 — Moneyline Step-9 six-market read-only integration.

Renders the frozen V18 Daily Picks production/verification surface, then appends
PRA + Points + Rebounds + Assists + Spread + Moneyline integration. Moneyline is
read only from its completed same-session Step-8 payload. No source model runs,
network requests, simulations, backfills, or source writes occur here.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v18 as v18
import wnba_daily_picks_hub_v9 as legacy_v9
import wnba_daily_picks_assists_connector_v1 as assists_feed
import wnba_daily_picks_spread_connector_v1 as spread_feed
import wnba_daily_picks_moneyline_connector_v1 as money_feed
import wnba_daily_picks_moneyline_integration_v1 as six

MODEL_VERSION = "WNBA DAILY PICKS V20 • MONEYLINE STEP-9 SIX-MARKET INTEGRATION"
_ET = ZoneInfo("America/New_York")
_MARKETS = ("PRA", "POINTS", "REBOUNDS", "ASSISTS", "SPREAD", "MONEYLINE")


def _count(frame: pd.DataFrame, market: str, state_col: str | None = None, state: str | None = None) -> int:
    if not isinstance(frame, pd.DataFrame) or frame.empty or "Market" not in frame.columns:
        return 0
    d = frame.loc[frame["Market"].astype(str).str.upper().eq(market)].copy()
    if state_col and state_col in d.columns and state is not None:
        d = d.loc[d[state_col].astype(str).str.upper().eq(state)]
    return int(len(d))


def _render_v18_with_live_feed_tiles(section_header=None, status_info=None, team_logo=None, h=None):
    now = datetime.now(_ET)
    day = now.strftime("%Y-%m-%d")
    assists = assists_feed.status(day)
    spread = spread_feed.status(day)
    money = money_feed.status(day)

    ui = legacy_v9.prev.base._ui
    original_card = ui._status_card
    original_caption = st.caption
    original_markdown = st.markdown

    def live_status_card(label, state, note):
        key = str(label or "").strip().upper()
        if key == "ASSISTS":
            return original_card(label, str(assists.get("state") or "⏳ NOT RUN"), str(assists.get("detail") or "No completed same-day Assists payload."))
        if key == "SPREAD":
            return original_card(label, str(spread.get("state") or "⏳ NOT RUN"), str(spread.get("detail") or "No completed same-day Spread payload."))
        if key == "MONEYLINE":
            return original_card(label, str(money.get("state") or "⏳ NOT RUN"), str(money.get("detail") or "No completed same-day Moneyline payload."))
        return original_card(label, state, note)

    def live_caption(body, *args, **kwargs):
        text = str(body)
        if text == "PRA, Points and Rebounds remain independent read-only feeds. Assists and game markets remain future connectors.":
            body = "PRA, Points, Rebounds, Assists, Spread and Moneyline are independent read-only feeds. Game Total remains a future connector."
        elif text == "PRA, Points, Rebounds, Assists and Spread are independent read-only feeds. Moneyline and Game Total remain future connectors.":
            body = "PRA, Points, Rebounds, Assists, Spread and Moneyline are independent read-only feeds. Game Total remains a future connector."
        return original_caption(body, *args, **kwargs)

    def live_markdown(body, *args, **kwargs):
        if isinstance(body, str) and "KYRE SPORTS AI • WNBA DAILY PICKS • STEP 9" in body:
            body = body.replace("🔌 3 read-only connectors", "🔌 6 read-only connectors")
            body = body.replace("🔌 5 read-only connectors", "🔌 6 read-only connectors")
        return original_markdown(body, *args, **kwargs)

    ui._status_card = live_status_card
    st.caption = live_caption
    st.markdown = live_markdown
    try:
        return v18.render_wnba_daily_picks_hub(
            section_header=section_header,
            status_info=status_info,
            team_logo=team_logo,
            h=h,
        )
    finally:
        ui._status_card = original_card
        st.caption = original_caption
        st.markdown = original_markdown


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_v18_with_live_feed_tiles(section_header=section_header, status_info=status_info, team_logo=team_logo, h=h)

    now = datetime.now(_ET)
    day = now.strftime("%Y-%m-%d")
    bundle = six.build_six_market_selection(day)
    feeds = bundle.get("feeds", {}) if isinstance(bundle, dict) else {}
    common = bundle.get("common") if isinstance(bundle, dict) else pd.DataFrame()
    audit = bundle.get("audit") if isinstance(bundle, dict) else pd.DataFrame()
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()
    selected = bundle.get("selected") if isinstance(bundle, dict) else pd.DataFrame()
    if not isinstance(common, pd.DataFrame): common = pd.DataFrame()
    if not isinstance(audit, pd.DataFrame): audit = pd.DataFrame()
    if not isinstance(ranked, pd.DataFrame): ranked = pd.DataFrame()
    if not isinstance(selected, pd.DataFrame): selected = pd.DataFrame()

    guarded = six.evaluate_six_market(selected, day, feeds=feeds, now_et=now)
    ready = six.ready_rows(guarded)
    diag = six.diagnostics(bundle, guarded)
    money = money_feed.status(day)

    ml_common = _count(common, "MONEYLINE")
    ml_safe = _count(audit, "MONEYLINE", "Safety state", "SAFE")
    ml_ranked = _count(ranked, "MONEYLINE", "Rank state", "RANKED")
    ml_selected = _count(selected, "MONEYLINE")
    ml_ready = _count(ready, "MONEYLINE")

    connected = {m: bool((feeds.get(m, {}) or {}).get("connected")) for m in _MARKETS}
    connected_n = sum(int(v) for v in connected.values())
    all6 = connected_n == 6
    pipeline = bool(diag.get("coverage_pass") and len(selected) <= 5)

    st.markdown("---")
    st.markdown("## 💰 Step 9 — Moneyline → Daily Picks Integration")
    st.caption(
        "Read-only connector → common schema → safety → cross-market protection/ranking → Top-5 selection → final production guard. "
        "No new simulations, network requests, source writes, backfills or forced picks."
    )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Moneyline connector", "CONNECTED" if money.get("connected") else "CHECK")
    a2.metric("Moneyline source picks", int(money.get("production_picks") or 0))
    a3.metric("Moneyline common rows", ml_common)
    a4.metric("Moneyline SAFE", ml_safe)

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Moneyline RANKED", ml_ranked)
    b2.metric("Moneyline SELECTED", ml_selected)
    b3.metric("Moneyline FINAL READY", ml_ready)
    b4.metric("Six-market feeds", f"{connected_n}/6")

    source_picks = int(money.get("production_picks") or 0)
    connector_pass = bool(
        money.get("connected")
        and ml_common == source_picks
        and ml_safe == ml_common
        and ml_ranked == ml_common
    )
    if connector_pass:
        if source_picks:
            st.success("✅ MONEYLINE CONNECTOR STEP 9 PASSED • completed Moneyline Step-8 QUALIFIED output reconciles read-only through schema, safety and ranking with no source-model changes.")
        else:
            st.success("✅ MONEYLINE CONNECTOR STEP 9 PASSED • Moneyline Step 8 is connected with 0 QUALIFIED plays; Daily Picks correctly adds zero forced Moneyline rows.")
    else:
        st.warning("⚠️ MONEYLINE CONNECTOR CHECK • the same-day Moneyline Step-8 source is missing or a row failed schema/safety/ranking reconciliation.")

    if not selected.empty:
        show = selected.copy()
        def candidate(r):
            market = str(r.get("Market") or "").upper()
            if market == "SPREAD":
                try: return f"{r.get('Team')} {float(r.get('Line')):+g}"
                except Exception: return f"{r.get('Team')} spread"
            if market == "MONEYLINE":
                return f"{r.get('Team')} ML"
            return f"{r.get('Player')} {r.get('Side')} {r.get('Line')}"
        show["Candidate"] = show.apply(candidate, axis=1)
        cols = [c for c in ("Daily rank", "Market", "Candidate", "Book", "Posted odds", "Model probability", "Edge", "Ranking score") if c in show.columns]
        st.markdown("### 🏆 Six-Market Overall Top 5 — pre-guard")
        st.dataframe(show[cols], use_container_width=True, hide_index=True)

    st.markdown("### 🛡️ Six-Market Final Production Guard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selected", len(selected))
    c2.metric("READY", int(diag.get("ready", 0)))
    c3.metric("MONITOR", int(diag.get("monitor", 0)))
    c4.metric("BLOCKED", int(diag.get("blocked", 0)))
    if isinstance(guarded, pd.DataFrame) and not guarded.empty:
        g = guarded.copy()
        cols = [c for c in ("Daily rank", "Market", "Player", "Team", "Side", "Line", "Book", "Guard state", "Guard reasons") if c in g.columns]
        st.dataframe(g[cols], use_container_width=True, hide_index=True)

    d1, d2, d3 = st.columns(3)
    d1.metric("Six-market pipeline", "PASS" if pipeline else "CHECK")
    d2.metric("All feeds connected", f"{connected_n}/6")
    d3.metric("Final READY", f"{len(ready)}/5")

    if all6 and pipeline:
        st.success("✅ SIX-MARKET END-TO-END PASS • PRA + Points + Rebounds + Assists + Spread + Moneyline reconcile through one guarded Daily Picks Top-5 pipeline.")
    elif pipeline:
        missing = [m.title() for m in _MARKETS if not connected[m]]
        st.info("ℹ️ Moneyline Step 9 is live. Full six-market end-to-end verification is waiting on: " + ", ".join(missing) + ".")
    else:
        st.warning("⚠️ SIX-MARKET PIPELINE CHECK • inspect the guard table before changing any source model. No backfill is performed.")

    st.caption(
        f"⚡ Daily Picks V20 • Moneyline Step 9 read-only • checked {now.strftime('%Y-%m-%d %I:%M:%S %p ET')} • "
        "new simulations 0 • network requests 0 • source writes 0 • backfills 0"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
