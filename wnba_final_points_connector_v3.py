"""WNBA Final Decision — persistent dashboard status layer.

Builds on the verified Step-2 Points card feed. This layer changes presentation
state only:
- Final Decision may render before PRA 5M exists;
- PRA reports WAITING 5M instead of falsely reporting LIVE when no stored PRA
  production payload exists;
- Points reports its own independent same-day production state;
- Rebounds remains intentionally NEXT/untouched.

No projection, Monte Carlo, market, qualification or card-selection math changes.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

import wnba_pra_final_v32 as final_ui
import wnba_final_points_connector_v1 as step1
import wnba_final_points_connector_v2 as step2

MODEL_VERSION = "WNBA FINAL DASHBOARD V3.1 • EXPLICIT MARKET STATES"


def _connector_tile(name: str, state: str, live: bool, detail: str = "") -> str:
    waiting = "WAIT" in str(state).upper() or "PENDING" in str(state).upper()
    check = "CHECK" in str(state).upper() or "LOCK" in str(state).upper()
    color = "#64e5aa" if live else ("#ffe178" if (waiting or check) else "#8aa0b2")
    border = "#276b52" if live else ("#78641f" if (waiting or check) else "#30495d")
    return (
        f'<div title="{escape(detail, quote=True)}" style="border:1px solid {border};background:#071827;'
        f'border-radius:12px;padding:9px;text-align:center;margin:3px 0">'
        f'<div style="font-size:9px;color:#7895aa;font-weight:900">{escape(name)}</div>'
        f'<div style="font-size:10px;color:{color};font-weight:1000;margin-top:3px">{escape(state)}</div>'
        '</div>'
    )


def _pra_status(day):
    if day is None:
        return False, "NEXT", "Select a WNBA slate date first.", 0
    try:
        rows, meta = step2._ORIGINAL_STORED_ROWS(day)
    except Exception:
        rows, meta = pd.DataFrame(), {"source": "NONE"}
    live = isinstance(rows, pd.DataFrame) and not rows.empty
    if live:
        source = str((meta or {}).get("source") or "5M")
        return True, "✅ LIVE", f"Completed PRA {source} payload is available to Final Decision.", int(len(rows))
    return False, "⏳ WAITING PRA 5M", "Final Decision is visible, but PRA has no completed same-day 5M production payload yet.", 0


def _points_status(day):
    points = step1.status(day)
    live = bool(points.get("live"))
    if live:
        detail = (
            f"Card feed active • {points.get('unique_distributions',0)} distributions • "
            f"{points.get('qualified',0)} qualified • {points.get('final_ready',0)} final ready"
        )
        return points, True, "✅ LIVE", detail

    restore_error = str(st.session_state.get("_wnba_final_points_restore_error") or "").strip()
    if restore_error:
        return points, False, "⚠ RESTORE CHECK", f"A persisted Points recovery attempt failed: {restore_error}"

    if day is not None:
        return (
            points,
            False,
            "⏳ WAITING POINTS 5M",
            "Points is wired to Final Decision but no validated completed same-day Points production payload is currently loaded/restored.",
        )
    return points, False, "NEXT", "Select a WNBA slate date first."


def render_connectors_persistent() -> None:
    day = st.session_state.get("wnba_pra_v2_date")
    pra_live, pra_state, pra_detail, pra_rows = _pra_status(day)
    points, points_live, points_state, points_detail = _points_status(day)

    items = [
        ("PRA", pra_state, pra_live, pra_detail),
        ("Points", points_state, points_live, points_detail),
        ("Rebounds", "NEXT", False, "Rebounds remains intentionally paused until its separate connector step."),
        ("Assists", "NEXT", False, "Not connected yet."),
        ("Spread", "NEXT", False, "Not connected yet."),
        ("Moneyline", "NEXT", False, "Not connected yet."),
        ("Total", "NEXT", False, "Not connected yet."),
    ]
    cols = st.columns(4)
    for i, (name, state, live, detail) in enumerate(items):
        cols[i % 4].markdown(_connector_tile(name, state, live, detail), unsafe_allow_html=True)

    with st.expander("🔌 Final Decision feed status — PRA + Points", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("PRA", pra_state)
        c2.metric("PRA market rows", pra_rows)
        c3.metric("Points", points_state)
        c4.metric("Points distributions", int(points.get("unique_distributions", 0)))
        st.caption(
            f"Slate {points.get('day') or (pd.to_datetime(day).strftime('%Y-%m-%d') if day is not None else '—')} • "
            f"Points source {points.get('source') or 'NONE'} • Points lineups {points.get('lineup_ready_games',0)}/{points.get('games',0)}"
        )
        if pra_live:
            st.success("✅ PRA completed production output is connected. LIVE means the PRA feed exists; it does not mean a PRA pick qualified.")
        else:
            st.info("⏳ PRA is waiting for its own standard 5M pass. The dashboard remains visible and no PRA simulation is launched here.")
        if points_live:
            st.success("✅ Points completed same-day output is connected and eligible to feed the Master Card under existing qualification rules.")
        elif points_state == "⚠ RESTORE CHECK":
            st.warning(points_detail)
        else:
            st.info("⏳ Points is connected at the dashboard level but is waiting for the POINTS 5M production pass (or a valid same-day Points snapshot restore). This is separate from the PRA Step-8 simulation.")
        st.caption(
            "DASHBOARD ONLY • PRA 5M and Points 5M are separate simulations. Each market reports independently. "
            "This panel never runs Monte Carlo, changes a projection, requests a sportsbook line, or forces a pick. Rebounds is untouched."
        )


def install() -> None:
    """Install Step 2 card feed, then replace only its connector-strip renderer."""
    step2.install()
    final_ui._render_connectors = render_connectors_persistent


# Re-export the Step-2 card-feed helpers for diagnostics/compatibility.
stored_rows_combined = step2.stored_rows_combined
best_offer_market_aware = step2.best_offer_market_aware
card_html_market_aware = step2.card_html_market_aware
why_market_aware = step2.why_market_aware

__all__ = [
    "MODEL_VERSION", "install", "render_connectors_persistent",
    "stored_rows_combined", "best_offer_market_aware", "card_html_market_aware", "why_market_aware",
]
