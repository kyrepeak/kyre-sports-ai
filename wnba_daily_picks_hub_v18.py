"""WNBA Daily Picks V18 — four-market end-to-end verification layer.

Preserves the complete V17 production page and appends only a passive verification
panel for the final same-session PRA + Points + Rebounds + Assists test.

This layer does not alter connectors, common-schema mapping, safety, protection,
ranking, selection, guard thresholds, source models, projections, prices or Monte
Carlo. It simply recomputes the already-established read-only four-market pipeline
and reports whether all four independent source feeds are present and whether rows
travel through the pipeline without silent loss.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v17 as v17
import wnba_daily_picks_selection_v2 as selection_v2
import wnba_daily_picks_guard_v2 as guard_v2

MODEL_VERSION = "WNBA DAILY PICKS V18 • FOUR-MARKET END-TO-END VERIFICATION"
_ET = ZoneInfo("America/New_York")
_MARKETS = ("PRA", "POINTS", "REBOUNDS", "ASSISTS")


def _count_market(frame: pd.DataFrame, market: str) -> int:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty or "Market" not in frame.columns:
        return 0
    return int(frame["Market"].astype(str).str.strip().str.upper().eq(market).sum())


def _state_count(frame: pd.DataFrame, column: str, state: str) -> int:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].astype(str).str.strip().str.upper().eq(state).sum())


def _feed_state(feed: dict) -> str:
    if bool((feed or {}).get("connected")):
        return "CONNECTED"
    state = str((feed or {}).get("state") or (feed or {}).get("status") or "NOT RUN").strip().upper()
    return state or "NOT RUN"


def _source_rows(feed: dict) -> int:
    for key in (
        "production_picks", "published", "final_ready", "qualified", "rows",
        "qualified_rows", "finalist_rows", "distributions",
    ):
        try:
            value = int(float((feed or {}).get(key, 0) or 0))
            if value:
                return value
        except Exception:
            pass
    return 0


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Freeze and render the entire verified V17 page first.
    v17.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )

    now_et = datetime.now(_ET)
    slate_day = now_et.strftime("%Y-%m-%d")

    bundle = selection_v2.build_four_market_selection(slate_day)
    feeds = bundle.get("feeds", {}) if isinstance(bundle, dict) else {}
    common = bundle.get("common") if isinstance(bundle, dict) else pd.DataFrame()
    audit = bundle.get("audit") if isinstance(bundle, dict) else pd.DataFrame()
    protected = bundle.get("protected") if isinstance(bundle, dict) else pd.DataFrame()
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()
    selected = bundle.get("selected") if isinstance(bundle, dict) else pd.DataFrame()

    for name, frame in (
        ("common", common), ("audit", audit), ("protected", protected),
        ("ranked", ranked), ("selected", selected),
    ):
        if not isinstance(frame, pd.DataFrame):
            if name == "common": common = pd.DataFrame()
            elif name == "audit": audit = pd.DataFrame()
            elif name == "protected": protected = pd.DataFrame()
            elif name == "ranked": ranked = pd.DataFrame()
            elif name == "selected": selected = pd.DataFrame()

    guarded = guard_v2.evaluate_four_market(selected, slate_day, feeds=feeds, now_et=now_et)
    ready = guard_v2.ready_rows(guarded)
    gdiag = guard_v2.diagnostics(guarded, selected)

    feed_connected = {m: bool((feeds.get(m, {}) or {}).get("connected")) for m in _MARKETS}
    connected_count = sum(int(v) for v in feed_connected.values())

    common_counts = {m: _count_market(common, m) for m in _MARKETS}
    safe_counts = {
        m: _count_market(
            audit.loc[audit.get("Safety state", pd.Series("", index=audit.index)).astype(str).str.upper().eq("SAFE")].copy()
            if isinstance(audit, pd.DataFrame) and not audit.empty else pd.DataFrame(),
            m,
        )
        for m in _MARKETS
    }
    ranked_rows = ranked.loc[
        ranked.get("Rank state", pd.Series("", index=ranked.index)).astype(str).str.upper().eq("RANKED")
    ].copy() if isinstance(ranked, pd.DataFrame) and not ranked.empty else pd.DataFrame()
    ranked_counts = {m: _count_market(ranked_rows, m) for m in _MARKETS}
    selected_counts = {m: _count_market(selected, m) for m in _MARKETS}
    ready_counts = {m: _count_market(ready, m) for m in _MARKETS}

    all_feeds_connected = connected_count == 4
    coverage_pass = bool(gdiag.get("coverage_pass"))
    selected_guarded = int(len(guarded)) == int(len(selected))
    top5_limit_ok = int(len(selected)) <= 5
    no_silent_common_loss = True
    # Connected feeds are allowed to contribute zero production rows. Any row that
    # does enter the common contract must appear in the safety audit.
    if not common.empty:
        no_silent_common_loss = int(len(audit)) == int(len(common))

    pipeline_integrity = bool(
        coverage_pass and selected_guarded and top5_limit_ok and no_silent_common_loss
    )
    full_e2e_pass = bool(all_feeds_connected and pipeline_integrity)

    st.markdown("---")
    st.markdown("## 🧪 Four-Market End-to-End Verification")
    st.caption(
        "Final passive system test only. Load PRA, Points, Rebounds and Assists from their own pages in this same Streamlit session, then return here. This panel verifies that all four independent feeds reach the shared schema → safety → protection → ranking → Top 5 → final guard chain."
    )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("PRA feed", _feed_state(feeds.get("PRA", {})))
    a2.metric("Points feed", _feed_state(feeds.get("POINTS", {})))
    a3.metric("Rebounds feed", _feed_state(feeds.get("REBOUNDS", {})))
    a4.metric("Assists feed", _feed_state(feeds.get("ASSISTS", {})))

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Feeds connected", f"{connected_count}/4")
    b2.metric("Common rows", int(len(common)))
    b3.metric("SAFE rows", _state_count(audit, "Safety state", "SAFE"))
    b4.metric("Candidate families", int(len(protected)))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ranked", _state_count(ranked, "Rank state", "RANKED"))
    c2.metric("Top-5 selected", f"{len(selected)}/5")
    c3.metric("Guard evaluated", int(len(guarded)))
    c4.metric("Final READY", f"{len(ready)}/5")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Pipeline integrity", "PASS" if pipeline_integrity else "CHECK")
    d2.metric("Four-market test", "PASS" if full_e2e_pass else "WAITING")
    d3.metric("New simulations", "0")
    d4.metric("Source-model writes", "0")

    if full_e2e_pass:
        st.success(
            "✅ FOUR-MARKET END-TO-END PASS • PRA, Points, Rebounds and Assists are all connected in this session and the shared Daily Picks pipeline reconciles from source feeds through the final production guard."
        )
    elif not all_feeds_connected:
        missing = [m.title() for m in _MARKETS if not feed_connected[m]]
        st.info(
            "⏳ FOUR-MARKET TEST WAITING • load these source model(s) in this same session: "
            + ", ".join(missing)
            + ". Do not reboot between source pages and Daily Picks."
        )
    else:
        st.warning(
            "⚠️ FOUR-MARKET PIPELINE CHECK • all four feeds are connected, but one or more row-coverage/Top-5/final-guard reconciliation checks did not pass. Inspect the audit below before changing any model."
        )

    market_rows = []
    for market in _MARKETS:
        feed = feeds.get(market, {}) or {}
        market_rows.append({
            "Market": market.title(),
            "Feed": _feed_state(feed),
            "Source output rows": _source_rows(feed),
            "Common schema": common_counts[market],
            "SAFE": safe_counts[market],
            "RANKED": ranked_counts[market],
            "SELECTED": selected_counts[market],
            "FINAL READY": ready_counts[market],
        })

    with st.expander("📋 Four-market source-to-final reconciliation", expanded=False):
        st.dataframe(pd.DataFrame(market_rows), use_container_width=True, hide_index=True)
        st.caption(
            "A connected market may correctly contribute 0 rows when its independent source model publishes no qualified production pick. Daily Picks never invents or forces a candidate."
        )

    with st.expander("🛡️ End-to-end integrity diagnostics", expanded=False):
        st.write(f"• Exact ET slate: {slate_day}")
        st.write(f"• Four source feeds connected: {connected_count}/4")
        st.write(f"• Common → safety row coverage: {'PASS' if no_silent_common_loss else 'CHECK'} ({len(common)} → {len(audit)})")
        st.write(f"• Top-5 maximum respected: {'PASS' if top5_limit_ok else 'CHECK'} ({len(selected)}/5)")
        st.write(f"• Selected → final-guard coverage: {'PASS' if selected_guarded and coverage_pass else 'CHECK'} ({len(selected)} → {len(guarded)})")
        st.write(f"• Final READY rows: {len(ready)}")
        st.write("• New simulations from Daily Picks: 0")
        st.write("• Network refreshes from this verification layer: 0")
        st.write("• Source-model writes: 0")
        st.write("• Ranking formula changes: 0")
        st.write("• Forced picks/backfills: 0")

    st.caption(
        f"⚡ WNBA Daily Picks V18 • V17 production logic frozen • four-market E2E verification only • checked {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
