"""Step 5.8 presentation-only MLB actionability shadow policy.

Runs strictly downstream of certified Step 5.7. It shows what a future execution
policy would say (playable / refresh / reprice / wait / pass) while remaining
completely non-binding. It does not modify model math, Pick Strength, ranking,
selection, risk logic, persistence, or wagering.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_price_health_v1 as step57
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_actionability_shadow_v1 import actionability_shadow_context

VERSION = "MLB DAILY PICKS STEP 5.8 • ACTIONABILITY SHADOW POLICY"
_STATE_KEY = "mlb_step5_8_actionability_shadow_v1"


def _shadow_label(status: Any) -> str:
    return {
        "SHADOW_PLAYABLE": "🟢 SHADOW PLAYABLE",
        "SHADOW_PLAYABLE_IMPROVING": "🟢 SHADOW PLAYABLE • IMPROVING",
        "SHADOW_PLAYABLE_COMPRESSED": "🟡 SHADOW PLAYABLE • COMPRESSED",
        "SHADOW_MONITOR_REFRESH": "🟡 SHADOW MONITOR • REFRESH FIRST",
        "SHADOW_REPRICE_LINE_CHANGE": "↕️ SHADOW REPRICE • LINE CHANGED",
        "SHADOW_WAIT_NEGATIVE_IMPROVING": "🟠 SHADOW WAIT • PRICE IMPROVING",
        "SHADOW_PASS_BREAK_EVEN": "⚪ SHADOW PASS • BREAK-EVEN",
        "SHADOW_PASS_NEGATIVE_VALUE": "🔴 SHADOW PASS • NEGATIVE VALUE",
        "SHADOW_BLOCK_STALE": "🟠 SHADOW BLOCK • STALE SNAPSHOT",
        "SHADOW_BLOCK_UNKNOWN_FRESHNESS": "⚪ SHADOW BLOCK • AGE UNKNOWN",
    }.get(str(status or ""), "SHADOW ACTIONABILITY")


def actionability_shadow_for_candidate(candidate: Mapping[str, Any], games_df) -> Mapping[str, Any] | None:
    try:
        health = step57.price_health_context_for_candidate(candidate, games_df)
        if not isinstance(health, Mapping):
            return None
        return actionability_shadow_context(health)
    except Exception:
        return None


def _shadow_board_html(context: Mapping[str, Any]) -> str:
    label = escape(_shadow_label(context.get("shadow_status")))
    action = escape(str(context.get("shadow_action") or "UNAVAILABLE").replace("_", " "))
    reason = escape(str(context.get("shadow_reason") or ""))
    return (
        '<div style="border:1px solid #70643d;background:#171508;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#ffe79a">ACTIONABILITY SHADOW • STEP 5.8</div>'
        f'<div style="font-size:8px;font-weight:900;color:#fff7d8">{label}</div>'
        f'<div style="font-size:8px;color:#eee3bb;font-weight:800">Shadow action: {action}</div>'
        f'<div style="font-size:7px;color:#c9bd91">{reason}</div>'
        '<div style="font-size:7px;color:#a89c73">SHADOW ONLY • activation disabled • does not change Final Card, Pick Strength, ranking, risk, persistence, or wagering</div>'
        '</div>'
    )


def _decision_card_step5_8(c, rank, games_df, ts, snap, baseline, risk):
    html = step57._decision_card_step5_7(c, rank, games_df, ts, snap, baseline, risk)
    context = actionability_shadow_for_candidate(c, games_df)
    if context is None:
        return html
    board = _shadow_board_html(context)
    marker = '<div class="kui-score">'
    if marker in html:
        return html.replace(marker, board + marker, 1)
    return html + board


def _why_sections_step5_8(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step57._why_sections_step5_7(c, games_df, snap, ts, baseline, risk)
    ]
    context = actionability_shadow_for_candidate(c, games_df)
    market = str(c.get("market") or "")
    if context is None:
        if market in {"Moneyline", "Run Line", "Total"}:
            line = (
                "Step 5.8 shadow actionability is unavailable because the exact Step 5.7 price-health context could not be proven. "
                "No play / wait / pass decision is fabricated."
            )
        else:
            line = (
                "Step 5.8 remains limited to full-game Moneyline, Run Line, and Total because those are the markets with certified exact-ID FanDuel pricing. "
                "Player-prop actionability remains unavailable until a certified prop-price feed exists."
            )
    else:
        line = (
            f"Step 5.8 shadow actionability: {str(context.get('shadow_status') or '').replace('_', ' ').lower()} — "
            f"{str(context.get('shadow_reason') or '')} "
            "This is a shadow-only policy result. Activation is disabled, so it cannot add, remove, rerank, resize, or wager a Final Card selection."
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


def install_actionability_shadow_layer(
    games_df,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    step57_state = step57.install_price_health_layer(games_df, payload=payload)
    state = {
        "data_type": "mlb_actionability_shadow_presentation_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "shadow_only": True,
        "activation_enabled": False,
        "strict_positive_ev_required": True,
        "fresh_snapshot_required_for_shadow_playable": True,
        "aging_positive_value_requires_refresh": True,
        "stale_or_unknown_freshness_never_shadow_playable": True,
        "line_change_requires_reprice": True,
        "comparison_only": True,
        "ephemeral_session_history": True,
        "durable_persistence": False,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "selection_impact": False,
        "ranking_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "step5_7_available": bool(step57_state.get("collected_at_utc")),
        "derived_market_context_count": int(step57_state.get("derived_market_context_count") or 0),
        "collected_at_utc": step57_state.get("collected_at_utc"),
    }
    st.session_state[_STATE_KEY] = state
    v217._decision_card_v217 = _decision_card_step5_8
    v217._why_sections = _why_sections_step5_8
    return state


__all__ = [
    "VERSION",
    "actionability_shadow_for_candidate",
    "install_actionability_shadow_layer",
]
