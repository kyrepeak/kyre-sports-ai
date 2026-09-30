"""WNBA PRA Speed V3 Step 8 — render visible Player PRA content first.

This layer changes render order only. It emits a lightweight Player identity +
projected PRA shell from the already-selected Game Center snapshot before the
frozen Step-7 Player loader begins. The shell stays alive through the server
run and is hidden only when the final Step-8 result marker exists, preventing
same-run Streamlit placeholder collapse while preserving the final Player UI.

No model, projection, market, ranking, qualification, Monte Carlo, sportsbook,
provider, or frozen Step-1-through-Step-7 behavior is modified.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_player_intelligence_v2_step4 as player_intelligence

MODEL_VERSION = "WNBA PRA SPEED V3 • STEP 8 VISIBLE CONTENT FIRST"
SESSION_PERF = "ks_wnba_pra_speed_v3_step8_perf"

MAX_VISIBLE_SHELL_SECONDS = 0.75
MAX_FINAL_PLAYER_SECONDS = 1.50

VISIBLE_FIRST_CONTRACT = {
    "project": "WNBA PRA Speed V3",
    "step": "8/9",
    "scope": "render_visible_player_pra_content_before_frozen_loader",
    "source": "already_selected_game_center_snapshot",
    "visible_before_loader": True,
    "shell_render_phase": "router_entry_before_frozen_parent",
    "loader_wrapper_renders_shell": False,
    "shell_is_temporary": True,
    "shell_lifetime": "until_final_result_marker",
    "server_side_clear": False,
    "final_marker_css_handoff": True,
    "final_renderer_unchanged": True,
    "frozen_speed_v3_steps_1_7_modified": False,
    "network_calls_added": 0,
    "projection_runs_added": 0,
    "sportsbook_calls_added": 0,
    "qualification_runs_added": 0,
    "ranking_runs_added": 0,
    "monte_carlo_runs_added": 0,
    "projection_math_changed": False,
    "market_math_changed": False,
    "data_meaning_changed": False,
    "sportsbook_projection_influence": 0.0,
    "warm_same_session_target_seconds_max": 0.75,
    "cached_cold_target_seconds_max": 1.50,
    "true_cold_target_seconds_max": 2.50,
}


def _record(**values: Any) -> None:
    current = st.session_state.get(SESSION_PERF)
    current = dict(current) if isinstance(current, Mapping) else {}
    current.update(values)
    st.session_state[SESSION_PERF] = current


def _visible_shell_markup(game_id: str, player_id: int) -> str:
    player = player_intelligence._selected_player()
    game = player_intelligence._selected_game()
    if not player or not game:
        return ""
    if player_intelligence._int(player.get("player_id")) != int(player_id):
        return ""
    if player_intelligence._text(game.get("game_id")) != str(game_id):
        return ""

    name = player_intelligence._text(player.get("player_name")) or f"Player {int(player_id)}"
    team_abbr = player_intelligence._text(player.get("team_abbreviation")) or "WNBA"
    role = player_intelligence._text(player.get("role_label")) or "ACTIVE"
    designation = player_intelligence._text(player.get("designation")) or "NO DESIGNATION"
    starter = bool(player.get("starter_confirmed"))
    away = player_intelligence._text(game.get("away_team"))
    home = player_intelligence._text(game.get("home_team"))
    matchup = f"{away} @ {home}".strip(" @")
    headshot = (
        player_intelligence._text(player.get("headshot_url"))
        or player_intelligence._player_headshot(player_id)
    )

    hero = (
        '<div class="wn4-hero">'
        f'{player_intelligence._image(headshot, name, "wn4-headshot")}'
        '<div>'
        '<div class="wn4-kicker">Kyre Sports AI • WNBA PRA Intelligence</div>'
        f'<div class="wn4-title">{name}</div>'
        f'<div class="wn4-sub">{team_abbr} • {matchup} • {role}</div>'
        '<div class="wn4-chips">'
        '<span class="wn4-chip ok">● PLAYER SELECTED</span>'
        f'<span class="wn4-chip">{"STARTER" if starter else "STARTER NOT CONFIRMED"}</span>'
        f'<span class="wn4-chip">{designation}</span>'
        '<span class="wn4-chip">Loading final intelligence…</span>'
        '</div></div></div>'
    )
    strip = (
        '<div class="wn4-strip">'
        + player_intelligence._metric("MIN", player_intelligence._fmt(player.get("projected_minutes")))
        + player_intelligence._metric("PTS", player_intelligence._fmt(player.get("projected_pts")))
        + player_intelligence._metric("REB", player_intelligence._fmt(player.get("projected_reb")))
        + player_intelligence._metric("AST", player_intelligence._fmt(player.get("projected_ast")))
        + player_intelligence._metric("PRA", player_intelligence._fmt(player.get("projected_pra")))
        + '</div>'
    )
    return (
        '<div data-wnba-pra-speed-v3-step8-shell="visible" '
        'data-visible-before-loader="true" '
        f'data-player-id="{int(player_id)}">'
        + hero
        + strip
        + '</div>'
    )


def render_visible_shell_early(state: navigation.NavigationState) -> Any:
    """Render Player identity/PRA immediately at Step-8 router entry."""
    started = perf_counter()
    if state.page != navigation.PAGE_PLAYER or not state.game_id or not state.player_id:
        _record(
            page=state.page,
            shell_emitted=False,
            shell_before_loader=False,
            shell_emit_ms=0.0,
            loader_started_after_shell=False,
        )
        return None

    try:
        player_id = int(state.player_id)
    except (TypeError, ValueError):
        _record(
            page=state.page,
            shell_emitted=False,
            shell_before_loader=False,
            shell_emit_ms=0.0,
            loader_started_after_shell=False,
        )
        return None

    markup = _visible_shell_markup(str(state.game_id), player_id)
    if not markup:
        _record(
            page=state.page,
            player_id=player_id,
            shell_emitted=False,
            shell_before_loader=False,
            shell_emit_ms=0.0,
            loader_started_after_shell=False,
        )
        return None

    slot = st.empty()
    slot.markdown(markup, unsafe_allow_html=True)
    shell_emit_ms = (perf_counter() - started) * 1000.0
    _record(
        page=navigation.PAGE_PLAYER,
        player_id=player_id,
        shell_emitted=True,
        shell_before_loader=True,
        shell_emit_ms=shell_emit_ms,
        loader_started_after_shell=False,
        shell_render_phase="router_entry_before_frozen_parent",
    )
    return slot


def load_player_intelligence_visible_first(
    original_loader: Callable[[str, int], dict[str, Any]],
    game_id: str,
    player_id: int,
    *,
    shell_slot: Any = None,
) -> dict[str, Any]:
    """Run the frozen loader after the router has already emitted the shell."""
    _record(
        page=navigation.PAGE_PLAYER,
        player_id=int(player_id),
        loader_started_after_shell=shell_slot is not None,
    )
    loader_started = perf_counter()
    try:
        payload = original_loader(str(game_id), int(player_id))
    except Exception as exc:
        _record(
            loader_ms=(perf_counter() - loader_started) * 1000.0,
            loader_error=type(exc).__name__,
            shell_retained_through_final=shell_slot is not None,
        )
        raise

    _record(
        loader_ms=(perf_counter() - loader_started) * 1000.0,
        loader_error="",
        shell_removed_before_final_renderer=False,
        shell_retained_through_final=shell_slot is not None,
    )
    return payload

def _render_deployment_marker(state: navigation.NavigationState) -> None:
    st.markdown(
        '<style>'
        'body:has([data-wnba-pra-speed-v3-step8-result="true"]) '
        '[data-wnba-pra-speed-v3-step8-shell="visible"]'
        '{display:none!important;}'
        '</style>'
        '<span data-wnba-pra-speed-v3-step8="visible-first" '
        'data-active="true" '
        'data-loader-wrapper="true" '
        f'data-page="{state.page}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def _render_result_marker(state: navigation.NavigationState) -> None:
    perf = st.session_state.get(SESSION_PERF)
    perf = dict(perf) if isinstance(perf, Mapping) else {}
    st.markdown(
        '<span data-wnba-pra-speed-v3-step8-result="true" '
        f'data-page="{state.page}" '
        f'data-shell-emitted="{str(bool(perf.get("shell_emitted"))).lower()}" '
        f'data-shell-before-loader="{str(bool(perf.get("shell_before_loader"))).lower()}" '
        f'data-shell-removed-before-final="{str(bool(perf.get("shell_removed_before_final_renderer"))).lower()}" '
        f'data-shell-retained-through-final="{str(bool(perf.get("shell_retained_through_final"))).lower()}" '
        f'data-shell-emit-ms="{float(perf.get("shell_emit_ms") or 0.0):.3f}" '
        f'data-loader-ms="{float(perf.get("loader_ms") or 0.0):.3f}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_step8_route(frozen_renderer: Callable[[], Any]) -> Any:
    """Expose deployment identity early, then preserve the frozen Step-7 render."""
    state = navigation.current_state()
    _render_deployment_marker(state)
    result = frozen_renderer()
    _render_result_marker(navigation.current_state())
    return result


__all__ = [
    "MAX_FINAL_PLAYER_SECONDS",
    "MAX_VISIBLE_SHELL_SECONDS",
    "MODEL_VERSION",
    "SESSION_PERF",
    "VISIBLE_FIRST_CONTRACT",
    "load_player_intelligence_visible_first",
    "render_visible_shell_early",
    "render_step8_route",
]
