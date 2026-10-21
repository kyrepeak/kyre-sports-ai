"""Provider-aware WNBA PRA customer presentation.

The backend selects one current approved sportsbook for the primary board.
This renderer displays that exact provider, line and price without averaging or
substituting a different book in presentation code.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import wnba_pra_advanced_diagnostics_v1 as diagnostics
import wnba_pra_product_view_v2 as previous

PRODUCT_CSS = previous.PRODUCT_CSS


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    try:
        number = float(value)
        if math.isnan(number):
            return "—"
        return f"{number:.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _odds(value: Any) -> str:
    try:
        number = int(float(value))
        return f"+{number}" if number > 0 else str(number)
    except (TypeError, ValueError):
        return "—"


def _player_key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _market_quotes(snapshot) -> dict[str, dict[str, Any]]:
    frame = getattr(snapshot, "market_rows", None)
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return {}
    rows = frame.copy()
    if "player" not in rows.columns or "book" not in rows.columns or "line" not in rows.columns:
        return {}
    if "market_grade" in rows.columns:
        rows = rows.sort_values("market_grade", ascending=False)
    out: dict[str, dict[str, Any]] = {}
    for _, row in rows.iterrows():
        key = _player_key(row.get("player"))
        if not key or key in out:
            continue
        book = str(row.get("book") or "").strip()
        line = row.get("line")
        if not book or pd.isna(line):
            continue
        out[key] = {
            "selected_sportsbook": book,
            "line": line,
            "over_odds": row.get("over_odds"),
            "under_odds": row.get("under_odds"),
            "freshness": str(row.get("freshness") or "UNAVAILABLE"),
        }
    return out


def _player_card(view, quote: dict[str, Any]) -> str:
    face = (
        f'<img class="fd-face" src="{escape(view.headshot_url)}" alt="{escape(view.player)}">'
        if view.headshot_url else '<div class="fd-face"></div>'
    )
    logo = (
        f'<img class="fd-logo" src="{escape(view.team_logo_url)}" alt="team logo">'
        if view.team_logo_url else ""
    )
    selected_sportsbook = str(quote.get("selected_sportsbook") or "Sportsbook")
    edge = _fmt(float(view.edge) * 100.0, 1, " pp") if view.edge is not None else "—"
    prices = f"O {_odds(quote.get('over_odds'))} • U {_odds(quote.get('under_odds'))}"
    evidence = escape(str(view.evidence_state or "UNAVAILABLE").replace("_", " "))
    freshness = escape(str(quote.get("freshness") or view.market_freshness or "UNAVAILABLE").replace("_", " "))
    decision = escape(view.decision_label or "Research only")
    return (
        '<div class="fd-card"><div class="fd-person">' + face + logo +
        f'<div><div class="fd-name">{escape(view.player)}</div>'
        f'<div class="fd-meta">{escape(view.team)} vs {escape(view.opponent)}</div></div></div>'
        '<div class="fd-grid">'
        f'<div class="fd-metric primary"><span>{escape(selected_sportsbook)} PRA</span><b>{_fmt(quote.get("line"))}</b></div>'
        f'<div class="fd-metric"><span>Model PRA</span><b>{_fmt(view.proj_pra)}</b></div>'
        f'<div class="fd-metric"><span>Over / Under</span><b>{_pct(view.over_probability)} / {_pct(view.under_probability)}</b></div>'
        f'<div class="fd-metric"><span>Edge</span><b>{edge}</b></div>'
        f'<div class="fd-metric"><span>Decision</span><b>{decision}</b></div>'
        f'<div class="fd-metric"><span>Confidence</span><b>{_fmt(view.decision_strength)}</b></div>'
        f'</div><div class="fd-foot">{escape(selected_sportsbook)} prices: {prices}<br>{freshness} • {evidence} • exact provider quote</div></div>'
    )


def _player_detail(view, quote: dict[str, Any]) -> None:
    selected_sportsbook = str(quote.get("selected_sportsbook") or "Sportsbook")
    st.markdown(
        '<div class="fd-detail"><strong>Decision Snapshot</strong>'
        f'<div class="fd-detail-grid"><div class="fd-mini"><span>{escape(selected_sportsbook)} PRA</span><b>{_fmt(quote.get("line"))}</b></div>'
        f'<div class="fd-mini"><span>Model PRA</span><b>{_fmt(view.proj_pra)}</b></div>'
        f'<div class="fd-mini"><span>Over</span><b>{_pct(view.over_probability)}</b></div>'
        f'<div class="fd-mini"><span>Under</span><b>{_pct(view.under_probability)}</b></div></div>'
        '<strong>P / R / A Breakdown</strong>'
        f'<div class="fd-detail-grid"><div class="fd-mini"><span>Points</span><b>{_fmt(view.proj_pts)}</b></div>'
        f'<div class="fd-mini"><span>Rebounds</span><b>{_fmt(view.proj_reb)}</b></div>'
        f'<div class="fd-mini"><span>Assists</span><b>{_fmt(view.proj_ast)}</b></div>'
        f'<div class="fd-mini"><span>PRA</span><b>{_fmt(view.proj_pra)}</b></div></div>'
        f'<p><strong>Minutes + Role:</strong> {_fmt(view.projected_minutes)} projected minutes • {escape(view.role_label or "Role pending")}</p>'
        '<p><strong>Market Rule:</strong> The displayed line and price belong to the named sportsbook only; no conflicting lines are averaged.</p>'
        f'<p><strong>Sources + Freshness:</strong> {escape(selected_sportsbook)} is the selected current market source • {escape(str(quote.get("freshness") or "UNAVAILABLE"))} • evidence {escape(view.evidence_state.replace("_", " "))}.</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_pra_product(snapshot, context, player_views, consensus) -> None:
    st.markdown(PRODUCT_CSS, unsafe_allow_html=True)
    quotes = _market_quotes(snapshot)
    eligible = tuple((view, quotes.get(_player_key(view.player))) for view in player_views)
    eligible = tuple((view, quote) for view, quote in eligible if quote is not None)
    selected_sportsbook = next((quote["selected_sportsbook"] for _, quote in eligible), "Approved sportsbook")

    st.markdown(
        '<div class="fd-wrap"><div class="fd-hero">'
        '<div class="fd-eyebrow">KYRE SPORTS AI • WNBA</div><div class="fd-title">🏀 WNBA PRA</div>'
        f'<div class="fd-sub">{escape(context.competition_label)} • {escape(context.series_label or "Verified slate context")}<br>'
        f'Current exact {escape(selected_sportsbook)} PRA markets selected by Kyre Sports API.</div>'
        f'<div class="fd-pills"><div class="fd-pill live">Market-qualified</div><div class="fd-pill">{escape(selected_sportsbook)}</div><div class="fd-pill">Kyre model</div><div class="fd-pill">{escape(context.evidence_state.replace("_", " "))}</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("### PRA Player Board")
    if not eligible:
        st.info(
            "No current exact approved WNBA PRA market is available for this verified slate yet. "
            "Kyre Sports API will continue with the next approved provider when the primary source is unavailable."
        )
    else:
        st.markdown('<div class="fd-board">' + ''.join(_player_card(view, quote) for view, quote in eligible) + '</div>', unsafe_allow_html=True)
        for view, quote in eligible:
            with st.expander(f"{view.player} • Full PRA Analysis", expanded=False):
                _player_detail(view, quote)

    if any(view.availability_label == "UNRESOLVED" for view, _ in eligible):
        st.warning("One or more market-listed players still have unresolved availability; Final Card certification remains blocked for those players.")

    st.markdown("### 🏆 Final PRA Card")
    selected = [(view, quote) for view, quote in eligible if view.final_card_selected]
    if not selected:
        st.info("No market-qualified PRA selection is certified for this slate yet. No pick is being forced.")
    else:
        rows = []
        for index, (view, quote) in enumerate(selected[:5], 1):
            book = str(quote.get("selected_sportsbook") or "Sportsbook")
            rows.append(
                f'<div class="fd-final-row"><b>#{index} {escape(view.player)} — {escape(view.decision_label or "Qualified PRA")}</b><br>'
                f'<span>{escape(view.team)} vs {escape(view.opponent)} • {escape(book)} PRA {_fmt(quote.get("line"))} • Model PRA {_fmt(view.proj_pra)} • Over {_pct(view.over_probability)}</span></div>'
            )
        st.markdown('<div class="fd-final">' + ''.join(rows) + '</div>', unsafe_allow_html=True)

    diagnostics.render_advanced_diagnostics(snapshot, context, consensus)


__all__ = ["PRODUCT_CSS", "render_pra_product"]
