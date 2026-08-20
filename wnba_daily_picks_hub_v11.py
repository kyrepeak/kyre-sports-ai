"""WNBA Daily Picks V11 — Assists Connector Step 1.

Preserves the complete Daily Picks V10 Steps 1–10 page and appends only a passive,
read-only WNBA Assists V20 Step-20 connector verification panel.

This step deliberately does NOT add Assists to the common schema, safety engine,
correlation protection, ranking, Top-5 selection, or final Daily Picks guard yet.
It launches zero simulations, makes zero sportsbook/model/network requests, and
writes to zero Assists production keys.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v10 as v10
import wnba_daily_picks_assists_connector_v1 as assists_feed

MODEL_VERSION = "WNBA DAILY PICKS V11 • ASSISTS CONNECTOR STEP 1"
_ET = ZoneInfo("America/New_York")


def _pct(value) -> str:
    try:
        x = float(value)
        return f"{100.0*x:.1f}%"
    except Exception:
        return "—"


def _preview_display(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    for c in ("Model probability", "No-vig probability", "Edge"):
        if c in out.columns:
            out[c] = out[c].map(_pct)
    if "EV / $100" in out.columns:
        out["EV / $100"] = pd.to_numeric(out["EV / $100"], errors="coerce").map(
            lambda x: "—" if pd.isna(x) else f"${x:+.2f}"
        )
    if "Simulation count" in out.columns:
        out["Simulation count"] = pd.to_numeric(out["Simulation count"], errors="coerce").map(
            lambda x: "—" if pd.isna(x) else f"{int(x):,}"
        )
    if "Posted odds" in out.columns:
        out["Posted odds"] = pd.to_numeric(out["Posted odds"], errors="coerce").map(
            lambda x: "—" if pd.isna(x) else f"{int(x):+d}"
        )
    return out


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # Freeze and render the complete existing Steps 1–10 implementation first.
    v10.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )

    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    feed = assists_feed.status(slate_day)

    st.markdown("---")
    st.markdown("## 🔌 Assists Connector — Step 1")
    st.caption(
        "Passive source verification only. This connector can read the completed same-day Assists V20 Step-20 production payload, but it is not yet allowed into Daily Picks standardization, safety, ranking, selection, or Step-10 final-card logic."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Connection", "CONNECTED" if feed.get("connected") else "NOT RUN / CHECK")
    c2.metric("Step-20 published", f"{int(feed.get('production_picks', 0))}/5")
    c3.metric("Qualified players", int(feed.get("qualified", 0)))
    c4.metric("Candidate sides", int(feed.get("candidate_sides", 0)))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Production ready", int(feed.get("final_ready", 0)))
    d2.metric("Converged pick rows", int(feed.get("converged", 0)))
    d3.metric("Visible sim proofs", f"{int(feed.get('completed_sims', 0)):,}")
    d4.metric("Daily Picks writes", "0")

    if feed.get("connected"):
        st.success(
            "✅ ASSISTS CONNECTOR STEP 1 PASSED • the completed same-day Assists Step-20 production output is visible read-only to Daily Picks. Nothing has been standardized or ranked with PRA/Points/Rebounds yet."
        )
    elif str(feed.get("state") or "").startswith("⚠"):
        st.warning(f"⚠️ ASSISTS CONNECTOR CHECK • {feed.get('detail')}")
    else:
        st.info(
            "⏳ ASSISTS NOT RUN / NOT LOADED • Daily Picks remains healthy. The Assists model can only be run from the Assists page."
        )

    st.caption(
        f"Assists slate {feed.get('day') or slate_day} • source {feed.get('source') or 'NONE'} • "
        f"Step 20 {'PASS' if feed.get('step20_ready') else 'NOT LOADED'} • "
        f"source timestamp {feed.get('ran_at') or '—'}"
    )

    with st.expander("📋 Assists Step-20 production preview — display only", expanded=False):
        preview = _preview_display(assists_feed.preview_rows(slate_day, limit=12))
        if preview.empty:
            if feed.get("connected"):
                st.info("Assists Step 20 is connected with a valid 0/5 production result — no picks were forced.")
            else:
                st.info("No same-day Assists Step-20 production rows are currently loaded in this Streamlit session.")
        else:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        st.caption(
            "Display only • no Assists requalification • no common-schema insertion • no cross-market ranking • no model writeback."
        )

    with st.expander("🛡️ Assists Connector Step-1 isolation diagnostics", expanded=False):
        st.write("• Reads only wnba_assists_v20_* same-day Streamlit session-state outputs")
        st.write("• Imports Assists production modules: NO")
        st.write("• Assists simulations launched by Daily Picks: 0")
        st.write("• Sportsbook/injury/roster/network requests launched by this connector: 0")
        st.write("• Assists production session-state writes: 0")
        st.write("• PRA / Points / Rebounds / Assists projections changed: 0")
        st.write("• Added to Daily Picks common schema: NO — Step 2")
        st.write("• Added to Daily Picks safety/ranking/Top 5: NO")
        st.write("• A valid Assists Step-20 PASS with 0/5 is treated as CONNECTED, not NOT RUN")

    st.info(
        "➡️ NEXT: Assists Connector Step 2 will add this verified read-only payload to the existing Daily Picks common schema. Existing Steps 1–10 remain frozen until this connector is verified on-screen."
    )
    st.caption(
        "⚡ WNBA Daily Picks V11 • Assists Connector Step 1 • Daily Picks Steps 1–10 preserved • read-only visibility only"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
