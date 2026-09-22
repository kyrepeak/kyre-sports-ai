"""WNBA Daily Picks V13 — Assists Connector Step 3 safety-engine integration.

Preserves the complete Daily Picks V12 page (existing Daily Picks Steps 1–10,
Assists Connector Step 1 read-only verification and Step 2 common-schema
insertion) and appends only a read-only Assists safety-gate verification panel.

Assists rows are evaluated through the existing Daily Picks Step-6 safety logic.
They are NOT yet passed into duplicate/correlation protection, cross-market
ranking, Top-5 selection, or the final Step-10 production guard.

No simulations, sportsbook/model/network requests, source-model writes,
projection changes, requalification, ranking or selection occur here.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v12 as v12
import wnba_daily_picks_standardizer_v2 as standardizer
import wnba_daily_picks_assists_connector_v1 as assists_feed
import wnba_daily_picks_safety_v2 as safety

MODEL_VERSION = "WNBA DAILY PICKS V13 • ASSISTS CONNECTOR STEP 3 SAFETY"
_ET = ZoneInfo("America/New_York")


def _audit_view(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
        "Posted odds", "Simulation count", "Converged", "Qualification state",
        "Freshness", "Safety state", "Slate gate", "Identity gate", "Market gate",
        "Simulation gate", "Convergence gate", "Availability gate",
        "Game-state gate", "Freshness gate", "Hard failures", "Holds",
    ]
    return frame[[c for c in keep if c in frame.columns]].copy()


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Render frozen Daily Picks V12 first: Steps 1–10 + Assists connector Steps 1–2.
    v12.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )

    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    feed = assists_feed.status(slate_day)
    schema_diag = standardizer.diagnostics(slate_day)
    assists = standardizer.normalize_assists(slate_day)
    audit = safety.evaluate_assists(assists, slate_day)
    diag = safety.diagnostics(audit)

    input_rows = int(len(assists))
    evaluated_rows = int(len(audit))
    source_ready = bool(feed.get("connected"))
    schema_ready = bool(schema_diag.get("assists_schema_ready"))
    evaluated_all = evaluated_rows == input_rows
    # A verified 0/5 Assists production result is a legitimate empty safety pass.
    layer_ready = bool(source_ready and schema_ready and evaluated_all)

    st.markdown("---")
    st.markdown("## 🛡️ Assists Connector — Step 3: Safety Engine")
    st.caption(
        "Safety integration only. Standardized Assists rows are evaluated through the existing Daily Picks safety contract for exact slate, identity, market fields, 5M proof, convergence, source qualification, availability, game state and freshness. Ranking and Top 5 remain OFF for Assists during this test."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Assists input rows", input_rows)
    c2.metric("Safety evaluated", evaluated_rows)
    c3.metric("✅ SAFE", int(diag.get("safe", 0)))
    c4.metric("⏳ HOLD", int(diag.get("hold", 0)))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("⛔ REJECT", int(diag.get("reject", 0)))
    d2.metric("New simulations", "0")
    d3.metric("Network requests", "0")
    d4.metric("Production writes", "0")

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Source connector", "PASS" if source_ready else "CHECK")
    e2.metric("Common schema", "PASS" if schema_ready else "CHECK")
    e3.metric("Safety coverage", "PASS" if evaluated_all else "CHECK")
    e4.metric("Ranking / Top 5", "OFF / OFF")

    if layer_ready:
        if input_rows == 0:
            st.success(
                "✅ ASSISTS CONNECTOR STEP 3 PASSED • the same-day Assists source is a valid production 0/5 result, so there are no rows to safety-audit and nothing is forced downstream."
            )
        else:
            st.success(
                f"✅ ASSISTS CONNECTOR STEP 3 PASSED • all {input_rows} standardized Assists row(s) were evaluated by the existing Daily Picks safety engine. SAFE/HOLD/REJECT are row-level outcomes; only SAFE rows will be eligible when ranking is connected later."
            )
    else:
        st.warning(
            "⚠️ ASSISTS CONNECTOR STEP 3 CHECK • the source, common-schema handoff or full-row safety coverage did not verify. Ranking remains disabled for Assists."
        )

    if input_rows and int(diag.get("safe", 0)) == 0:
        st.info(
            "ℹ️ No Assists row is currently SAFE. That is not automatically an engine failure: HOLD/REJECT rows are intentionally prevented from reaching future ranking until their safety evidence clears."
        )

    with st.expander("📋 Assists Daily Picks safety audit — display only", expanded=False):
        view = _audit_view(audit)
        if view.empty:
            st.info("No Assists production rows exist to safety-audit right now.")
        else:
            st.dataframe(view, use_container_width=True, hide_index=True)
        st.caption("Display only • no ranking • no selection • no guard publishing • no Assists source-state writeback.")

    with st.expander("🧪 Assists Connector Step-3 gate diagnostics", expanded=False):
        st.write("• Slate gate: exact current Eastern calendar date")
        st.write("• Identity gate: non-empty player/team/opponent and team ≠ opponent")
        st.write("• Market gate: exact Assist side/line/book/posted odds/projection/probability")
        st.write("• Simulation gate: source connected + row-level 5,000,000-trial proof")
        st.write("• Convergence gate: row-level Monte Carlo convergence required")
        st.write("• Source qualification: Step-20 PRODUCTION READY is preserved")
        st.write("• Availability gate: same-session roster/injury/status evidence can downgrade to HOLD/REJECT")
        st.write("• Game-state gate: explicit started/live/final evidence rejects")
        st.write(f"• Freshness gate: existing Daily Picks safety maximum {int(safety.MAX_QUOTE_AGE_MIN)} minutes")
        st.write("• Existing Step-6 safety logic is reused; the compatibility adapter only extends its accepted market identity to ASSISTS")
        st.write("• New simulations: 0")
        st.write("• Network requests: 0")
        st.write("• Production/source-model writes: 0")
        st.write("• Correlation protection: OFF — next connector step")
        st.write("• Cross-market ranking / Top 5 / final production guard: OFF for Assists")

    st.info(
        "➡️ NEXT: Assists Connector Step 4 will pass only SAFE Assists rows into the existing Daily Picks duplicate/correlation protection layer. Cross-market ranking will still remain OFF during that test."
    )
    st.caption(
        "⚡ WNBA Daily Picks V13 • Assists Connector Step 3 • existing Daily Picks Steps 1–10 preserved • safety integration only"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
