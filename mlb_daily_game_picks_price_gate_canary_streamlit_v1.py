"""Step 5.10B session-scoped Streamlit control for the certified MLB canary.

Step 5.10 intentionally ships with host environment defaults OFF/0%. The public
Streamlit frontend does not expose the Render control surface used by the backend,
so Step 5.10B adds a narrowly scoped fallback for live verification: an explicit
URL query can arm the already-certified Step 5.10 canary for that Streamlit
browser session only.

Host environment variables always take precedence when they are explicitly
present. Query control never changes model math, Pick Strength, ranking math,
risk logic, persistence, wagering, WNBA behavior, or the 25% Step 5.10 cap.
Removing the query parameters is an exact session rollback to the underlying
Step 5.10 host/default configuration.
"""
from __future__ import annotations

from html import escape
import os
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_price_gate_canary_v1 as step510
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_streamlit_canary_control_v1 import (
    QUERY_ENABLED_KEY,
    QUERY_PERCENT_KEY,
    resolve_streamlit_canary_config,
)

VERSION = "MLB DAILY PICKS STEP 5.10B • STREAMLIT SESSION CANARY CONTROL"
_STATE_KEY = "mlb_step5_10b_streamlit_session_canary_v1"
_BASE_CONFIG = step510.canary_rollout_config
_BASE_DECISION = step510._decision_card_step5_10
_BASE_WHY = step510._why_sections_step5_10


def _host_env_present() -> bool:
    return any(
        key in os.environ
        for key in (
            step510._CANARY_ENABLED_KEY,
            step510._CANARY_PERCENT_KEY,
        )
    )


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


def streamlit_canary_rollout_config() -> dict[str, Any]:
    return resolve_streamlit_canary_config(
        _BASE_CONFIG(),
        host_env_present=_host_env_present(),
        query_enabled_value=_query_value(QUERY_ENABLED_KEY),
        query_percent_value=_query_value(QUERY_PERCENT_KEY),
    )


def _session_context_for_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(st.session_state.get(step510._STATE_KEY) or {})
    game_id = step510._safe_game_id(candidate)
    selected = set(state.get("selected_game_ids") or [])
    market = str(candidate.get("market") or "")
    return {
        **state,
        "candidate_game_id": game_id,
        "candidate_market": market,
        "candidate_session_canary_enrolled": bool(
            state.get("control_source") == "STREAMLIT_QUERY_SESSION"
            and state.get("canary_applied") is True
            and game_id is not None
            and game_id in selected
        ),
    }


def _session_board_html(context: Mapping[str, Any]) -> str:
    source = str(context.get("control_source") or "DEFAULT_OFF")
    if source == "HOST_ENV":
        label = "HOST ENV CONTROL HAS PRECEDENCE"
    elif context.get("query_param_activation_requested") is True:
        label = "LIVE STREAMLIT SESSION CANARY ARMED"
    elif source == "STREAMLIT_QUERY_SESSION":
        label = "STREAMLIT SESSION CANARY OFF"
    else:
        label = "SESSION CONTROL IDLE • DEFAULT OFF"

    enrolled = "YES" if context.get("candidate_session_canary_enrolled") is True else "NO"
    effective = float(context.get("effective_percent") or 0.0)
    realized = float(context.get("realized_percent") or 0.0)
    return (
        '<div style="border:1px solid #2f6d6a;background:#071716;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#8be4dd">STREAMLIT SESSION CANARY • STEP 5.10B</div>'
        f'<div style="font-size:8px;font-weight:900;color:#e7fffd">{escape(label)}</div>'
        f'<div style="font-size:8px;color:#c1e8e5;font-weight:800">Effective {effective:.1f}% • realized {realized:.1f}% • this game enrolled {enrolled}</div>'
        '<div style="font-size:7px;color:#96c9c5">Session/query scoped only • remove query parameters for exact rollback • host env wins if configured</div>'
        '<div style="font-size:7px;color:#79aaa6">No model, Pick Strength, ranking-math, risk, persistence, wagering, or WNBA changes</div>'
        '</div>'
    )


def _decision_card_step5_10b(c, rank, games_df, ts, snap, baseline, risk):
    html = _BASE_DECISION(c, rank, games_df, ts, snap, baseline, risk)
    board = _session_board_html(_session_context_for_candidate(c))
    marker = '<div class="kui-score">'
    return html.replace(marker, board + marker, 1) if marker in html else html + board


def _why_sections_step5_10b(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in _BASE_WHY(c, games_df, snap, ts, baseline, risk)
    ]
    context = _session_context_for_candidate(c)
    source = str(context.get("control_source") or "DEFAULT_OFF")
    if source == "HOST_ENV":
        line = "Step 5.10B detected explicit Step 5.10 host environment control and did not override it."
    elif context.get("query_param_activation_requested") is True:
        line = (
            "Step 5.10B is using explicit Streamlit URL query control for this browser session only; "
            "the certified Step 5.10 game-level cohort and 25% hard cap remain unchanged."
        )
    elif source == "STREAMLIT_QUERY_SESSION":
        line = "Step 5.10B query control is present but not armed, so the session remains on the Step 5.10 rollback path."
    else:
        line = "Step 5.10B session control is idle; production remains on the Step 5.10 default OFF/0% path."
    line += " Removing the Step 5.10B query parameters is an exact session rollback."

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


def install_streamlit_session_canary_layer(games_df) -> dict[str, Any]:
    # Patch only Step 5.10's configuration reader. Its certified cohort math,
    # Step 5.9 gate, and selector behavior remain byte-for-byte unchanged.
    step510.canary_rollout_config = streamlit_canary_rollout_config
    state = step510.install_price_gate_canary_layer(games_df)
    v217._decision_card_v217 = _decision_card_step5_10b
    v217._why_sections = _why_sections_step5_10b

    config = streamlit_canary_rollout_config()
    wrapper_state = {
        "data_type": "mlb_streamlit_session_canary_control_v1",
        "schema_version": 1,
        **config,
        "session_only": True,
        "host_env_precedence": True,
        "step5_10_core_unchanged": True,
        "exact_query_rollback": True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
    }
    st.session_state[_STATE_KEY] = wrapper_state
    wrapper_state["step5_10_available"] = bool(state.get("data_type"))
    return wrapper_state


__all__ = [
    "VERSION",
    "install_streamlit_session_canary_layer",
    "streamlit_canary_rollout_config",
]
