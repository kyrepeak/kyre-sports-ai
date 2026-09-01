"""Step 6G graduated-production presentation and runtime status layer.

The active Step 6D 25% rollout remains unchanged. This wrapper consumes the
certified Step 6F graduation permission, retires the canary label when the
existing Step 6D configuration is healthy at 25%, and preserves the same cohort,
gate, rollback, and selection behavior.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_price_gate_canary_v1 as step510
import mlb_daily_game_picks_step6d_production_expansion_v1 as step6d
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_step6g_controlled_graduation_v1 import (
    CERTIFIED_STEP6F_DECISION,
    MAX_GRADUATED_PRODUCTION_PERCENT,
    STEP6F_CERTIFICATION_MARKER,
    STEP6F_CERTIFICATION_RUN_ID,
    STEP6F_CERTIFIED_MAIN_SHA,
    resolve_step6g_controlled_graduation,
)

VERSION = "MLB DAILY PICKS STEP 6G • CONTROLLED PRODUCTION GRADUATION"
_STATE_KEY = "mlb_step6g_controlled_graduation_v1"


def step6g_graduation_config() -> dict[str, Any]:
    step6d_config = step6d.step6d_rollout_config()
    return {
        **step6d_config,
        **resolve_step6g_controlled_graduation(
            step6d_config,
            permission=CERTIFIED_STEP6F_DECISION,
        ),
    }


def _context_for_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    config = step6g_graduation_config()
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
        "candidate_step6g_enrolled": enrolled,
    }


def _board_html(context: Mapping[str, Any]) -> str:
    source = str(context.get("control_source") or context.get("step6d_control_source") or "")
    graduated = context.get("graduated_production_active") is True
    market = str(context.get("candidate_market") or "")
    if source == "GLOBAL_KILL_SWITCH":
        label = "⛔ GLOBAL KILL SWITCH • EXACT STEP 5 PASSTHROUGH"
    elif source == "STREAMLIT_SESSION_ROLLBACK":
        label = "↩️ SESSION ROLLBACK • EXACT STEP 5 PASSTHROUGH"
    elif market not in step510.step59.SUPPORTED_MARKETS:
        label = "⚪ PLAYER PROP • PRICE GATE NOT APPLICABLE"
    elif not graduated:
        label = "🟡 GRADUATION HOLD • 25% CANARY STATUS RETAINED"
    elif context.get("candidate_step6g_enrolled") is True:
        label = "🟢 GRADUATED PRODUCTION • CERTIFIED 25% COHORT"
    elif context.get("canary_applied") is True:
        label = "⚪ GRADUATED PRODUCTION • OUTSIDE 25% COHORT"
    else:
        label = "⚪ GRADUATED PRODUCTION • NO GAME ENROLLED AT CURRENT SLATE SIZE"

    effective = float(context.get("effective_percent") or context.get("step6d_effective_percent") or 0.0)
    realized = float(context.get("realized_percent") or 0.0)
    count = int(context.get("selected_game_count") or 0)
    priced = int(context.get("priced_game_count") or 0)
    permission_ok = bool(context.get("step6f_permission_valid"))
    return (
        '<div style="border:1px solid #2f7d5a;background:#071811;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#7af0b5">STEP 6G • CONTROLLED PRODUCTION GRADUATION</div>'
        f'<div style="font-size:8px;font-weight:900;color:#ecfff5">{escape(label)}</div>'
        f'<div style="font-size:8px;color:#bdebd3;font-weight:800">Exposure unchanged at {effective:.1f}% • realized {realized:.1f}% • {count}/{priced} priced games</div>'
        f'<div style="font-size:7px;color:#8fd2ae">Step 6F graduation permission: {"GREEN" if permission_ok else "HOLD"} • hard cap {MAX_GRADUATED_PRODUCTION_PERCENT:.0f}%</div>'
        f'<div style="font-size:7px;color:#78b997">Certified graduation run {STEP6F_CERTIFICATION_RUN_ID} • {escape(STEP6F_CERTIFICATION_MARKER)}</div>'
        '<div style="font-size:7px;color:#6fa98c">Step 6D kill switch and ?mlb_step6d_rollback=1 remain active</div>'
        '<div style="font-size:7px;color:#608f78">Same Step 5.10 cohort and Step 5.9 eligibility gate • no projection, ranking, or risk changes</div>'
        '</div>'
    )


def _decision_card_step6g(c, rank, games_df, ts, snap, baseline, risk):
    html = step510._decision_card_step5_10(c, rank, games_df, ts, snap, baseline, risk)
    board = _board_html(_context_for_candidate(c))
    marker = '<div class="kui-score">'
    return html.replace(marker, board + marker, 1) if marker in html else html + board


def _why_sections_step6g(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step510._why_sections_step5_10(c, games_df, snap, ts, baseline, risk)
    ]
    context = _context_for_candidate(c)
    source = str(context.get("control_source") or context.get("step6d_control_source") or "")
    if source == "GLOBAL_KILL_SWITCH":
        line = "Step 6G graduation remains certified, but the Step 6D global kill switch currently forces exact Step 5 pass-through."
    elif source == "STREAMLIT_SESSION_ROLLBACK":
        line = "Step 6G graduation remains certified, but this Streamlit session is explicitly rolled back to exact Step 5 pass-through."
    elif context.get("candidate_market") not in step510.step59.SUPPORTED_MARKETS:
        line = "Step 6G does not change player-prop handling; this market remains outside the full-game price-gate cohort."
    elif context.get("graduated_production_active") is not True:
        line = "Step 6G refused to retire canary status because the Step 6F graduation permission or Step 6D runtime contract was not healthy. Exposure remains unchanged."
    elif context.get("candidate_step6g_enrolled") is True:
        line = "Step 6G has graduated the existing 25% cohort from canary status. This official MLB game ID remains in the same deterministic Step 5.10 cohort, so the same Step 5.9 eligibility gate applies."
    else:
        line = "Step 6G has graduated the 25% production cohort, but this game is outside the current deterministic cohort and therefore passes through unchanged."
    line += " Graduation changes status only; the 25% cap, exact rollback, selection logic, and protected model behavior are unchanged."

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


def install_step6g_controlled_graduation_layer(games_df) -> dict[str, Any]:
    step6d_state = step6d.install_step6d_production_expansion_layer(games_df)
    v217._decision_card_v217 = _decision_card_step6g
    v217._why_sections = _why_sections_step6g

    config = step6g_graduation_config()
    state = {
        "data_type": "mlb_step6g_controlled_graduation_presentation_v1",
        "schema_version": 1,
        **config,
        "step6f_permission_consumed": True,
        "step6f_certified_main_sha": STEP6F_CERTIFIED_MAIN_SHA,
        "step6f_certification_run_id": STEP6F_CERTIFICATION_RUN_ID,
        "step6f_certification_marker": STEP6F_CERTIFICATION_MARKER,
        "step6d_layer_available": bool(step6d_state.get("data_type")),
        "production_exposure_changed": False,
        "same_step5_10_cohort": True,
        "same_step5_9_gate": True,
        "exact_session_rollback": True,
        "global_kill_switch_available": True,
        "player_props_passthrough": True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wnba_impact": False,
    }
    st.session_state[_STATE_KEY] = state
    return state


__all__ = [
    "VERSION",
    "install_step6g_controlled_graduation_layer",
    "step6g_graduation_config",
]
