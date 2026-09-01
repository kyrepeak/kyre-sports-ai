"""Step 6A production activation wrapper for the frozen Step 5 MLB price gate.

This is the first intentionally active production phase after the Step 5.11
freeze. It reuses the certified Step 5.10 game-atomic cohort and Step 5.9 gate,
but supplies a repository production default of ON at 10%. Step 6A never exceeds
10% even though the underlying Step 5.10 controller has a 25% absolute cap.

A host kill switch or explicit host setting can override the repository default.
The query parameter ``mlb_step6a_rollback=1`` provides an exact browser-session
rollback to the Step 5 pass-through path for verification/recovery.
"""
from __future__ import annotations

from html import escape
import os
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_price_gate_canary_v1 as step510
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_step6a_production_canary_v1 import (
    ENABLED_ENV_KEY,
    KILL_SWITCH_ENV_KEY,
    MAX_PRODUCTION_CANARY_PERCENT,
    PERCENT_ENV_KEY,
    ROLLBACK_QUERY_KEY,
    resolve_step6a_production_canary,
)

VERSION = "MLB DAILY PICKS STEP 6A • CONTROLLED PRODUCTION CANARY"
_STATE_KEY = "mlb_step6a_production_canary_v1"


def _query_value(key: str) -> str | None:
    try:
        value = st.query_params.get(key)
    except Exception:
        return None
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else None
    if value is None:
        return None
    return str(value).strip()


def _rollback_requested() -> bool:
    value = str(_query_value(ROLLBACK_QUERY_KEY) or "").strip().lower()
    return value in {"1", "true", "yes", "on", "rollback"}


def step6a_rollout_config() -> dict[str, Any]:
    resolved = resolve_step6a_production_canary(
        os.environ,
        rollback_requested=_rollback_requested(),
    )
    return {
        **resolved,
        "enabled_env_key": ENABLED_ENV_KEY,
        "percent_env_key": PERCENT_ENV_KEY,
        "kill_switch_env_key": KILL_SWITCH_ENV_KEY,
        "rollback_query_key": ROLLBACK_QUERY_KEY,
    }


def _context_for_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    config = step6a_rollout_config()
    step5_state = dict(st.session_state.get(step510._STATE_KEY) or {})
    game_id = step510._safe_game_id(candidate)
    selected = set(step5_state.get("selected_game_ids") or [])
    market = str(candidate.get("market") or "")
    enrolled = bool(
        step5_state.get("canary_applied") is True
        and market in step510.step59.SUPPORTED_MARKETS
        and game_id is not None
        and game_id in selected
    )
    return {
        **config,
        **step5_state,
        "candidate_game_id": game_id,
        "candidate_market": market,
        "candidate_step6a_enrolled": enrolled,
    }


def _board_html(context: Mapping[str, Any]) -> str:
    source = str(context.get("control_source") or "REPOSITORY_PRODUCTION_DEFAULT")
    if source == "GLOBAL_KILL_SWITCH":
        label = "⛔ GLOBAL KILL SWITCH • ROLLED BACK"
    elif source == "STREAMLIT_SESSION_ROLLBACK":
        label = "↩️ SESSION ROLLBACK • STEP 5 PASSTHROUGH"
    elif context.get("candidate_market") not in step510.step59.SUPPORTED_MARKETS:
        label = "⚪ PLAYER PROP • PRICE GATE NOT APPLICABLE"
    elif context.get("candidate_step6a_enrolled") is True:
        label = "🟢 LIVE STEP 6A PRODUCTION CANARY"
    elif context.get("canary_applied") is True:
        label = "⚪ OUTSIDE STEP 6A COHORT"
    else:
        label = "⚪ NO GAME ENROLLED AT CURRENT SLATE SIZE"

    effective = float(context.get("effective_percent") or 0.0)
    realized = float(context.get("realized_percent") or 0.0)
    count = int(context.get("selected_game_count") or 0)
    priced = int(context.get("priced_game_count") or 0)
    return (
        '<div style="border:1px solid #7a5d1d;background:#1b1405;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#ffd56a">STEP 6A • CONTROLLED PRODUCTION ACTIVATION</div>'
        f'<div style="font-size:8px;font-weight:900;color:#fff3ce">{escape(label)}</div>'
        f'<div style="font-size:8px;color:#ead9a9;font-weight:800">Configured {effective:.1f}% • realized {realized:.1f}% • {count}/{priced} priced games</div>'
        f'<div style="font-size:7px;color:#cdbb8c">Control source: {escape(source)} • hard Step 6A cap {MAX_PRODUCTION_CANARY_PERCENT:.0f}%</div>'
        '<div style="font-size:7px;color:#a99568">Exact session rollback: ?mlb_step6a_rollback=1 • host kill switch supported</div>'
        '<div style="font-size:7px;color:#8d7a52">Step 5 gate math reused unchanged • no model, Pick Strength, ranking, risk, persistence, wagering, or WNBA changes</div>'
        '</div>'
    )


def _decision_card_step6a(c, rank, games_df, ts, snap, baseline, risk):
    html = step510._decision_card_step5_10(c, rank, games_df, ts, snap, baseline, risk)
    board = _board_html(_context_for_candidate(c))
    marker = '<div class="kui-score">'
    return html.replace(marker, board + marker, 1) if marker in html else html + board


def _why_sections_step6a(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step510._why_sections_step5_10(c, games_df, snap, ts, baseline, risk)
    ]
    context = _context_for_candidate(c)
    source = str(context.get("control_source") or "REPOSITORY_PRODUCTION_DEFAULT")
    if source == "GLOBAL_KILL_SWITCH":
        line = "Step 6A global kill switch is active, so Final Card eligibility is on the exact Step 5 pass-through rollback path."
    elif source == "STREAMLIT_SESSION_ROLLBACK":
        line = "Step 6A is rolled back for this Streamlit session; removing the rollback query returns to the controlled production canary."
    elif context.get("candidate_market") not in step510.step59.SUPPORTED_MARKETS:
        line = "Step 6A still excludes player props from price gating because no certified exact prop-price feed exists."
    elif context.get("candidate_step6a_enrolled") is True:
        line = "Step 6A enrolled this official MLB game ID in the live bounded production cohort, so the frozen Step 5.9 price gate may affect Final Card eligibility."
    else:
        line = "Step 6A did not enroll this game in the current production cohort, so its Step 5 Final Card eligibility passes through unchanged."
    line += " The Step 6A production rollout is capped at 10% and reuses the frozen Step 5 gate and selector math unchanged."

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


def install_step6a_production_canary_layer(games_df) -> dict[str, Any]:
    # Supply only a new activation policy to the certified Step 5.10 controller.
    # Cohort hashing, Step 5.9 gate behavior, and V2.1.7 selector math stay frozen.
    step510.canary_rollout_config = step6a_rollout_config
    step5_state = step510.install_price_gate_canary_layer(games_df)
    v217._decision_card_v217 = _decision_card_step6a
    v217._why_sections = _why_sections_step6a

    config = step6a_rollout_config()
    state = {
        "data_type": "mlb_step6a_production_canary_presentation_v1",
        "schema_version": 1,
        **config,
        "production_activation_intent": bool(config.get("enabled")),
        "step5_10_controller_reused": True,
        "step5_9_gate_reused": True,
        "max_production_canary_percent": MAX_PRODUCTION_CANARY_PERCENT,
        "exact_session_rollback": True,
        "global_kill_switch_available": True,
        "player_props_passthrough": True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
        "step5_10_available": bool(step5_state.get("data_type")),
    }
    st.session_state[_STATE_KEY] = state
    return state


__all__ = [
    "VERSION",
    "install_step6a_production_canary_layer",
    "step6a_rollout_config",
]
