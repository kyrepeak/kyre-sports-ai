"""WNBA Daily Picks V14 — Assists Connector Step 4 protection integration.

Preserves the complete Daily Picks V13 page (existing Daily Picks Steps 1–10 and
Assists Connector Steps 1–3) and appends only duplicate/correlation protection
verification for SAFE Assists rows.

Cross-market ranking, Top-5 selection and the final Daily Picks production guard
remain OFF for Assists. No simulations, network requests, source-model writes,
projection changes, requalification, ranking or selection occur here.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v13 as v13
import wnba_daily_picks_standardizer_v2 as standardizer
import wnba_daily_picks_assists_connector_v1 as assists_feed
import wnba_daily_picks_safety_v2 as safety
import wnba_daily_picks_protection_v2 as protection

MODEL_VERSION = "WNBA DAILY PICKS V14 • ASSISTS CONNECTOR STEP 4 PROTECTION"
_ET = ZoneInfo("America/New_York")


def _protection_view(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
        "Safety state", "Protection state", "Protection flags", "Candidate key",
        "Quote group size", "Alternate lines", "Player candidate groups",
        "Player markets", "Game key", "Game candidate groups",
        "Team exposure key", "Team candidate groups",
    ]
    return frame[[c for c in keep if c in frame.columns]].copy()


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Render frozen V13 first: Daily Picks Steps 1–10 + Assists Connector 1–3.
    v13.render_wnba_daily_picks_hub(
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
    safety_diag = safety.diagnostics(audit)
    protected = protection.protect_assists(audit)
    diag = protection.diagnostics(protected, audit)

    source_ready = bool(feed.get("connected"))
    schema_ready = bool(schema_diag.get("assists_schema_ready"))
    safety_coverage = int(len(audit)) == int(len(assists))
    protection_coverage = bool(diag.get("coverage_pass"))
    layer_ready = bool(source_ready and schema_ready and safety_coverage and protection_coverage)

    safe_rows = int(safety_diag.get("safe", 0))
    protected_rows = int(diag.get("protected_rows", 0))

    st.markdown("---")
    st.markdown("## 🧬 Assists Connector — Step 4: Duplicate + Correlation Protection")
    st.caption(
        "Protection integration only. Only Step-3 SAFE Assists rows enter this layer. The existing Daily Picks protection contract groups duplicate sportsbook quotes, alternate lines and player/game/team exposure before ranking. Cross-market ranking and Top 5 remain OFF for Assists during this test."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Step-3 SAFE rows", safe_rows)
    c2.metric("Protection evaluated", protected_rows)
    c3.metric("Candidate families", int(diag.get("candidate_groups", 0)))
    c4.metric("Duplicate quote groups", int(diag.get("duplicate_quote_groups", 0)))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Alternate-line groups", int(diag.get("alternate_line_groups", 0)))
    d2.metric("Player-correlation groups", int(diag.get("player_correlation_groups", 0)))
    d3.metric("Game-exposure groups", int(diag.get("game_exposure_groups", 0)))
    d4.metric("Team-exposure groups", int(diag.get("team_exposure_groups", 0)))

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Protection coverage", "PASS" if protection_coverage else "CHECK")
    e2.metric("New simulations", "0")
    e3.metric("Production writes", "0")
    e4.metric("Ranking / Top 5", "OFF / OFF")

    if layer_ready:
        if safe_rows == 0:
            st.success(
                "✅ ASSISTS CONNECTOR STEP 4 PASSED • no Assists row is currently SAFE, so protection has zero eligible rows and correctly creates no candidate family. Nothing is forced downstream."
            )
        else:
            st.success(
                f"✅ ASSISTS CONNECTOR STEP 4 PASSED • all {safe_rows} SAFE Assists row(s) were processed by the existing Daily Picks duplicate/correlation protection layer. Protection flags describe exposure; they do not rank or select a pick."
            )
    else:
        st.warning(
            "⚠️ ASSISTS CONNECTOR STEP 4 CHECK • source/schema/safety/protection coverage did not fully reconcile. Cross-market ranking remains disabled for Assists."
        )

    with st.expander("🧬 Assists protection audit — display only", expanded=False):
        view = _protection_view(protected)
        if view.empty:
            st.info("No SAFE Assists rows currently exist to annotate for duplicate/correlation exposure.")
        else:
            st.dataframe(view, use_container_width=True, hide_index=True)
        st.caption("Display only • protection tags are not scores • no ranking • no selection • no source-model writeback.")

    with st.expander("🛡️ Assists Connector Step-4 isolation diagnostics", expanded=False):
        st.write("• Input eligibility: Safety state must equal SAFE")
        st.write("• Candidate key: slate + market + player + side + line")
        st.write("• Multiple books for one exact wager are one candidate family, not independent picks")
        st.write("• Alternate lines for the same player/market are tagged")
        st.write("• Player, same-game and same-team exposure are tagged before ranking")
        st.write("• Protection state does not itself reject a SAFE row; it supplies exposure metadata for later ranking/selection")
        st.write("• Existing Daily Picks Protection V1 logic is reused without editing its behavior")
        st.write("• Cross-market PRA/Points/Rebounds + Assists ranking: OFF until Connector Step 5")
        st.write("• New simulations: 0")
        st.write("• Sportsbook/injury/network requests: 0")
        st.write("• Production/source-model writes: 0")
        st.write("• Assists projection/distribution/5M result/Step-20 qualification changes: 0")

    st.info(
        "➡️ NEXT: Assists Connector Step 5 will let protected SAFE Assists candidate families enter the existing cross-market ranking with PRA, Points and Rebounds. Top-5 publishing will still remain separate until Step 6."
    )
    st.caption(
        "⚡ WNBA Daily Picks V14 • Assists Connector Step 4 • existing Daily Picks Steps 1–10 preserved • duplicate/correlation protection only"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
