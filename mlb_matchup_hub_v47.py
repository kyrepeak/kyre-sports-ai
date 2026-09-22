"""MLB Matchup Explorer V5.1 — cleanup Step 6 compact mobile controls.

Presentation-only wrapper over certified Cleanup Step 5 and Matchup Intelligence
V2. Matchup cards and roster groups stay available on demand behind compact
change controls so the selected-player hero/final result is reached faster on
phone and tablet. No projection, probability, calibration or ranking math is
changed.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v43 as step2
import mlb_matchup_hub_v44 as step3
import mlb_matchup_hub_v45 as step4
import mlb_matchup_hub_v46 as step5
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.1 • Cleanup Step 6"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP1_PRESENTATION = "mlb_matchup_hub_v42"
FROZEN_STEP2_PRESENTATION = "mlb_matchup_hub_v43"
FROZEN_STEP3_PRESENTATION = "mlb_matchup_hub_v44"
FROZEN_STEP4_PRESENTATION = "mlb_matchup_hub_v45"
FROZEN_STEP5_PRESENTATION = "mlb_matchup_hub_v46"

_STEP6_CSS = r"""
<style>
.mx47-summary{border:1px solid #28465f;background:linear-gradient(145deg,#0b1724,#08121d);border-radius:15px;padding:9px 11px;margin:7px 0 8px}
.mx47-kicker{font-size:.49rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#63d9ff;margin-bottom:2px}
.mx47-game{font-size:.82rem;font-weight:900;color:#f5f9fd;line-height:1.25}
.mx47-player{font-size:.61rem;color:#8fa5b9;line-height:1.4;margin-top:2px}
.mx47-player b{color:#dfeaf4;font-weight:850}
.mx47-helper{font-size:.53rem;color:#708aa0;margin:-2px 0 6px;line-height:1.35}
.mx43-head,.mx44-head{padding:8px 10px!important;margin:5px 0 7px!important;border-radius:13px!important}
.mx43-head-sub,.mx44-head-sub{display:none!important}
.mx43-card{padding:8px 9px!important;min-height:0!important;margin:3px 0 5px!important;border-radius:13px!important}
.mx43-matchup{font-size:.78rem!important;margin-bottom:3px!important}.mx43-time{font-size:.62rem!important;margin-bottom:2px!important}
.mx43-meta,.mx43-pitchers{font-size:.56rem!important;line-height:1.3!important}.mx43-status{font-size:.49rem!important;margin-top:4px!important}
.mx44-selected{display:none!important}.mx44-group{margin:8px 0 4px!important}.mx44-team{margin:2px 0 4px!important}.mx44-meta{margin:-4px 0 4px 2px!important}
.mx44-counts{margin:2px 0 5px!important}.mx45-hero{margin-top:8px!important;margin-bottom:10px!important}
@media(max-width:640px){
  .mx47-summary{padding:8px 9px;margin:5px 0 6px;border-radius:13px}.mx47-game{font-size:.75rem}.mx47-player{font-size:.56rem}.mx47-helper{font-size:.49rem}
  .mx43-card{padding:7px 8px!important}.mx43-pitchers{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mx45-note{display:none!important}
}
</style>
"""


def _safe_int(value: Any, default: int = 0) -> int:
    return step1._safe_int(value, default)


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _selected_game_index(games_df) -> int:
    if games_df is None or games_df.empty:
        return 0
    raw = _safe_int(st.session_state.get("mh12_game", 0), 0)
    return max(0, min(raw, len(games_df) - 1))


def _selection_summary_html(context: dict[str, Any] | None) -> str:
    if not context:
        return (
            '<div class="mx47-summary"><div class="mx47-kicker">Current selection</div>'
            '<div class="mx47-game">Waiting for a verified matchup</div>'
            '<div class="mx47-player">Use the controls below when slate data is ready.</div></div>'
        )

    row = context["row"]
    player = context["player"]
    away = _esc(row.get("away_team") or "Away")
    home = _esc(row.get("home_team") or "Home")
    first_pitch = _esc(row.get("first_pitch_et") or "TBD")
    player_name = _esc(player.get("name") or "Player")
    team = _esc(player.get("team") or "")
    role_label, _ = step1._role(player)
    slot = _safe_int(player.get("slot"), 99)
    slot_text = f" • #{slot}" if role_label != "Bench" and 1 <= slot <= 9 else ""
    return (
        '<div class="mx47-summary">'
        '<div class="mx47-kicker">Current selection</div>'
        f'<div class="mx47-game">{away} @ {home} • {first_pitch}</div>'
        f'<div class="mx47-player"><b>{player_name}</b> • {team} • {_esc(role_label + slot_text)}</div>'
        '</div>'
    )


def _game_callback(original):
    """After changing games, close the slate and open player access."""
    def wrapped(index: int) -> None:
        original(index)
        st.session_state["mx47_show_games"] = False
        st.session_state["mx47_show_players"] = True
    return wrapped


def _player_callback(original):
    """After choosing a hitter, collapse controls so the hero is immediate."""
    def wrapped(index: int) -> None:
        original(index)
        st.session_state["mx47_show_players"] = False
    return wrapped


def _render_compact_controls(games_df) -> int:
    context = step4._selected_context(games_df)
    st.markdown(_STEP6_CSS + _selection_summary_html(context), unsafe_allow_html=True)

    left, right = st.columns(2, gap="small")
    with left:
        show_games = st.toggle(
            "Change matchup",
            value=False,
            key="mx47_show_games",
            help="Open the slate only when you need a different game.",
        )
    with right:
        show_players = st.toggle(
            "Change player",
            value=False,
            key="mx47_show_players",
            help="Open grouped rosters only when you need a different hitter.",
        )

    game_index = _selected_game_index(games_df)
    if show_games:
        original_choose_game = step2._choose_game
        step2._choose_game = _game_callback(original_choose_game)
        try:
            game_index = step2._render_game_cards(games_df)
        finally:
            step2._choose_game = original_choose_game

    game_index = _selected_game_index(games_df)
    if show_players:
        original_choose_player = step3._choose_player
        step3._choose_player = _player_callback(original_choose_player)
        try:
            step3._render_roster_groups(games_df, game_index)
        finally:
            step3._choose_player = original_choose_player

    st.markdown(
        '<div class="mx47-helper">Controls stay collapsed after a selection so the player result remains the main screen.</div>',
        unsafe_allow_html=True,
    )
    return _selected_game_index(games_df)


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    _render_compact_controls(games_df)

    context = step4._selected_context(games_df)
    hero_slot = st.empty()
    step4._render_hero(hero_slot, context, None)

    original_selectbox = st.selectbox
    original_expander = st.expander
    original_step12_profile = final_layer._render_step12_profile

    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    st.expander = step5._collapsed_expander(original_expander)
    final_layer._render_step12_profile = step4._step12_profile_with_hero(
        original_step12_profile,
        hero_slot,
        context,
    )
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        final_layer._render_step12_profile = original_step12_profile
        st.expander = original_expander
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP1_PRESENTATION",
    "FROZEN_STEP2_PRESENTATION",
    "FROZEN_STEP3_PRESENTATION",
    "FROZEN_STEP4_PRESENTATION",
    "FROZEN_STEP5_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_game_callback",
    "_player_callback",
    "_render_compact_controls",
    "_selection_summary_html",
    "render_matchup_hub",
]
