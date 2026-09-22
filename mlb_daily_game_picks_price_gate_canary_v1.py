"""Step 5.10 bounded canary rollout controller for the Step 5.9 MLB price gate.

The canary is OFF and 0% by default. When explicitly enabled, a deterministic
cohort of at most 25% of priced official MLB game IDs receives the already-certified
Step 5.9 eligibility gate. Non-enrolled games and unpriced player props preserve
existing behavior. Setting the canary back to OFF or 0% is an exact rollback.

This module does not itself configure an external Streamlit/hosting environment;
it only provides the certified runtime control boundary once those environment
variables are supplied by the actual app host.
"""
from __future__ import annotations

from html import escape
import os
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_controlled_price_gate_v1 as step59
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_price_gate_canary_v1 import (
    MAX_CANARY_PERCENT,
    game_is_in_canary,
    select_canary_game_ids,
)

VERSION = "MLB DAILY PICKS STEP 5.10 • BOUNDED PRICE-GATE CANARY"
_STATE_KEY = "mlb_step5_10_price_gate_canary_v1"
_CANARY_ENABLED_KEY = "MLB_STEP5_10_CANARY_ENABLED"
_CANARY_PERCENT_KEY = "MLB_STEP5_10_CANARY_PERCENT"
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}


def canary_rollout_config() -> dict[str, Any]:
    enabled = str(os.getenv(_CANARY_ENABLED_KEY, "0") or "0").strip().lower() in _TRUE_VALUES
    raw_percent = str(os.getenv(_CANARY_PERCENT_KEY, "0") or "0").strip()
    try:
        requested_percent = float(raw_percent)
        config_valid = True
    except Exception:
        requested_percent = 0.0
        config_valid = False
        enabled = False
    return {
        "enabled": enabled,
        "requested_percent": requested_percent,
        "config_valid": config_valid,
        "enabled_env_key": _CANARY_ENABLED_KEY,
        "percent_env_key": _CANARY_PERCENT_KEY,
        "production_default_enabled": False,
        "production_default_percent": 0.0,
    }


def _safe_game_id(candidate: Mapping[str, Any]) -> int | None:
    value = candidate.get("game_pk")
    if isinstance(value, bool):
        return None
    try:
        game_id = int(value)
    except Exception:
        return None
    return game_id if game_id > 0 else None


def _candidate_key(candidate: Mapping[str, Any]):
    return v217._candidate_key(candidate)


def _all_live_context_step5_10(games_df):
    config = canary_rollout_config()
    global_gate_active = step59.price_gate_activation_requested()

    # If the older global Step 5.9 switch is deliberately enabled, preserve that
    # certified full-rollout behavior. Step 5.10 never silently downscopes it.
    if global_gate_active:
        result = step59._all_live_context_step5_9(games_df)
        state = {
            "data_type": "mlb_price_gate_canary_presentation_v1",
            "schema_version": 1,
            **config,
            "global_step5_9_gate_active": True,
            "canary_applied": False,
            "mode": "GLOBAL_STEP5_9_GATE_PRECEDENCE",
            "effective_percent": 0.0,
            "selected_game_ids": [],
            "selected_game_count": 0,
            "blocked_candidate_count": int((st.session_state.get(step59._STATE_KEY) or {}).get("blocked_candidate_count") or 0),
            "exact_rollback_available": True,
            "external_host_activation_verified": False,
            "model_math_impact": False,
            "pick_strength_impact": False,
            "ranking_math_impact": False,
            "risk_logic_impact": False,
            "wagering_impact": False,
            "durable_persistence": False,
        }
        st.session_state[_STATE_KEY] = state
        return result

    candidates, base_selected, snaps, baseline, ts, risks = step59._BASE_ALL_LIVE_CONTEXT(games_df)
    candidates = list(candidates or [])
    priced_game_ids = [
        game_id
        for candidate in candidates
        if str(candidate.get("market") or "") in step59.SUPPORTED_MARKETS
        for game_id in [_safe_game_id(candidate)]
        if game_id is not None
    ]

    cohort = select_canary_game_ids(
        priced_game_ids,
        enabled=bool(config["enabled"] and config["config_valid"]),
        requested_percent=config["requested_percent"],
    )
    selected_games = set(cohort["selected_game_ids"])
    canary_applied = bool(selected_games)
    gates: dict[Any, dict[str, Any]] = {}

    for candidate in candidates:
        game_id = _safe_game_id(candidate)
        market = str(candidate.get("market") or "")
        enrolled = bool(
            market in step59.SUPPORTED_MARKETS
            and game_id is not None
            and game_id in selected_games
        )
        gate = step59.controlled_gate_for_candidate(
            candidate,
            games_df,
            activation_requested=enrolled,
        )
        gate = dict(gate)
        gate["step5_10_canary_enrolled"] = enrolled
        gate["step5_10_canary_effective_percent"] = cohort["effective_percent"]
        gates[_candidate_key(candidate)] = gate

    # Reuse Step 5.9's cache key so its certified card/explanation renderer shows
    # the exact per-candidate gate result chosen by this canary controller.
    st.session_state[step59._GATE_CONTEXTS_KEY] = gates

    blocked = sum(
        1
        for gate in gates.values()
        if gate.get("step5_10_canary_enrolled") is True
        and gate.get("final_card_price_eligible") is False
    )

    if not canary_applied:
        # Exact rollback/pass-through path: do not even rerun selection.
        selected = base_selected
    else:
        eligible = [
            candidate
            for candidate in candidates
            if (gates.get(_candidate_key(candidate)) or {}).get("final_card_price_eligible") is True
        ]
        selected = v217._select_risk_aware(eligible, risks)

    state = {
        "data_type": "mlb_price_gate_canary_presentation_v1",
        "schema_version": 1,
        **config,
        "global_step5_9_gate_active": False,
        "canary_applied": canary_applied,
        "mode": "BOUNDED_CANARY" if canary_applied else "CANARY_OFF_EXACT_PASSTHROUGH",
        "effective_percent": cohort["effective_percent"],
        "percent_bounded": cohort["percent_bounded"],
        "max_canary_percent": MAX_CANARY_PERCENT,
        "priced_game_count": cohort["official_game_count"],
        "selected_game_ids": list(cohort["selected_game_ids"]),
        "selected_game_count": cohort["selected_game_count"],
        "realized_percent": cohort["realized_percent"],
        "candidate_gate_context_count": len(gates),
        "blocked_candidate_count": blocked,
        "base_selected_count": len(base_selected or []),
        "canary_selected_count": len(selected or []),
        "game_level_atomicity": True,
        "deterministic_assignment": True,
        "unpriced_player_props_passthrough": True,
        "exact_rollback_available": True,
        "external_host_activation_verified": False,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
    }
    st.session_state[_STATE_KEY] = state
    return candidates, selected, snaps, baseline, ts, risks


def _canary_context_for_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(st.session_state.get(_STATE_KEY) or {})
    game_id = _safe_game_id(candidate)
    market = str(candidate.get("market") or "")
    selected_games = set(state.get("selected_game_ids") or [])
    enrolled = bool(
        state.get("canary_applied") is True
        and market in step59.SUPPORTED_MARKETS
        and game_id is not None
        and game_id in selected_games
    )
    return {**state, "candidate_canary_enrolled": enrolled, "candidate_market": market}


def _canary_label(context: Mapping[str, Any]) -> str:
    if context.get("global_step5_9_gate_active") is True:
        return "🟣 GLOBAL STEP 5.9 GATE HAS PRECEDENCE"
    if context.get("candidate_market") not in step59.SUPPORTED_MARKETS:
        return "⚪ CANARY N/A • PROP PASSTHROUGH"
    if context.get("candidate_canary_enrolled") is True:
        return "🟢 CANARY ENROLLED"
    if context.get("canary_applied") is True:
        return "⚪ NOT IN CANARY COHORT"
    return "⚪ CANARY OFF • EXACT PASSTHROUGH"


def _canary_board_html(context: Mapping[str, Any]) -> str:
    label = escape(_canary_label(context))
    effective = float(context.get("effective_percent") or 0.0)
    realized = float(context.get("realized_percent") or 0.0)
    count = int(context.get("selected_game_count") or 0)
    priced = int(context.get("priced_game_count") or 0)
    return (
        '<div style="border:1px solid #5a477e;background:#100b19;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#ceb9ff">BOUNDED CANARY • STEP 5.10</div>'
        f'<div style="font-size:8px;font-weight:900;color:#f2eaff">{label}</div>'
        f'<div style="font-size:8px;color:#d8caef;font-weight:800">Effective cap {effective:.1f}% • realized {realized:.1f}% • {count}/{priced} priced games</div>'
        '<div style="font-size:7px;color:#ae9acb">Game-level deterministic cohort • OFF/0% is exact rollback • host activation not inferred</div>'
        '<div style="font-size:7px;color:#9481b0">No model, Pick Strength, ranking-math, risk, persistence, or wagering changes</div>'
        '</div>'
    )


def _decision_card_step5_10(c, rank, games_df, ts, snap, baseline, risk):
    html = step59._decision_card_step5_9(c, rank, games_df, ts, snap, baseline, risk)
    board = _canary_board_html(_canary_context_for_candidate(c))
    marker = '<div class="kui-score">'
    return html.replace(marker, board + marker, 1) if marker in html else html + board


def _why_sections_step5_10(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step59._why_sections_step5_9(c, games_df, snap, ts, baseline, risk)
    ]
    context = _canary_context_for_candidate(c)
    if context.get("global_step5_9_gate_active") is True:
        line = "Step 5.10 canary does not downscope an explicitly enabled global Step 5.9 gate; the global gate has precedence."
    elif context.get("candidate_market") not in step59.SUPPORTED_MARKETS:
        line = "Step 5.10 does not canary-gate this player market because no certified exact prop-price feed exists; existing eligibility passes through unchanged."
    elif context.get("candidate_canary_enrolled") is True:
        line = "Step 5.10 enrolled this official game ID in the deterministic bounded canary, so its certified Step 5.9 gate can affect Final Card eligibility."
    else:
        line = "Step 5.10 did not enroll this candidate's official game ID; its existing Final Card eligibility is unchanged."

    line += " OFF/0% is an exact rollback path, and this code does not claim an external host environment has been activated."
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


def install_price_gate_canary_layer(games_df) -> dict[str, Any]:
    step59.install_controlled_price_gate_layer(games_df)
    v217._all_live_context = _all_live_context_step5_10
    v217._decision_card_v217 = _decision_card_step5_10
    v217._why_sections = _why_sections_step5_10

    state = dict(st.session_state.get(_STATE_KEY) or {})
    if not state:
        config = canary_rollout_config()
        state = {
            "data_type": "mlb_price_gate_canary_presentation_v1",
            "schema_version": 1,
            **config,
            "global_step5_9_gate_active": step59.price_gate_activation_requested(),
            "canary_applied": False,
            "mode": "CANARY_OFF_EXACT_PASSTHROUGH",
            "effective_percent": 0.0,
            "selected_game_ids": [],
            "selected_game_count": 0,
            "external_host_activation_verified": False,
            "exact_rollback_available": True,
            "model_math_impact": False,
            "pick_strength_impact": False,
            "ranking_math_impact": False,
            "risk_logic_impact": False,
            "wagering_impact": False,
            "durable_persistence": False,
        }
        st.session_state[_STATE_KEY] = state
    return state


__all__ = [
    "VERSION",
    "canary_rollout_config",
    "install_price_gate_canary_layer",
]
