"""WNBA PRA Repair V1 Step 7 — final runtime integration overlay.

Additive wrapper above frozen Step 5. It activates the frozen Step-6 completeness
audits at the existing game/player/final-card handoff points without introducing
network reads or changing any WNBA model, projection, market, probability,
qualification, ranking, sportsbook, or other-sport behavior.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback as frozen_parent
import streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness as deep_route
import wnba_pra_final_v2_step7 as final_transport
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_player_intelligence_v2_step4 as player_intelligence
import wnba_pra_repair_v1_step5_decision_fallback as step5_engine
import wnba_pra_repair_v1_step6_completeness_sweep as step6
import wnba_pra_repair_v1_step7_final_integration as integration
import wnba_pra_slate_v2_step2 as slate

MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 7 FINAL INTEGRATION"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_PROJECTION_MATH = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_QUALIFICATION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0
PROOF_MARKER = "wnba-pra-repair-v1-step7-final-integration"


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _selected_game() -> dict[str, Any]:
    raw = st.session_state.get(slate.SESSION_SELECTED_GAME)
    return dict(raw) if isinstance(raw, Mapping) else {}


def _selected_player() -> dict[str, Any]:
    raw = st.session_state.get(game_center.SESSION_SELECTED_PLAYER)
    return dict(raw) if isinstance(raw, Mapping) else {}


def _flatten_players(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    teams = payload.get("teams")
    if not isinstance(teams, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for team_rows in teams.values():
        if not isinstance(team_rows, (list, tuple)):
            continue
        rows.extend(dict(row) for row in team_rows if isinstance(row, Mapping))
    return rows


def _proof_marker(kind: str, ready: bool, detail: str = "") -> None:
    status = "green" if ready else "blocked"
    safe_kind = str(kind or "integration").replace('"', "")
    safe_detail = str(detail or "").replace('"', "")
    st.markdown(
        '<div style="display:none" '
        f'data-wnba-pra-repair-v1-step7="{PROOF_MARKER}" '
        f'data-kind="{safe_kind}" data-status="{status}" '
        f'data-detail="{safe_detail}"></div>',
        unsafe_allow_html=True,
    )


def _blocked(message: str, *, kind: str) -> dict[str, Any]:
    _proof_marker(kind, False, message)
    st.error(message)
    return {"state": "STEP7_INTEGRATION_BLOCKED", "kind": kind, "detail": message}


def _emit_one_shot_wnba_pra_shell_handoff() -> None:
    """Pin durable WNBA/PRA ownership and issue one universal-shell jump."""
    st.session_state[deep_route.SHELL_SPORT_SESSION_KEY] = deep_route.SHELL_SPORT_VALUE
    st.session_state[deep_route.SHELL_MARKET_SESSION_KEY] = deep_route.SHELL_MARKET_VALUE
    if deep_route._query_value(deep_route.SHELL_SPORT_QUERY_KEY) != deep_route.SHELL_SPORT_VALUE:
        st.query_params[deep_route.SHELL_SPORT_QUERY_KEY] = deep_route.SHELL_SPORT_VALUE
    if deep_route._query_value(deep_route.SHELL_MARKET_QUERY_KEY) != deep_route.SHELL_MARKET_VALUE:
        st.query_params[deep_route.SHELL_MARKET_QUERY_KEY] = deep_route.SHELL_MARKET_VALUE


def _wrap_step7_player_open(delegate):
    """Capture the shell handoff inside the callback object persisted by Streamlit."""
    def _wrapped(game_id: str, player: Mapping[str, Any]):
        _emit_one_shot_wnba_pra_shell_handoff()
        return delegate(game_id, player)

    return _wrapped


def _pin_deep_wnba_session_route(
    state: navigation.NavigationState | None = None,
) -> navigation.NavigationState:
    """Keep deep WNBA routes stable while explicit transitions hand off once.

    The universal router intentionally consumes and deletes ``ks_jump_*`` query
    keys, then reruns. Passive Game/Player rerenders therefore remain session-only
    to avoid the old consume/rerun loop. An explicit navigation transition receives
    one category-jump handoff so the universal shell follows that click before the
    destination page renders.
    """
    explicit_transition = state is not None
    resolved = state or navigation.current_state()
    if deep_route._protect_explicit_cfb_top_picks_route():
        return resolved
    if resolved.page not in {navigation.PAGE_GAME, navigation.PAGE_PLAYER}:
        return resolved
    st.session_state[deep_route.SHELL_SPORT_SESSION_KEY] = deep_route.SHELL_SPORT_VALUE
    st.session_state[deep_route.SHELL_MARKET_SESSION_KEY] = deep_route.SHELL_MARKET_VALUE
    if explicit_transition:
        _emit_one_shot_wnba_pra_shell_handoff()
    return resolved


def render_app() -> Any:
    original_game_renderer = game_center.render_game_center
    original_player_card_renderer = game_center._render_player_card
    original_player_renderer = player_intelligence.render_player_intelligence
    original_final_card_renderer = step5_engine.render_step5_final_card
    original_deep_pin = deep_route._pin_deep_wnba_shell_route
    original_go_to_game = navigation.go_to_game
    original_final_player_open = final_transport._open_player_immediate

    def _go_to_game_with_shell_handoff(*args, **kwargs):
        _emit_one_shot_wnba_pra_shell_handoff()
        return original_go_to_game(*args, **kwargs)

    def guarded_game_renderer(state):
        game = _selected_game()
        game_audit = step6.audit_game(game)
        if not game_audit["ready"]:
            return _blocked(
                "Selected WNBA game context is incomplete. Final integration stopped safely.",
                kind="game",
            )
        result = original_game_renderer(state)
        if isinstance(result, Mapping):
            players = _flatten_players(result)
            audit = integration.audit_game_context(game, players)
            _proof_marker(
                "game",
                bool(audit["ready"]),
                f'players={audit["players_ready"]}/{audit["players_seen"]}',
            )
        return result

    def guarded_player_card(player, game_id: str):
        audit = integration.audit_selected_player(
            player if isinstance(player, Mapping) else None,
            _selected_game(),
        )
        if not audit["ready"]:
            _proof_marker("player-card", False, ",".join(audit.get("missing") or ()))
            return None

        original_go_to_player = navigation.go_to_player

        def _go_to_player_with_shell_handoff(selected_game_id: str, player_id: str):
            _emit_one_shot_wnba_pra_shell_handoff()
            return original_go_to_player(selected_game_id, player_id)

        navigation.go_to_player = _go_to_player_with_shell_handoff
        try:
            return original_player_card_renderer(player, game_id)
        finally:
            navigation.go_to_player = original_go_to_player

    def guarded_player_renderer(state):
        game = _selected_game()
        player = _selected_player()
        game_audit = step6.audit_game(game)
        player_audit = integration.audit_selected_player(player, game)
        if not game_audit["ready"] or not player_audit["ready"]:
            missing = list(game_audit.get("missing") or ()) + list(player_audit.get("missing") or ())
            return _blocked(
                "Selected WNBA player/game context is incomplete. Final integration stopped safely.",
                kind="player",
            ) | {"missing": tuple(dict.fromkeys(missing))}
        _proof_marker("player", True, f'player_id={player_audit.get("player_id")}')
        return original_player_renderer(state)

    def guarded_final_card_renderer(summary):
        audit = integration.audit_final_card(summary if isinstance(summary, Mapping) else None)
        if not audit["covered"]:
            _proof_marker("final-card", False, ",".join(audit.get("missing") or ()))
            st.error("Final PRA card data is incomplete. The card was withheld safely.")
            return None
        _proof_marker("final-card", True, str(audit.get("decision_source") or ""))
        return original_final_card_renderer(summary)

    deep_route._pin_deep_wnba_shell_route = _pin_deep_wnba_session_route
    navigation.go_to_game = _go_to_game_with_shell_handoff
    final_transport._open_player_immediate = _wrap_step7_player_open(original_final_player_open)
    game_center.render_game_center = guarded_game_renderer
    game_center._render_player_card = guarded_player_card
    player_intelligence.render_player_intelligence = guarded_player_renderer
    step5_engine.render_step5_final_card = guarded_final_card_renderer
    try:
        return frozen_parent.render_app()
    finally:
        deep_route._pin_deep_wnba_shell_route = original_deep_pin
        navigation.go_to_game = original_go_to_game
        final_transport._open_player_immediate = original_final_player_open
        game_center.render_game_center = original_game_renderer
        game_center._render_player_card = original_player_card_renderer
        player_intelligence.render_player_intelligence = original_player_renderer
        step5_engine.render_step5_final_card = original_final_card_renderer


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
    "NETWORK_CALLS_ADDED",
    "PROOF_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
