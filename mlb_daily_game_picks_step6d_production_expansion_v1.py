"""Step 6D controlled 25% production activation wrapper.

Consumes the certified Step 6C expansion permission and supplies a bounded 25%
production rollout policy to the frozen Step 5.10 cohort controller. The
underlying deterministic game hashing, Step 5.9 price gate, V2.1.7 selector,
model math, Pick Strength, ranking, risk logic, player-prop passthrough, and WNBA
behavior remain unchanged.
"""
from __future__ import annotations

from html import escape
import os
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_price_gate_canary_v1 as step510
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_step6d_production_expansion_v1 import (
    CERTIFIED_STEP6C_PERMISSION,
    ENABLED_ENV_KEY,
    KILL_SWITCH_ENV_KEY,
    MAX_PRODUCTION_CANARY_PERCENT,
    PERCENT_ENV_KEY,
    ROLLBACK_QUERY_KEY,
    STEP6C_CERTIFICATION_MARKER,
    STEP6C_CERTIFICATION_RUN_ID,
    STEP6C_CERTIFIED_MAIN_SHA,
    resolve_step6d_production_expansion,
)

VERSION = "MLB DAILY PICKS STEP 6D • CONTROLLED 25% PRODUCTION EXPANSION"
_STATE_KEY = "mlb_step6d_production_expansion_v1"


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


def step6d_rollout_config() -> dict[str, Any]:
    resolved = resolve_step6d_production_expansion(
        os.environ,
        rollback_requested=_rollback_requested(),
        permission=CERTIFIED_STEP6C_PERMISSION,
    )
    return {
        **resolved,
        "enabled_env_key": ENABLED_ENV_KEY,
        "percent_env_key": PERCENT_ENV_KEY,
        "kill_switch_env_key": KILL_SWITCH_ENV_KEY,
        "rollback_query_key": ROLLBACK_QUERY_KEY,
    }


def _context_for_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    config = step6d_rollout_config()
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
        "candidate_step6d_enrolled": enrolled,
    }


def _board_html(context: Mapping[str, Any]) -> str:
    source = str(context.get("control_source") or "REPOSITORY_PRODUCTION_DEFAULT")
    if source == "GLOBAL_KILL_SWITCH":
        label = "⛔ GLOBAL KILL SWITCH • EXACT STEP 5 PASSTHROUGH"
    elif source == "STREAMLIT_SESSION_ROLLBACK":
        label = "↩️ SESSION ROLLBACK • EXACT STEP 5 PASSTHROUGH"
    elif source == "STEP6C_PERMISSION_HOLD":
        label = "🟡 EXPANSION HELD • STEP 6C PERMISSION NOT VALID"
    elif context.get("candidate_market") not in step510.step59.SUPPORTED_MARKETS:
        label = "⚪ PLAYER PROP • PRICE GATE NOT APPLICABLE"
    elif context.get("candidate_step6d_enrolled") is True:
        label = "🟢 LIVE STEP 6D • 25% PRODUCTION COHORT"
    elif context.get("canary_applied") is True:
        label = "⚪ OUTSIDE STEP 6D COHORT"
    else:
        label = "⚪ NO GAME ENROLLED AT CURRENT SLATE SIZE"

    effective = float(context.get("effective_percent") or 0.0)
    realized = float(context.get("realized_percent") or 0.0)
    count = int(context.get("selected_game_count") or 0)
    priced = int(context.get("priced_game_count") or 0)
    permission_ok = bool(context.get("step6c_permission_valid"))
    return (
        '<div style="border:1px solid #2f7d5a;background:#071811;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#7af0b5">STEP 6D • CONTROLLED 25% PRODUCTION EXPANSION</div>'
        f'<div style="font-size:8px;font-weight:900;color:#ecfff5">{escape(label)}</div>'
        f'<div style="font-size:8px;color:#bdebd3;font-weight:800">Configured {effective:.1f}% • realized {realized:.1f}% • {count}/{priced} priced games</div>'
        f'<div style="font-size:7px;color:#8fd2ae">Step 6C permission: {"GREEN" if permission_ok else "HOLD"} • hard cap {MAX_PRODUCTION_CANARY_PERCENT:.0f}%</div>'
        f'<div style="font-size:7px;color:#78b997">Certified gate run {STEP6C_CERTIFICATION_RUN_ID} • {escape(STEP6C_CERTIFICATION_MARKER)}</div>'
        '<div style="font-size:7px;color:#6fa98c">Exact session rollback: ?mlb_step6d_rollback=1 • global kill switch supported</div>'
        '<div style="font-size:7px;color:#608f78">Frozen Step 5 gate/selector reused • no model, Pick Strength, ranking, risk, persistence, wagering, prop-price, or WNBA changes</div>'
        '</div>'
    )


def _decision_card_step6d(c, rank, games_df, ts, snap, baseline, risk):
    html = step510._decision_card_step5_10(c, rank, games_df, ts, snap, baseline, risk)
    board = _board_html(_context_for_candidate(c))
    marker = '<div class="kui-score">'
    return html.replace(marker, board + marker, 1) if marker in html else html + board


def _why_sections_step6d(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step510._why_sections_step5_10(c, games_df, snap, ts, baseline, risk)
    ]
    context = _context_for_candidate(c)
    source = str(context.get("control_source") or "REPOSITORY_PRODUCTION_DEFAULT")
    if source == "GLOBAL_KILL_SWITCH":
        line = "Step 6D global kill switch is active, so Final Card price eligibility is on the exact Step 5 pass-through path."
    elif source == "STREAMLIT_SESSION_ROLLBACK":
        line = "Step 6D is rolled back for this Streamlit session; removing the rollback query returns to the controlled 25% production cohort."
    elif source == "STEP6C_PERMISSION_HOLD":
        line = "Step 6D refused expansion because the Step 6C permission contract was not valid, so exposure remains at the certified 10% baseline."
    elif context.get("candidate_market") not in step510.step59.SUPPORTED_MARKETS:
        line = "Step 6D still excludes player props from price gating because no certified exact player-prop price feed exists."
    elif context.get("candidate_step6d_enrolled") is True:
        line = "Step 6D enrolled this official MLB game ID in the live 25% production cohort after the GREEN Step 6C evidence gate, so the frozen Step 5.9 price gate may affect Final Card eligibility."
    else:
        line = "Step 6D did not enroll this game in the current 25% production cohort, so its Step 5 Final Card eligibility passes through unchanged."
    line += " The rollout remains game-atomic, deterministic, capped at 25%, and preserves exact rollback."

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


def install_step6d_production_expansion_layer(games_df) -> dict[str, Any]:
    # Only the activation policy changes here. Step 5.10 still owns cohort
    # hashing and Step 5.9 still owns gate eligibility; V2.1.7 still owns
    # selection/risk behavior.
    step510.canary_rollout_config = step6d_rollout_config
    step5_state = step510.install_price_gate_canary_layer(games_df)
    v217._decision_card_v217 = _decision_card_step6d
    v217._why_sections = _why_sections_step6d

    config = step6d_rollout_config()
    state = {
        "data_type": "mlb_step6d_production_expansion_presentation_v1",
        "schema_version": 1,
        **config,
        "production_activation_intent": bool(config.get("enabled")),
        "step6c_permission_consumed": True,
        "step6c_certified_main_sha": STEP6C_CERTIFIED_MAIN_SHA,
        "step6c_certification_run_id": STEP6C_CERTIFICATION_RUN_ID,
        "step6c_certification_marker": STEP6C_CERTIFICATION_MARKER,
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
    "install_step6d_production_expansion_layer",
    "step6d_rollout_config",
]
