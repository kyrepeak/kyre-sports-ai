"""WNBA PRA Repair V1 Step 5 — decision/data fallback overlay.

Additive wrapper above frozen Step 4. Exact certified cards remain untouched.
Only players without an exact card receive a cached hosted Step-5F probability
read against a clearly labeled history-derived reference threshold. If that
read is unavailable, official game-log hit rate is used; missing data fails
closed to N/A.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card as frozen_parent
import wnba_pra_player_intelligence_v2_step4 as player_intelligence
import wnba_pra_repair_v1_step4_final_card as step4_final_card
import wnba_pra_repair_v1_step5_decision_fallback as step5_engine
from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON


MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 5 DECISION FALLBACK"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_PROJECTION_MATH = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_QUALIFICATION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MODEL_TIMEOUT_SECONDS = 12.0
MODEL_ATTEMPTS = 1
MODEL_CACHE_TTL_SECONDS = 60
SESSION_CONTEXT = "ks_wnba_pra_repair_v1_step5_context"
SESSION_MODEL_ERROR = "ks_wnba_pra_repair_v1_step5_model_error"
PROOF_MARKER = "decision-fallback"


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


@st.cache_data(ttl=MODEL_CACHE_TTL_SECONDS, show_spinner=False)
def _read_model_probability(game_id: str, player_id: int, line: float) -> dict[str, Any]:
    client = KyreWNBAAPIClient(timeout_seconds=MODEL_TIMEOUT_SECONDS, attempts=MODEL_ATTEMPTS)
    path = f"/api/v1/wnba/games/{str(game_id)}/players/{int(player_id)}/prop-threshold-probability"
    return client.get_json(
        path,
        params={
            "stat": "pra",
            "line": float(line),
            "season": int(SUPPORTED_SEASON),
            "require_current_availability": "true",
            "require_convergence": "true",
        },
    )


def _context() -> dict[str, Any]:
    raw = st.session_state.get(SESSION_CONTEXT)
    return dict(raw) if isinstance(raw, Mapping) else {}


def render_app() -> Any:
    original_loader = player_intelligence.load_player_intelligence
    original_build = step4_final_card.build_final_card
    original_render = step4_final_card.render_final_card

    def captured_loader(game_id: str, player_id: int):
        payload = original_loader(game_id, player_id)
        history = payload.get("history") if isinstance(payload, Mapping) and isinstance(payload.get("history"), Mapping) else None
        st.session_state[SESSION_CONTEXT] = {
            "game_id": str(game_id),
            "player_id": int(player_id),
            "history": dict(history) if isinstance(history, Mapping) else None,
        }
        return payload

    def step5_build(player, exact_card, card_state):
        base = original_build(player, exact_card, card_state)
        context = _context()
        history = context.get("history") if isinstance(context.get("history"), Mapping) else None

        if base.get("market_ready") is True:
            st.session_state[SESSION_MODEL_ERROR] = ""
            return step5_engine.build_step5_decision(base, history, None)

        line = step5_engine.reference_line(history)
        probability_payload = None
        st.session_state[SESSION_MODEL_ERROR] = ""
        if line is not None:
            try:
                game_id = str(context.get("game_id") or "")
                player_id = int(context.get("player_id") or 0)
                if game_id and player_id > 0:
                    probability_payload = _read_model_probability(game_id, player_id, line)
            except Exception as exc:
                st.session_state[SESSION_MODEL_ERROR] = type(exc).__name__

        return step5_engine.build_step5_decision(base, history, probability_payload)

    def step5_render(summary):
        return step5_engine.render_step5_final_card(summary)

    st.session_state.pop(SESSION_CONTEXT, None)
    st.session_state[SESSION_MODEL_ERROR] = ""
    player_intelligence.load_player_intelligence = captured_loader
    step4_final_card.build_final_card = step5_build
    step4_final_card.render_final_card = step5_render
    try:
        return frozen_parent.render_app()
    finally:
        player_intelligence.load_player_intelligence = original_loader
        step4_final_card.build_final_card = original_build
        step4_final_card.render_final_card = original_render


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION_MATH",
    "MAY_MODIFY_QUALIFICATION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_ATTEMPTS",
    "MODEL_CACHE_TTL_SECONDS",
    "MODEL_TIMEOUT_SECONDS",
    "MODEL_VERSION",
    "PROOF_MARKER",
    "SESSION_CONTEXT",
    "SESSION_MODEL_ERROR",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
