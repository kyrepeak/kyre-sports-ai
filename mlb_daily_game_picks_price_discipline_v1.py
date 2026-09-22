"""Step 5.5 presentation-only MLB price-discipline layer.

Runs strictly downstream of Step 5.4. It separates handicap edge from actual price
edge by comparing the production model probability to both FanDuel no-vig probability
and the raw break-even probability implied by the exact FanDuel price. It also shows
selected-side vig drag, EV, and the model's zero-EV American price limit.

This layer is informational only. It does not change production probability,
projection, Pick Strength, simulation, ranking, selection, risk logic, persistence,
or wagering state.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_model_market_edge_v1 as step54
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_price_discipline_v1 import (
    MLBPriceDisciplineError,
    price_discipline_context,
)

VERSION = "MLB DAILY PICKS STEP 5.5 • PRICE DISCIPLINE + ZERO-EV PRICE LIMIT"
_STATE_KEY = "mlb_step5_5_price_discipline_v1"


def _pct(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:.1f}%"


def _pp(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:+.1f} pp"


def _ev(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:+.1f}%"


def _odds(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _status_label(status: Any) -> str:
    text = str(status or "")
    if text == "POSITIVE_VALUE":
        return "✅ POSITIVE VALUE"
    if text == "BREAK_EVEN":
        return "🟡 BREAK-EVEN"
    if text == "NEGATIVE_VALUE":
        return "⛔ NEGATIVE VALUE"
    return "—"


def price_context_for_candidate(candidate: Mapping[str, Any], games_df) -> Mapping[str, Any] | None:
    """Return one read-only Step 5.5 context or None when Step 5.4 is unavailable."""
    try:
        edge_context = step54.edge_context_for_candidate(candidate, games_df)
        if not isinstance(edge_context, Mapping):
            return None
        return price_discipline_context(edge_context)
    except (MLBPriceDisciplineError, Exception):
        return None


def _price_board_html(context: Mapping[str, Any]) -> str:
    status = escape(_status_label(context.get("current_price_status")))
    return (
        '<div style="border:1px solid #4c6573;background:#081219;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#a8e4ff">PRICE DISCIPLINE • STEP 5.5</div>'
        f'<div style="font-size:8px;font-weight:900;color:#e7f2f8">{status}</div>'
        '<div style="font-size:8px;color:#dbe9f1;font-weight:800">'
        f'Model {_pct(context.get("model_probability"))} • '
        f'Raw break-even {_pct(context.get("market_raw_break_even_probability"))} • '
        f'Price margin {escape(_pp(context.get("pricing_margin_probability")))}</div>'
        '<div style="font-size:8px;color:#dbe9f1;font-weight:800">'
        f'No-vig edge {escape(_pp(context.get("handicap_edge_probability")))} • '
        f'Vig drag {escape(_pp(context.get("vig_drag_probability")))} • '
        f'EV {escape(_ev(context.get("expected_value_per_unit")))}</div>'
        '<div style="font-size:8px;color:#dbe9f1;font-weight:800">'
        f'FanDuel {escape(_odds(context.get("market_odds")))} • '
        f'Zero-EV price limit {escape(_odds(context.get("zero_ev_american_price_limit")))}</div>'
        '<div style="font-size:7px;color:#82a8bd">Display only • does not alter Pick Strength, ranking, selection, or risk logic</div>'
        '</div>'
    )


def _decision_card_step5_5(c, rank, games_df, ts, snap, baseline, risk):
    html = step54._decision_card_step5_4(c, rank, games_df, ts, snap, baseline, risk)
    context = price_context_for_candidate(c, games_df)
    if context is None:
        return html
    board = _price_board_html(context)
    marker = '<div class="kui-score">'
    if marker in html:
        return html.replace(marker, board + marker, 1)
    return html + board


def _why_sections_step5_5(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step54._why_sections_step5_4(c, games_df, snap, ts, baseline, risk)
    ]
    context = price_context_for_candidate(c, games_df)
    market = str(c.get("market") or "")
    if context is None:
        if market in {"Moneyline", "Run Line", "Total"}:
            line = (
                "Step 5.5 price discipline is unavailable because a certified Step 5.4 price context could not be proven. "
                "No price status, vig drag, or playable limit is fabricated."
            )
        else:
            line = (
                "Step 5.5 remains limited to full-game Moneyline, Run Line, and Total because those are the markets with certified exact-ID FanDuel prices. "
                "Player-prop price discipline remains intentionally unavailable until an equally certified prop-price feed exists."
            )
    else:
        line = (
            f"Step 5.5 price discipline: the production model is {_pct(context.get('model_probability'))}; "
            f"the exact FanDuel price {_odds(context.get('market_odds'))} requires {_pct(context.get('market_raw_break_even_probability'))} to break even. "
            f"That leaves a {_pp(context.get('pricing_margin_probability'))} price margin after vig. "
            f"The underlying model-vs-no-vig edge is {_pp(context.get('handicap_edge_probability'))}; "
            f"selected-side vig consumes {_pp(context.get('vig_drag_probability'))}. "
            f"Current EV is {_ev(context.get('expected_value_per_unit'))}, so the exact price is {_status_label(context.get('current_price_status')).lower()}. "
            f"The model's zero-EV American price limit is {_odds(context.get('zero_ev_american_price_limit'))}. "
            "This is display-only and does not change Pick Strength, ranking, selection, or risk logic."
        )

    out = []
    inserted = False
    for title, lines in sections:
        if title == "📈 Market context":
            lines.append(line)
            inserted = True
        out.append((title, lines))
    if not inserted:
        out.insert(1, ("📈 Market context", [line]))
    return out


def install_price_discipline_layer(
    games_df,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Install Step 5.5 downstream of Step 5.4 without touching selection state."""
    step54_state = step54.install_model_market_edge_layer(games_df, payload=payload)
    state = {
        "data_type": "mlb_price_discipline_presentation_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "comparison_only": True,
        "selection_impact": False,
        "ranking_impact": False,
        "wagering_impact": False,
        "step5_4_available": bool(step54_state.get("step5_3_available")),
        "derived_market_context_count": int(step54_state.get("derived_market_context_count") or 0),
    }
    st.session_state[_STATE_KEY] = state
    v217._decision_card_v217 = _decision_card_step5_5
    v217._why_sections = _why_sections_step5_5
    return state


__all__ = [
    "VERSION",
    "install_price_discipline_layer",
    "price_context_for_candidate",
]
