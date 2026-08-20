"""WNBA Daily Picks V16 — Assists Connector Step 6 Top-5 selection integration.

Preserves the complete Daily Picks V15 page (existing Daily Picks Steps 1–10 and
Assists Connector Steps 1–5) and appends only a four-market Top-5 selection
verification panel.

The frozen Daily Picks Step-9 selection contract is reused unchanged. Assists may
now appear in the same selection board as PRA, Points and Rebounds. This is still
pre-guard output: Connector Step 7 owns the final production-ready recheck.

No source model is run or modified; no Monte Carlo/network request/source write
occurs here.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v15 as v15
import wnba_daily_picks_hub_v9 as visual
import wnba_daily_picks_selection_v2 as selection_v2

MODEL_VERSION = "WNBA DAILY PICKS V16 • ASSISTS CONNECTOR STEP 6 TOP 5"
_ET = ZoneInfo("America/New_York")


def _selection_view(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    keep = [
        "Daily rank", "Selection state", "Rank", "Ranking score", "Market",
        "Player", "Team", "Opponent", "Side", "Line", "Book", "Posted odds",
        "Projection", "Model probability", "No-vig ranked", "Edge ranked",
        "EV / $100 ranked", "Exposure penalty", "Qualification state",
        "Freshness", "Protection flags",
    ]
    out = frame[[c for c in keep if c in frame.columns]].copy()
    for col in ("Model probability", "No-vig ranked", "Edge ranked"):
        if col in out.columns:
            vals = pd.to_numeric(out[col], errors="coerce")
            out[col] = vals.map(lambda x: f"{100.0*x:.1f}%" if pd.notna(x) else "—")
    return out


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Preserve everything already verified through Connector Step 5.
    v15.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )

    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    bundle = selection_v2.build_four_market_selection(slate_day)
    diag = selection_v2.diagnostics(bundle)
    selected = bundle.get("selected") if isinstance(bundle, dict) else pd.DataFrame()
    skipped = bundle.get("skipped") if isinstance(bundle, dict) else pd.DataFrame()
    ranked = bundle.get("ranked") if isinstance(bundle, dict) else pd.DataFrame()

    if not isinstance(selected, pd.DataFrame):
        selected = pd.DataFrame()
    if not isinstance(skipped, pd.DataFrame):
        skipped = pd.DataFrame()
    if not isinstance(ranked, pd.DataFrame):
        ranked = pd.DataFrame()

    coverage = bool(diag.get("selection_coverage"))
    selected_counts = dict(diag.get("selected_counts") or {})

    st.markdown("---")
    st.markdown("## 🏆 Assists Connector — Step 6: Four-Market Top 5 Selection")
    st.caption(
        "Selection integration only. The existing Daily Picks Step-9 rules now consume the four-market ranked board: PRA + Points + Rebounds + Assists. Rank order is preserved, one card per player is allowed, game/team concentration is capped, and five is never forced. The final production guard remains OFF until Connector Step 7."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ranked eligible", int(diag.get("eligible", 0)))
    c2.metric("Published", f"{int(diag.get('published', 0))}/{int(diag.get('max_cards', 5))}")
    c3.metric("Markets selected", int(diag.get("selected_markets", 0)))
    c4.metric("Selection coverage", "PASS" if coverage else "CHECK")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("PRA selected", int(selected_counts.get("PRA", 0)))
    d2.metric("Points selected", int(selected_counts.get("POINTS", 0)))
    d3.metric("Rebounds selected", int(selected_counts.get("REBOUNDS", 0)))
    d4.metric("Assists selected", int(selected_counts.get("ASSISTS", 0)))

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Same-player skips", int(diag.get("same_player_skips", 0)))
    e2.metric("Game-cap skips", int(diag.get("game_cap_skips", 0)))
    e3.metric("Team-cap skips", int(diag.get("team_cap_skips", 0)))
    e4.metric("Final guard", "OFF")

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("New simulations", "0")
    f2.metric("Network requests", "0")
    f3.metric("Production writes", "0")
    f4.metric("Forced picks", "0")

    if coverage:
        published = int(diag.get("published", 0))
        if published:
            st.success(
                f"✅ ASSISTS CONNECTOR STEP 6 PASSED • {published} selection(s) were published from the four-market ranking using the existing Daily Picks diversity rules. The board is pre-guard only; Connector Step 7 still owns final production readiness."
            )
        else:
            st.success(
                "✅ ASSISTS CONNECTOR STEP 6 PASSED • the four-market ranking currently yields 0/5 selections. No pick was forced. Connector Step 7 remains the final guard."
            )
    else:
        st.warning(
            "⚠️ ASSISTS CONNECTOR STEP 6 CHECK • the four-market ranking/selection handoff did not fully reconcile. Final production guarding remains disabled."
        )

    if not selected.empty:
        st.markdown("### 🏆 Four-Market Top 5 — PRE-GUARD")
        st.caption(
            "These are Step-9-style selections from the current four-market ranked board. They are not final production-ready Daily Picks until Connector Step 7 rechecks them."
        )
        # Reuse the existing verified visual-card renderer. Its on-card wording
        # correctly says STEP-9 SELECTED / STEP 10 GUARD PENDING because Connector
        # Step 6 maps to the existing Daily Picks Step-9 selection layer.
        visual._render_cards(selected)

    with st.expander("🏆 Four-market selection audit — PRE-GUARD", expanded=False):
        view = _selection_view(selected)
        if view.empty:
            st.info("No current ranked candidate passed into a Top-5 slot; nothing was forced.")
        else:
            st.dataframe(view, use_container_width=True, hide_index=True)
        st.caption("Display only • final guard not yet applied • no source-model writeback.")

    with st.expander("🧷 Selection holds / diversity audit", expanded=False):
        if skipped.empty:
            st.info("No ranked row was skipped by the one-player / game-cap / team-cap rules before the card filled or candidates ended.")
        else:
            st.dataframe(skipped, use_container_width=True, hide_index=True)
        st.write(f"• Maximum cards: {int(diag.get('max_cards', 5))}")
        st.write(f"• Maximum cards from one game: {int(diag.get('max_per_game', 3))}")
        st.write(f"• Maximum cards from one team: {int(diag.get('max_per_team', 3))}")
        st.write("• One published card per player")
        st.write("• Ranking is not rescored in this layer")
        st.write("• No requirement to fill all five slots")

    with st.expander("🛡️ Assists Connector Step-6 isolation diagnostics", expanded=False):
        st.write("• Input: only four-market rows already marked RANKED")
        st.write("• Ranking formula changes: 0")
        st.write("• Assists projection/distribution/5M/qualification changes: 0")
        st.write("• New simulations: 0")
        st.write("• Sportsbook/injury/network requests: 0")
        st.write("• Production/source-model writes: 0")
        st.write("• Final production-ready guard: OFF — Connector Step 7")

    st.info(
        "➡️ FINAL CONNECTOR STEP: Step 7 will pass these selected rows through the existing Daily Picks production-ready guard/recheck. Only guard-passed rows will become the final four-market Daily Picks card."
    )
    st.caption(
        "⚡ WNBA Daily Picks V16 • Assists Connector Step 6 • four-market Top-5 selection ACTIVE • final guard OFF"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
