"""WNBA Final Decision — Step-1 read-only Points connector.

This module does NOT run or restore the Points model, request sportsbook data,
change a projection, or alter the WNBA Daily Master Card. It only inspects the
same-day completed WNBA Points V1.9 session payload already present in
Streamlit session state and reports whether Final Decision can safely see it.

Step 1 contract:
- PRA remains the only market feeding the Daily Master Card.
- Points is status/diagnostics only.
- Rebounds and every other future connector remain untouched.
- A valid Points payload may contain zero qualified picks; connection health is
  about completed model output, not whether a wager clears the model gates.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

import wnba_pra_final_v32 as final_ui

MODEL_VERSION = "WNBA FINAL POINTS CONNECTOR V1 • READ ONLY"
STANDARD_SIMS = 5_000_000

_REQUIRED_COLUMNS = {
    "market",
    "game_id",
    "player_key",
    "line",
    "book",
    "model_over",
    "no_vig_over",
    "edge",
    "model_qualified",
    "final_ready",
    "lineup_ready",
    "freshness",
    "converged",
    "sims",
}

_ORIGINAL_CONNECTORS = getattr(final_ui, "_render_connectors", None)


def _day(value) -> str:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _std_key(day: str) -> str:
    return f"wnba_points_v19_standard::{_day(day)}"


def _final_key(day: str) -> str:
    return f"wnba_points_v19_final::{_day(day)}"


def _frame(value) -> pd.DataFrame:
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def status(day) -> dict:
    """Inspect same-day Points output without invoking any Points function."""
    day_str = _day(day)
    base = {
        "day": day_str,
        "live": False,
        "state": "NEXT",
        "detail": "No same-day completed Points payload in this Streamlit session.",
        "rows": 0,
        "unique_distributions": 0,
        "qualified": 0,
        "final_ready": 0,
        "lineup_ready_games": 0,
        "games": 0,
        "source": "NONE",
        "missing_columns": [],
    }
    if not day_str:
        base.update(state="⚠ CHECK", detail="Final Decision slate date is unavailable.")
        return base

    std = st.session_state.get(_std_key(day_str)) or {}
    rows = _frame(std.get("rows"))
    if rows.empty:
        return base

    missing = sorted(_REQUIRED_COLUMNS.difference(rows.columns))
    if missing:
        base.update(
            state="⚠ CHECK",
            detail="Points payload exists but is missing required production fields.",
            rows=int(len(rows)),
            missing_columns=missing,
        )
        return base

    work = rows.copy()
    market_ok = work["market"].astype(str).str.upper().eq("POINTS")
    sims = pd.to_numeric(work["sims"], errors="coerce")
    completed = sims.ge(STANDARD_SIMS)
    identity_ok = (
        work["game_id"].astype(str).str.strip().ne("")
        & work["player_key"].astype(str).str.strip().ne("")
    )

    # Every stored row must belong to the Points connector and represent a
    # completed standard/final simulation. We do not partially bless a payload.
    if not bool(market_ok.all() and completed.all() and identity_ok.all()):
        bad = int((~(market_ok & completed & identity_ok)).sum())
        base.update(
            state="⚠ CHECK",
            detail=f"Points payload has {bad} incomplete or mismatched production row(s).",
            rows=int(len(work)),
        )
        return base

    keys = ["game_id", "player_key", "line"]
    unique = int(work[keys].drop_duplicates().shape[0])
    games = int(work["game_id"].astype(str).nunique())
    qualified = int(work["model_qualified"].fillna(False).astype(bool).sum())
    final_ready = int(work["final_ready"].fillna(False).astype(bool).sum())

    lineup_ready_games = 0
    if games:
        lineup = work.groupby("game_id", dropna=False)["lineup_ready"].max()
        lineup_ready_games = int(lineup.fillna(False).astype(bool).sum())

    fin = st.session_state.get(_final_key(day_str)) or {}
    frows = _frame(fin.get("rows"))
    source = "5M/10M" if not frows.empty else "5M"

    base.update(
        live=True,
        state="✅ CONNECTED",
        detail=(
            f"{len(work)} rows • {unique} distributions • {qualified} qualified • "
            f"{final_ready} final ready • lineups {lineup_ready_games}/{games}"
        ),
        rows=int(len(work)),
        unique_distributions=unique,
        qualified=qualified,
        final_ready=final_ready,
        lineup_ready_games=lineup_ready_games,
        games=games,
        source=source,
    )
    return base


def _connector_tile(name: str, state: str, live: bool, detail: str = "") -> str:
    color = "#64e5aa" if live else ("#ffe178" if "CHECK" in state else "#8aa0b2")
    border = "#276b52" if live else ("#78641f" if "CHECK" in state else "#30495d")
    title = escape(name)
    label = escape(state)
    tip = escape(detail, quote=True)
    return (
        f'<div title="{tip}" style="border:1px solid {border};background:#071827;'
        f'border-radius:12px;padding:9px;text-align:center;margin:3px 0">'
        f'<div style="font-size:9px;color:#7895aa;font-weight:900">{title}</div>'
        f'<div style="font-size:10px;color:{color};font-weight:1000;margin-top:3px">{label}</div>'
        '</div>'
    )


def render_connectors_read_only() -> None:
    """Drop-in replacement for the existing Final Decision connector strip."""
    day = st.session_state.get("wnba_pra_v2_date")
    points = status(day)

    items = [
        ("PRA", "✅ LIVE", True, "PRA remains the only market feeding the Daily Master Card in Step 1."),
        ("Points", points["state"], bool(points["live"]), points["detail"]),
        ("Rebounds", "NEXT", False, "Rebounds is intentionally paused until Points integration is verified."),
        ("Assists", "NEXT", False, "Not connected yet."),
        ("Spread", "NEXT", False, "Not connected yet."),
        ("Moneyline", "NEXT", False, "Not connected yet."),
        ("Total", "NEXT", False, "Not connected yet."),
    ]
    cols = st.columns(4)
    for i, (name, state, live, detail) in enumerate(items):
        cols[i % 4].markdown(_connector_tile(name, state, live, detail), unsafe_allow_html=True)

    with st.expander("🔌 Points connector — read-only check", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Connection", points["state"])
        c2.metric("Points distributions", int(points["unique_distributions"]))
        c3.metric("Qualified", int(points["qualified"]))
        c4.metric("Final ready", int(points["final_ready"]))
        st.caption(f"Slate {points['day'] or '—'} • source {points['source']} • {points['detail']}")
        if points.get("missing_columns"):
            st.warning("Missing fields: " + ", ".join(points["missing_columns"]))
        if points["live"]:
            st.success("✅ Same-day completed Points production payload is visible to Final Decision.")
        else:
            st.info("Points is not connected yet. Open the Points page and run/restore its same-day production pass, then return here. PRA does not need to be rerun.")
        st.caption(
            "STEP 1 READ-ONLY • Points output is visible to Final Decision but is NOT eligible for the Daily Master Card yet. "
            "No simulation, sportsbook request, restore, regrade, or projection is run from this connector."
        )


def install() -> None:
    """Patch presentation only; selection/model functions are untouched."""
    final_ui._render_connectors = render_connectors_read_only


__all__ = ["MODEL_VERSION", "status", "render_connectors_read_only", "install"]
