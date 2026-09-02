"""MLB Matchup Explorer V4.7 — cleanup Step 2 compact game cards.

Presentation-only wrapper over the certified V2 Step 12 Matchup Explorer.
Builds on Cleanup Step 1 by replacing the game dropdown with a scannable card
grid while keeping the clean player search/selection flow and all model math
frozen underneath.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

import mlb_matchup_hub_v14 as roster
import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1

VERSION = "MLB Matchup Hub V4.7 • Cleanup Step 2"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP1_PRESENTATION = "mlb_matchup_hub_v42"

_CARD_CSS = r"""
<style>
.mx43-head{border:1px solid #253e57;background:linear-gradient(145deg,#0b1724,#08111c);border-radius:18px;padding:14px 15px;margin:8px 0 12px}
.mx43-head-title{font-size:1.08rem;font-weight:950;color:#f8fafc;margin-bottom:2px}
.mx43-head-sub{font-size:.70rem;color:#8fa4b9;line-height:1.35}
.mx43-card{border:1px solid #29445f;background:#0b1623;border-radius:16px;padding:11px 12px 10px;margin:4px 0 7px;min-height:118px}
.mx43-card-selected{border-color:#50d6ff;box-shadow:0 0 0 1px rgba(80,214,255,.18) inset;background:linear-gradient(145deg,#0d1c2b,#0a1521)}
.mx43-matchup{font-size:.90rem;font-weight:900;color:#f7fafc;line-height:1.25;margin-bottom:5px}
.mx43-time{font-size:.70rem;font-weight:800;color:#65dcff;margin-bottom:4px}
.mx43-meta{font-size:.62rem;color:#91a6ba;line-height:1.42}
.mx43-pitchers{font-size:.64rem;color:#c8d5e2;line-height:1.35;margin-top:5px}
.mx43-status{display:inline-block;font-size:.55rem;font-weight:800;color:#89a3bb;border:1px solid #29445f;border-radius:999px;padding:2px 6px;margin-top:6px}
.mx43-selected-title{font-size:.78rem;font-weight:900;color:#edf6ff;margin:8px 0 1px}
.mx43-selected-sub{font-size:.62rem;color:#8299ae;margin-bottom:7px}
.mx43-roster-note{font-size:.62rem;color:#7890a6;margin:2px 0 7px}
@media(max-width:640px){.mx43-head{padding:12px;border-radius:16px}.mx43-head-title{font-size:1rem}.mx43-card{padding:9px 10px;min-height:112px}.mx43-matchup{font-size:.82rem}}
</style>
"""


def _safe_int(value: Any, default: int = 0) -> int:
    return step1._safe_int(value, default)


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _time_text(row: Any) -> str:
    raw = str(row.get("first_pitch_et") or "TBD").strip()
    if raw.upper() == "TBD":
        return raw
    return raw if "ET" in raw.upper() else f"{raw} ET"


def _game_card_html(row: Any, selected: bool = False) -> str:
    away = _esc(row.get("away_team") or "Away")
    home = _esc(row.get("home_team") or "Home")
    venue = _esc(row.get("venue_name") or "Venue TBD")
    away_pitcher = _esc(row.get("away_pitcher") or "TBD")
    home_pitcher = _esc(row.get("home_pitcher") or "TBD")
    status = _esc(row.get("status") or "Scheduled")
    selected_class = " mx43-card-selected" if selected else ""
    return (
        f'<div class="mx43-card{selected_class}">'
        f'<div class="mx43-matchup">{away} @ {home}</div>'
        f'<div class="mx43-time">{_esc(_time_text(row))}</div>'
        f'<div class="mx43-meta">{venue}</div>'
        f'<div class="mx43-pitchers">{away_pitcher} vs {home_pitcher}</div>'
        f'<div class="mx43-status">{status}</div>'
        '</div>'
    )


def _choose_game(index: int) -> None:
    st.session_state["mh12_game"] = int(index)
    st.session_state["mh12_player"] = 0
    st.session_state["mx43_last_game"] = int(index)


def _render_game_cards(games_df) -> int:
    game_options = list(range(len(games_df)))
    prior_game = _safe_int(st.session_state.get("mh12_game", 0), 0)
    selected = prior_game if prior_game in game_options else 0
    st.session_state["mh12_game"] = selected

    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="mx43-head"><div class="mx43-head-title">Choose a matchup</div>'
        '<div class="mx43-head-sub">Tap a game, then choose a hitter. Time, park and probable starters are visible before you open anything.</div></div>',
        unsafe_allow_html=True,
    )

    for start in range(0, len(game_options), 2):
        cols = st.columns(2, gap="small")
        for offset, col in enumerate(cols):
            index = start + offset
            if index >= len(game_options):
                continue
            row = games_df.iloc[index]
            game_pk = _safe_int(row.get("game_pk"), index)
            with col:
                st.markdown(_game_card_html(row, selected=index), unsafe_allow_html=True)
                st.button(
                    "✓ Selected" if selected == index else "View players",
                    key=f"mx43_game_{game_pk}_{index}",
                    use_container_width=True,
                    disabled=(selected == index),
                    on_click=_choose_game,
                    args=(index,),
                )

    return _safe_int(st.session_state.get("mh12_game", selected), selected)


def _render_player_picker(games_df, game_index: int) -> None:
    row = games_df.iloc[int(game_index)]
    players = roster._all_hitters_v14(row)
    if not players:
        st.warning("No active hitters are available for this matchup yet.")
        return

    away = _esc(row.get("away_team") or "Away")
    home = _esc(row.get("home_team") or "Home")
    st.markdown(
        f'<div class="mx43-selected-title">Players • {away} @ {home}</div>'
        '<div class="mx43-selected-sub">Lineup players appear first. Bench/active-roster players stay available below them.</div>',
        unsafe_allow_html=True,
    )

    game_pk = _safe_int(row.get("game_pk"), game_index)
    query = st.text_input(
        "Search player",
        placeholder="Name, team, position, confirmed/projected/bench",
        key=f"mx43_search_{game_pk}",
    ).strip()

    ordered = step1._ordered_player_indices(players)
    filtered = [i for i in ordered if step1._matches_search(players[i], query)]
    if not filtered:
        st.info("No players match that search. Clear the search to see the full roster.")
        prior_player = _safe_int(st.session_state.get("mh12_player", 0), 0)
        st.session_state["mh12_player"] = prior_player if 0 <= prior_player < len(players) else ordered[0]
        return

    prior_player = _safe_int(st.session_state.get("mh12_player", filtered[0]), filtered[0])
    default_player = prior_player if prior_player in filtered else filtered[0]
    selected_player = st.selectbox(
        "Player",
        filtered,
        index=filtered.index(default_player),
        format_func=lambda i: step1._player_label(players[int(i)]),
        key=f"mx43_player_{game_pk}",
    )
    st.session_state["mh12_player"] = _safe_int(selected_player, filtered[0])

    confirmed = sum(1 for p in players if step1._role(p)[0] == "Confirmed")
    projected = sum(1 for p in players if step1._role(p)[0] == "Projected")
    bench = sum(1 for p in players if step1._role(p)[0] == "Bench")
    st.markdown(
        f'<div class="mx43-roster-note">Confirmed {confirmed} • Projected {projected} • Bench/active {bench}</div>',
        unsafe_allow_html=True,
    )


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    game_index = _render_game_cards(games_df)
    _render_player_picker(games_df, game_index)

    original_selectbox = st.selectbox
    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP1_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_game_card_html",
    "_render_game_cards",
    "render_matchup_hub",
]
