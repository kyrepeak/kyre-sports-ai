"""WNBA Navigation V2 — Step 7 final transport + freeze layer.

Step 7 preserves frozen Steps 1-6 byte-for-byte and removes the last public
navigation blocker: selected-destination prefetch no longer runs synchronously
inside the Streamlit button callback. The native button rerun first commits the
selected game/player and navigation state; the frozen destination loader then
runs on the destination render.

No model, projection, market, ranking, qualification, sportsbook, Monte Carlo,
responsive, or data-source behavior is changed.
"""
from __future__ import annotations

from functools import partial
from typing import Any, Callable, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_slate_v2_step2 as slate
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_responsive_v2_step6 as responsive


MODEL_VERSION = "WNBA PRA NAVIGATION V2 • STEP 7 FINAL TRANSPORT + FREEZE"

FINAL_TRANSPORT_CONTRACT = {
    "project": "WNBA Navigation V2",
    "step": "7/7",
    "scope": "navigation_transport_only_over_frozen_steps_1_through_6",
    "native_button_rerun": True,
    "navigation_state_committed_before_destination_work": True,
    "synchronous_prefetch_in_navigation_callback": False,
    "destination_loads_on_destination_render": True,
    "speculative_prefetch": False,
    "background_prefetch": False,
    "frozen_steps_1_through_6_modified": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "ranking_changed": False,
    "qualification_changed": False,
    "monte_carlo_changed": False,
    "sportsbook_projection_influence": 0.0,
}


def _open_game_immediate(game: Mapping[str, Any]) -> None:
    snapshot = dict(game)
    game_id = str(snapshot.get("game_id") or "")
    if not game_id:
        performance._record(last_transition="slate_to_game", transition_status="missing_game_id")
        return

    st.session_state[slate.SESSION_SELECTED_GAME] = snapshot
    navigation.go_to_game(game_id)
    performance._record(
        last_transition="slate_to_game",
        transition_transport="native_on_click_single_rerun_step7",
        prefetch_target="destination_render",
        prefetch_status="deferred_until_destination",
        explicit_rerun=False,
    )


def _open_player_immediate(game_id: str, player: Mapping[str, Any]) -> None:
    snapshot = dict(player)
    try:
        player_id = int(snapshot.get("player_id"))
    except (TypeError, ValueError):
        performance._record(last_transition="game_to_player", transition_status="missing_player_id")
        return

    st.session_state[game_center.SESSION_SELECTED_PLAYER] = snapshot
    navigation.go_to_player(str(game_id), str(player_id))
    performance._record(
        last_transition="game_to_player",
        transition_transport="native_on_click_single_rerun_step7",
        prefetch_target="destination_render",
        prefetch_status="deferred_until_destination",
        explicit_rerun=False,
    )


def _step7_button_callback(key: str) -> Callable[[], None] | None:
    if key.startswith("wnba_nav_v2_step2_open_"):
        game_id = key.removeprefix("wnba_nav_v2_step2_open_")
        game = performance._slate_game(game_id)
        return partial(_open_game_immediate, game) if game is not None else None

    if key.startswith("wnba_nav_v2_step3_player_"):
        suffix = key.removeprefix("wnba_nav_v2_step3_player_")
        if "_" not in suffix:
            return None
        game_id, player_id = suffix.rsplit("_", 1)
        player = performance._game_player(game_id, player_id)
        return partial(_open_player_immediate, game_id, player) if player is not None else None

    if key in {
        "wnba_nav_v2_step3_back_slate",
        "wnba_nav_v2_step3_missing_game_back",
        "wnba_nav_v2_step3_mismatch_back",
    }:
        return performance._back_to_slate_once

    if key in {
        "wnba_nav_v2_step4_back_game",
        "wnba_nav_v2_step4_missing_back",
    }:
        state = navigation.current_state()
        return partial(performance._back_to_game_once, state.game_id)

    return None


def _render_step7_marker(state: navigation.NavigationState) -> None:
    st.html(
        f"""
<div data-wnba-nav-v2-step7="final-transport"
     data-wnba-nav-page="{state.page}"
     data-navigation-first="true"
     data-callback-prefetch="false"
     style="height:0;min-height:0;overflow:hidden;padding:0;margin:0;border:0"
     aria-hidden="true"></div>
"""
    )


def render_step7_route():
    state = navigation.current_state()
    _render_step7_marker(state)

    original_callback = performance._button_callback
    performance._button_callback = _step7_button_callback
    try:
        return responsive.render_step6_route()
    finally:
        performance._button_callback = original_callback


__all__ = [
    "FINAL_TRANSPORT_CONTRACT",
    "MODEL_VERSION",
    "_open_game_immediate",
    "_open_player_immediate",
    "_step7_button_callback",
    "render_step7_route",
]
