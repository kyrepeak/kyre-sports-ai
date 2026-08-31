"""Step 5.7 presentation-only MLB price-health + edge-retention layer.

Runs strictly downstream of certified Step 5.6. It summarizes the current exact
FanDuel price, snapshot freshness, same-line price-only EV trajectory, and zero-EV
crossing state without altering any production model or Final Card behavior.

The 2-minute fresh / 5-minute aging bands are display-only context. They do not
change Pick Strength, ranking, selection, risk logic, persistence, or wagering.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_market_movement_v1 as step56
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_price_health_v1 import (
    MLBPriceHealthError,
    price_health_context,
)

VERSION = "MLB DAILY PICKS STEP 5.7 • PRICE HEALTH + EDGE RETENTION"
_STATE_KEY = "mlb_step5_7_price_health_v1"


def _odds(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _pct(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:+.1f}%"


def _pp(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:+.1f} pp"


def _age(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "age unavailable"
    seconds = max(0.0, float(value))
    if seconds < 60:
        return f"{seconds:.0f}s old"
    if seconds < 3600:
        return f"{seconds / 60.0:.1f}m old"
    return f"{seconds / 3600.0:.1f}h old"


def _health_label(status: Any) -> str:
    return {
        "POSITIVE_VALUE_IMPROVING": "🟢 POSITIVE VALUE • IMPROVING PRICE",
        "POSITIVE_VALUE_COMPRESSED": "🟡 POSITIVE VALUE • PRICE COMPRESSED",
        "POSITIVE_VALUE": "🟢 POSITIVE VALUE",
        "BREAK_EVEN": "⚪ BREAK-EVEN PRICE",
        "NEGATIVE_VALUE_IMPROVING": "🟠 NEGATIVE VALUE • IMPROVING",
        "NEGATIVE_VALUE_WORSENING": "🔴 NEGATIVE VALUE • WORSENING",
        "NEGATIVE_VALUE": "🔴 NEGATIVE VALUE",
        "STALE_SNAPSHOT": "🟠 STALE MARKET SNAPSHOT",
        "FRESHNESS_UNAVAILABLE": "⚪ SNAPSHOT FRESHNESS UNAVAILABLE",
        "LINE_CHANGED_NOT_COMPARABLE": "↕️ LINE CHANGED • RE-COMPARE CURRENT LINE ONLY",
    }.get(str(status or ""), "PRICE HEALTH")


def _freshness_label(status: Any) -> str:
    return {
        "FRESH": "FRESH",
        "AGING": "AGING",
        "STALE": "STALE",
        "UNKNOWN": "UNKNOWN",
    }.get(str(status or ""), "UNKNOWN")


def price_health_context_for_candidate(candidate: Mapping[str, Any], games_df) -> Mapping[str, Any] | None:
    """Build Step 5.7 from the exact Step 5.6 candidate context, failing closed."""
    try:
        movement = step56.movement_context_for_candidate(candidate, games_df)
        if not isinstance(movement, Mapping):
            return None
        return price_health_context(movement)
    except (MLBPriceHealthError, Exception):
        return None


def _price_health_board_html(context: Mapping[str, Any]) -> str:
    health = escape(_health_label(context.get("price_health_status")))
    freshness = escape(_freshness_label(context.get("snapshot_freshness_status")))
    age = escape(_age(context.get("snapshot_age_seconds")))
    odds = escape(_odds(context.get("current_market_odds")))
    fair_limit = escape(_odds(context.get("model_zero_ev_american_price_limit")))
    headroom = escape(_pp(context.get("value_headroom_percentage_points")))
    current_ev = escape(_pct(context.get("current_expected_value_per_unit")))
    trajectory = escape(str(context.get("value_trajectory") or "UNAVAILABLE").replace("_", " "))
    crossing = escape(str(context.get("zero_ev_crossing_status") or "NOT COMPARABLE").replace("_", " "))

    return (
        '<div style="border:1px solid #4b778e;background:#07131c;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#a9e7ff">PRICE HEALTH • STEP 5.7</div>'
        f'<div style="font-size:8px;font-weight:900;color:#eef7fb">{health}</div>'
        f'<div style="font-size:8px;color:#dbe9f1;font-weight:800">FanDuel {odds} • model zero-EV limit {fair_limit}</div>'
        f'<div style="font-size:8px;color:#dbe9f1;font-weight:800">Current EV {current_ev} • value headroom {headroom}</div>'
        f'<div style="font-size:8px;color:#dbe9f1;font-weight:800">Snapshot {freshness} • {age}</div>'
        f'<div style="font-size:7px;color:#82a8bd">Price trajectory: {trajectory} • zero-EV crossing: {crossing}</div>'
        '<div style="font-size:7px;color:#82a8bd">Freshness bands are display-only • no model, Pick Strength, ranking, selection, risk, persistence, or wagering changes</div>'
        '</div>'
    )


def _decision_card_step5_7(c, rank, games_df, ts, snap, baseline, risk):
    html = step56._decision_card_step5_6(c, rank, games_df, ts, snap, baseline, risk)
    context = price_health_context_for_candidate(c, games_df)
    if context is None:
        return html
    board = _price_health_board_html(context)
    marker = '<div class="kui-score">'
    if marker in html:
        return html.replace(marker, board + marker, 1)
    return html + board


def _why_sections_step5_7(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step56._why_sections_step5_6(c, games_df, snap, ts, baseline, risk)
    ]
    context = price_health_context_for_candidate(c, games_df)
    market = str(c.get("market") or "")

    if context is None:
        if market in {"Moneyline", "Run Line", "Total"}:
            line = (
                "Step 5.7 price health is unavailable because the exact Step 5.6 movement/freshness context could not be proven. "
                "No freshness, trajectory, or zero-EV crossing claim is fabricated."
            )
        else:
            line = (
                "Step 5.7 remains limited to full-game Moneyline, Run Line, and Total because those are the markets with certified exact-ID FanDuel prices. "
                "Player-prop price health remains unavailable until a certified prop-price feed exists."
            )
    else:
        freshness = str(context.get("snapshot_freshness_status") or "UNKNOWN")
        health = str(context.get("price_health_status") or "")
        trajectory = str(context.get("value_trajectory") or "")
        crossing = str(context.get("zero_ev_crossing_status") or "")
        line = (
            f"Step 5.7 price health: {health.replace('_', ' ').lower()}. "
            f"The exact FanDuel price is {_odds(context.get('current_market_odds'))} versus the unchanged model zero-EV limit {_odds(context.get('model_zero_ev_american_price_limit'))}; "
            f"current EV is {_pct(context.get('current_expected_value_per_unit'))} with {_pp(context.get('value_headroom_percentage_points'))} of probability headroom. "
            f"Snapshot freshness is {freshness.lower()} ({_age(context.get('snapshot_age_seconds'))}); same-line price trajectory is {trajectory.replace('_', ' ').lower()} and zero-EV crossing state is {crossing.replace('_', ' ').lower()}. "
            "The freshness bands and price-health label are comparison-only and do not alter Final Card logic."
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


def install_price_health_layer(
    games_df,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Install Step 5.7 downstream of Step 5.6 without touching selection state."""
    step56_state = step56.install_market_movement_layer(games_df, payload=payload)
    state = {
        "data_type": "mlb_price_health_presentation_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "comparison_only": True,
        "freshness_bands_are_display_only": True,
        "ephemeral_session_history": True,
        "durable_persistence": False,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "selection_impact": False,
        "ranking_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "step5_6_available": bool(step56_state.get("collected_at_utc")),
        "derived_market_context_count": int(step56_state.get("derived_market_context_count") or 0),
        "collected_at_utc": step56_state.get("collected_at_utc"),
    }
    st.session_state[_STATE_KEY] = state
    v217._decision_card_v217 = _decision_card_step5_7
    v217._why_sections = _why_sections_step5_7
    return state


__all__ = [
    "VERSION",
    "install_price_health_layer",
    "price_health_context_for_candidate",
]
