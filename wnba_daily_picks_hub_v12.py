"""WNBA Daily Picks V12 — Assists Connector Step 2 common-schema insertion.

Preserves the complete Daily Picks V11 page (existing Steps 1–10 + Assists
Connector Step 1) and appends only a read-only common-schema verification panel.

Assists V20 Step-20 production rows are now allowed into the same 22-column Daily
Picks schema used by PRA, Points and Rebounds. They are NOT yet passed through the
Daily Picks safety engine, duplicate/correlation protection, ranking, Top-5
selection, or final Step-10 production guard. No source-model write occurs.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v11 as v11
import wnba_daily_picks_standardizer_v2 as standardizer

MODEL_VERSION = "WNBA DAILY PICKS V12 • ASSISTS CONNECTOR STEP 2 COMMON SCHEMA"
_ET = ZoneInfo("America/New_York")


def _pct(value) -> str:
    try:
        x = float(value)
        return f"{100.0*x:.1f}%"
    except Exception:
        return "—"


def _schema_preview(frame: pd.DataFrame) -> pd.DataFrame:
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
    # Render the verified Step-1 connector and the complete frozen Daily Picks
    # Steps 1–10 exactly as they already exist.
    v11.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )

    slate_day = datetime.now(_ET).strftime("%Y-%m-%d")
    common = standardizer.normalize_all(slate_day)
    assists = standardizer.normalize_assists(slate_day)
    diag = standardizer.diagnostics(slate_day)
    counts = dict(diag.get("market_counts") or {})
    ready = bool(diag.get("assists_schema_ready"))

    st.markdown("---")
    st.markdown("## 🧩 Assists Connector — Step 2: Common Schema")
    st.caption(
        "Schema insertion only. The verified Assists V20 Step-20 production rows are mapped into the exact same 22-column Daily Picks contract used by PRA, Points and Rebounds. Safety, correlation protection, ranking, Top 5 and the final guard remain OFF for Assists until later connector steps."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Schema", f"{int(diag.get('schema_columns') or 0)}/22 columns")
    c2.metric("Assists source", f"{int(diag.get('assists_source_picks') or 0)} row(s)")
    c3.metric("Assists standardized", int(diag.get("assists_schema_rows") or 0))
    c4.metric("Total common rows", int(diag.get("rows") or 0))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("PRA rows", int(counts.get("PRA", 0)))
    d2.metric("Points rows", int(counts.get("POINTS", 0)))
    d3.metric("Rebounds rows", int(counts.get("REBOUNDS", 0)))
    d4.metric("Assists rows", int(counts.get("ASSISTS", 0)))

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Missing required cells", int(diag.get("missing_required_cells") or 0))
    e2.metric("New simulations", "0")
    e3.metric("Network requests", "0")
    e4.metric("Production writes", "0")

    if ready:
        if assists.empty:
            st.success(
                "✅ ASSISTS CONNECTOR STEP 2 PASSED • Assists Step 20 is a verified connected 0/5 result, so the common schema correctly receives zero Assists rows. No pick was invented."
            )
        else:
            st.success(
                f"✅ ASSISTS CONNECTOR STEP 2 PASSED • {len(assists)} verified Assists production row(s) now match the existing Daily Picks 22-column common schema. Nothing has entered safety/ranking/selection yet."
            )
    elif bool(diag.get("assists_connected")):
        st.warning(
            "⚠️ ASSISTS SCHEMA CHECK • the source connector is connected, but the number of valid standardized Assists rows does not reconcile to the Step-20 production output. Safety/ranking integration remains locked."
        )
    else:
        st.info(
            "⏳ ASSISTS SCHEMA ARMED • no connected same-day Assists Step-20 payload is currently visible. Run Assists from its own page, then return here in the same session."
        )

    with st.expander("📋 Assists rows in Daily Picks common schema — display only", expanded=False):
        preview = _schema_preview(assists)
        if preview.empty:
            if ready:
                st.caption("Verified connected 0/5 Assists result — zero schema rows by design.")
            else:
                st.caption("No verified Assists rows are currently available for schema insertion.")
        else:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        st.caption("Common-schema display only • no safety result • no ranking score • no Daily Picks selection.")

    with st.expander("🧾 Four-market common-schema audit — display only", expanded=False):
        if common.empty:
            st.caption("No source rows are loaded in the common schema in this session.")
        else:
            audit = common.copy()
            show_cols = [
                c for c in (
                    "Market", "Player", "Team", "Opponent", "Side", "Line", "Book",
                    "Posted odds", "Projection", "Model probability", "Edge", "EV / $100",
                    "Simulation count", "Converged", "Qualification state", "Source",
                ) if c in audit.columns
            ]
            st.dataframe(_schema_preview(audit[show_cols]), use_container_width=True, hide_index=True)

    with st.expander("🛡️ Assists Connector Step-2 isolation diagnostics", expanded=False):
        st.write("• PRA / Points / Rebounds schema mapping: frozen V1 implementation")
        st.write("• Assists source: read-only V20 Step-20 standardized production payload")
        st.write("• Common contract: exact same 22 Daily Picks columns")
        st.write("• Source Assists requalification performed here: NO")
        st.write("• Daily Picks safety engine applied to Assists: NO — Connector Step 3")
        st.write("• Duplicate/correlation protection applied to Assists: NO")
        st.write("• Cross-market ranking applied to Assists: NO")
        st.write("• Top-5 selection applied to Assists: NO")
        st.write("• Step-10 final production guard applied to Assists: NO")
        st.write("• New simulations / network requests / production-model writes: 0 / 0 / 0")

    if ready:
        st.info(
            "➡️ NEXT: Assists Connector Step 3 will pass these standardized Assists rows through the existing Daily Picks safety engine only. Ranking and Top 5 will remain off for Assists during that test."
        )
    else:
        st.info("🔒 NEXT remains held until the Assists common-schema insertion passes on-screen.")

    st.caption(
        "⚡ WNBA Daily Picks V12 • Assists Connector Step 2 • existing Daily Picks Steps 1–10 preserved • common-schema insertion only"
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
