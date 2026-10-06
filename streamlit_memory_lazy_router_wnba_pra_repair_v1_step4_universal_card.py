"""WNBA PRA Repair V1 Step 4 — universal final PRA card overlay.

This wrapper sits above frozen WNBA PRA Repair V1 Step 3. It captures the exact
PRA-card result already produced by frozen Player Intelligence and renders one
truthful final summary for every eligible selected player. It performs no extra
network read and changes no model or market ownership.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness as frozen_parent
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_player_intelligence_v2_step4 as player_intelligence
import wnba_pra_repair_v1_step4_final_card as final_card


MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 4 UNIVERSAL FINAL CARD"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_PROJECTION_MATH = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_QUALIFICATION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SESSION_CAPTURE = "ks_wnba_pra_repair_v1_step4_exact_card"
PROOF_MARKER = "universal-final-card"


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _selected_player() -> dict[str, Any]:
    raw = st.session_state.get(game_center.SESSION_SELECTED_PLAYER)
    return dict(raw) if isinstance(raw, Mapping) else {}


def _save_capture(card: Mapping[str, Any] | None, card_state: str) -> None:
    st.session_state[SESSION_CAPTURE] = {
        "card": dict(card) if isinstance(card, Mapping) else None,
        "card_state": str(card_state or ""),
    }


def _current_capture() -> dict[str, Any]:
    raw = st.session_state.get(SESSION_CAPTURE)
    return dict(raw) if isinstance(raw, Mapping) else {}


def render_app() -> Any:
    original_exact = player_intelligence._exact_pra_card
    original_player_renderer = player_intelligence.render_player_intelligence

    def captured_exact(view, game_id: str, player_id: int):
        card, card_state = original_exact(view, game_id, player_id)
        _save_capture(card, card_state)
        return card, card_state

    def universal_player_renderer(state):
        st.session_state.pop(SESSION_CAPTURE, None)
        result = original_player_renderer(state)
        captured = _current_capture()
        summary = final_card.build_final_card(
            _selected_player(),
            captured.get("card") if isinstance(captured.get("card"), Mapping) else None,
            str(captured.get("card_state") or "unavailable"),
        )
        final_card.render_final_card(summary)
        return result

    player_intelligence._exact_pra_card = captured_exact
    player_intelligence.render_player_intelligence = universal_player_renderer
    try:
        return frozen_parent.render_app()
    finally:
        player_intelligence._exact_pra_card = original_exact
        player_intelligence.render_player_intelligence = original_player_renderer


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION_MATH",
    "MAY_MODIFY_QUALIFICATION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "PROOF_MARKER",
    "SESSION_CAPTURE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
