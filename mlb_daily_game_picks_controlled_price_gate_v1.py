"""Step 5.9 feature-flagged controlled MLB price-aware Final Card gate.

Production default is OFF. When `MLB_STEP5_9_PRICE_GATE_ENABLED` is explicitly
set to a truthy value, certified full-game markets must pass the Step 5.8 shadow
policy before they remain eligible for Final Card selection. Player props are
passed through unchanged because they do not yet have a certified exact-price feed.

Even when active, this layer filters eligibility only. It never edits projection,
probability, Pick Strength, ranking math, risk logic, persistence, or wagering.
"""
from __future__ import annotations

from html import escape
import os
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_actionability_shadow_v1 as step58
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_controlled_price_gate_v1 import (
    SUPPORTED_MARKETS,
    controlled_price_gate,
)

VERSION = "MLB DAILY PICKS STEP 5.9 • CONTROLLED PRICE GATE"
_STATE_KEY = "mlb_step5_9_controlled_price_gate_v1"
_GATE_CONTEXTS_KEY = "mlb_step5_9_gate_contexts_v1"
_ENV_KEY = "MLB_STEP5_9_PRICE_GATE_ENABLED"
_BASE_ALL_LIVE_CONTEXT = v217._all_live_context


def price_gate_activation_requested() -> bool:
    value = str(os.getenv(_ENV_KEY, "0") or "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _candidate_key(candidate: Mapping[str, Any]):
    return v217._candidate_key(candidate)


def controlled_gate_for_candidate(
    candidate: Mapping[str, Any],
    games_df,
    *,
    activation_requested: bool | None = None,
) -> dict[str, Any]:
    active = price_gate_activation_requested() if activation_requested is None else bool(activation_requested)
    market = str(candidate.get("market") or "")

    if market not in SUPPORTED_MARKETS:
        return {
            "data_type": "mlb_controlled_price_gate_passthrough_v1",
            "schema_version": 1,
            "market": market,
            "activation_requested": active,
            "gate_status": "NOT_APPLICABLE_UNPRICED_MARKET",
            "final_card_price_eligible": True,
            "gate_reason": "This market has no certified exact-price feed yet, so Step 5.9 leaves existing eligibility unchanged.",
            "selection_eligibility_impact": False,
            "model_math_impact": False,
            "pick_strength_impact": False,
            "ranking_math_impact": False,
            "risk_logic_impact": False,
            "wagering_impact": False,
            "durable_persistence": False,
        }

    shadow = step58.actionability_shadow_for_candidate(candidate, games_df)
    if not isinstance(shadow, Mapping):
        return {
            "data_type": "mlb_controlled_price_gate_unverified_v1",
            "schema_version": 1,
            "market": market,
            "activation_requested": active,
            "gate_status": "GATE_BLOCK_UNVERIFIED_PRICE_CONTEXT" if active else "CONTROL_DISABLED_UNVERIFIED_PRICE_CONTEXT",
            "final_card_price_eligible": not active,
            "gate_reason": (
                "Controlled gate is active and exact Step 5.8 price context could not be proven."
                if active
                else "Controlled gate is disabled; unverified price context does not alter existing selection behavior."
            ),
            "selection_eligibility_impact": active,
            "model_math_impact": False,
            "pick_strength_impact": False,
            "ranking_math_impact": False,
            "risk_logic_impact": False,
            "wagering_impact": False,
            "durable_persistence": False,
        }

    return controlled_price_gate(shadow, activation_requested=active)


def _all_live_context_step5_9(games_df):
    candidates, base_selected, snaps, baseline, ts, risks = _BASE_ALL_LIVE_CONTEXT(games_df)
    active = price_gate_activation_requested()
    gates: dict[Any, dict[str, Any]] = {}

    for candidate in candidates or []:
        gate = controlled_gate_for_candidate(
            candidate,
            games_df,
            activation_requested=active,
        )
        gates[_candidate_key(candidate)] = gate

    st.session_state[_GATE_CONTEXTS_KEY] = gates

    if not active:
        selected = base_selected
    else:
        eligible = [
            candidate
            for candidate in candidates or []
            if (gates.get(_candidate_key(candidate)) or {}).get("final_card_price_eligible") is True
        ]
        # Reuse the certified V2.1.7 selector unchanged. Step 5.9 only removes
        # price-ineligible candidates from its input; it does not alter score/order math.
        selected = v217._select_risk_aware(eligible, risks)

    blocked = sum(
        1
        for gate in gates.values()
        if gate.get("activation_requested") is True and gate.get("final_card_price_eligible") is False
    )
    st.session_state[_STATE_KEY] = {
        "data_type": "mlb_controlled_price_gate_presentation_v1",
        "schema_version": 1,
        "activation_env_key": _ENV_KEY,
        "activation_requested": active,
        "production_default_enabled": False,
        "certified_full_game_markets_only": True,
        "unpriced_player_props_passthrough": True,
        "candidate_gate_context_count": len(gates),
        "blocked_candidate_count": blocked,
        "base_selected_count": len(base_selected or []),
        "controlled_selected_count": len(selected or []),
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
    }
    return candidates, selected, snaps, baseline, ts, risks


def _gate_label(status: Any) -> str:
    return {
        "CONTROL_DISABLED": "⚪ PRICE GATE OFF",
        "CONTROL_DISABLED_UNVERIFIED_PRICE_CONTEXT": "⚪ PRICE GATE OFF • PRICE UNVERIFIED",
        "GATE_ALLOW": "🟢 PRICE GATE ALLOW",
        "GATE_BLOCK": "🔴 PRICE GATE BLOCK",
        "GATE_BLOCK_UNVERIFIED_PRICE_CONTEXT": "🔴 PRICE GATE BLOCK • UNVERIFIED",
        "NOT_APPLICABLE_UNPRICED_MARKET": "⚪ PRICE GATE N/A • PROP PASSTHROUGH",
    }.get(str(status or ""), "PRICE GATE")


def _gate_context_for_render(candidate: Mapping[str, Any], games_df) -> Mapping[str, Any] | None:
    cached = st.session_state.get(_GATE_CONTEXTS_KEY) or {}
    gate = cached.get(_candidate_key(candidate))
    if isinstance(gate, Mapping):
        return gate
    try:
        return controlled_gate_for_candidate(candidate, games_df)
    except Exception:
        return None


def _gate_board_html(context: Mapping[str, Any]) -> str:
    label = escape(_gate_label(context.get("gate_status")))
    reason = escape(str(context.get("gate_reason") or ""))
    active = "ON" if context.get("activation_requested") is True else "OFF"
    eligible = "YES" if context.get("final_card_price_eligible") is True else "NO"
    return (
        '<div style="border:1px solid #79414b;background:#160b0f;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#ffb4c0">CONTROLLED PRICE GATE • STEP 5.9</div>'
        f'<div style="font-size:8px;font-weight:900;color:#fff0f3">{label}</div>'
        f'<div style="font-size:8px;color:#ead3d8;font-weight:800">Activation {active} • price-eligible {eligible}</div>'
        f'<div style="font-size:7px;color:#c8a4ac">{reason}</div>'
        '<div style="font-size:7px;color:#a97f88">Eligibility filter only • model probability, Pick Strength, ranking math, risk logic, persistence, and wagering unchanged</div>'
        '</div>'
    )


def _decision_card_step5_9(c, rank, games_df, ts, snap, baseline, risk):
    html = step58._decision_card_step5_8(c, rank, games_df, ts, snap, baseline, risk)
    gate = _gate_context_for_render(c, games_df)
    if gate is None:
        return html
    board = _gate_board_html(gate)
    marker = '<div class="kui-score">'
    return html.replace(marker, board + marker, 1) if marker in html else html + board


def _why_sections_step5_9(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step58._why_sections_step5_8(c, games_df, snap, ts, baseline, risk)
    ]
    gate = _gate_context_for_render(c, games_df)
    if gate is None:
        line = "Step 5.9 controlled price-gate context is unavailable. No price-aware eligibility claim is fabricated."
    else:
        line = (
            f"Step 5.9 controlled price gate: {str(gate.get('gate_status') or '').replace('_', ' ').lower()}. "
            f"{str(gate.get('gate_reason') or '')} "
            "When enabled, this layer changes eligibility only; it never edits the production score or ranking math."
        )

    out = []
    inserted = False
    for title, lines in sections:
        if title == "🧠 Final decision":
            lines.append(line)
            inserted = True
        out.append((title, lines))
    if not inserted:
        out.append(("🧠 Final decision", [line]))
    return out


def install_controlled_price_gate_layer(games_df) -> dict[str, Any]:
    # Install Step 5.8 first so all certified price-health/shadow presentation remains.
    shadow_state = step58.install_actionability_shadow_layer(games_df)
    v217._all_live_context = _all_live_context_step5_9
    v217._decision_card_v217 = _decision_card_step5_9
    v217._why_sections = _why_sections_step5_9

    state = dict(st.session_state.get(_STATE_KEY) or {})
    if not state:
        state = {
            "data_type": "mlb_controlled_price_gate_presentation_v1",
            "schema_version": 1,
            "activation_env_key": _ENV_KEY,
            "activation_requested": price_gate_activation_requested(),
            "production_default_enabled": False,
            "certified_full_game_markets_only": True,
            "unpriced_player_props_passthrough": True,
            "candidate_gate_context_count": 0,
            "blocked_candidate_count": 0,
            "model_math_impact": False,
            "pick_strength_impact": False,
            "ranking_math_impact": False,
            "risk_logic_impact": False,
            "wagering_impact": False,
            "durable_persistence": False,
        }
        st.session_state[_STATE_KEY] = state
    state["step5_8_available"] = bool(shadow_state.get("step5_7_available"))
    return state


__all__ = [
    "VERSION",
    "controlled_gate_for_candidate",
    "install_controlled_price_gate_layer",
    "price_gate_activation_requested",
]
