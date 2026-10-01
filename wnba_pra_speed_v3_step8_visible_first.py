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

from html import escape
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
    "client_preview_before_rerun": True,
    "client_preview_source": "frozen_game_center_projection_card",
    "client_preview_transport": "css_focus_within",
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



def _preview_value(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:.1f}"


def _client_preview_markup(player: Mapping[str, Any]) -> str:
    try:
        player_id = int(player.get("player_id"))
    except (TypeError, ValueError):
        return ""
    name = escape(str(player.get("player_name") or f"Player {player_id}"))
    team = escape(str(player.get("team_abbreviation") or "WNBA"))
    metrics = [
        ("MIN", player.get("projected_minutes")),
        ("PTS", player.get("projected_pts")),
        ("REB", player.get("projected_reb")),
        ("AST", player.get("projected_ast")),
        ("PRA", player.get("projected_pra")),
    ]
    metric_html = "".join(
        '<div class="wn8-client-metric">'
        f'<b>{escape(_preview_value(value))}</b>'
        f'<span>{escape(label)}</span>'
        '</div>'
        for label, value in metrics
    )
    return (
        '<div data-wnba-pra-speed-v3-step8-click-preview="true" '
        f'data-player-id="{player_id}" '
        'role="status" aria-live="polite">'
        '<div class="wn8-client-kicker">Kyre Sports AI • Player PRA</div>'
        f'<div class="wn8-client-name">{name}</div>'
        f'<div class="wn8-client-team">{team} • opening PRA intelligence…</div>'
        f'<div class="wn8-client-metrics">{metric_html}</div>'
        '</div>'
    )


def render_client_preview_css() -> None:
    st.markdown(
        """
<style>
[class*="st-key-wnba_pra_speed_v3_step8_preview_"]
[data-wnba-pra-speed-v3-step8-click-preview="true"] {
  display:none;
}
[class*="st-key-wnba_pra_speed_v3_step8_preview_"]:focus-within
[data-wnba-pra-speed-v3-step8-click-preview="true"],
[class*="st-key-wnba_pra_speed_v3_step8_preview_"]:has(button:active)
[data-wnba-pra-speed-v3-step8-click-preview="true"] {
  display:block !important;
  position:fixed;
  left:12px;
  right:12px;
  top:12px;
  z-index:2147483000;
  padding:14px 16px;
  border:1px solid rgba(255,255,255,.18);
  border-radius:16px;
  background:rgba(8,14,24,.97);
  box-shadow:0 18px 55px rgba(0,0,0,.45);
  pointer-events:none;
}
.wn8-client-kicker {font-size:.76rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;opacity:.72;}
.wn8-client-name {font-size:1.28rem;font-weight:900;margin-top:3px;}
.wn8-client-team {font-size:.84rem;opacity:.76;margin-top:2px;}
.wn8-client-metrics {display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin-top:10px;}
.wn8-client-metric {text-align:center;padding:8px 5px;border-radius:10px;background:rgba(255,255,255,.06);}
.wn8-client-metric b {display:block;font-size:1rem;}
.wn8-client-metric span {display:block;font-size:.68rem;opacity:.68;margin-top:2px;}
</style>
<span data-wnba-pra-speed-v3-step8-client-preview-contract="true"
      data-client-before-rerun="true"
      style="display:none" aria-hidden="true"></span>
""",
        unsafe_allow_html=True,
    )


def render_game_player_with_client_preview(
    original_renderer: Callable[[Mapping[str, Any], str], Any],
    player: Mapping[str, Any],
    game_id: str,
) -> Any:
    """Wrap a frozen Game Center player/button with a browser-side click preview."""
    try:
        player_id = int(player.get("player_id"))
    except (TypeError, ValueError):
        return original_renderer(player, game_id)

    key = f"wnba_pra_speed_v3_step8_preview_{player_id}"
    with st.container(key=key):
        result = original_renderer(player, game_id)
        markup = _client_preview_markup(player)
        if markup:
            st.markdown(markup, unsafe_allow_html=True)
        return result


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
    "render_client_preview_css",
    "render_game_player_with_client_preview",
    "render_visible_shell_early",
    "render_step8_route",
]
