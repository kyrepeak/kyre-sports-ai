"""MLB Matchup Explorer V4.6 — cleanup Step 1 two-step picker.

Presentation-only wrapper over the certified V2 Step 12 Matchup Explorer.
It replaces the buried legacy game/player dropdown flow with one clean selection
surface while leaving every projection, calibration, probability and ranking
engine untouched.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_matchup_hub_v14 as roster
import mlb_matchup_hub_v41 as current

VERSION = "MLB Matchup Hub V4.6 • Cleanup Step 1"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"

_PICKER_CSS = r"""
<style>
.mx42-picker{border:1px solid #253e57;background:linear-gradient(145deg,#0b1724,#08111c);border-radius:18px;padding:14px 15px;margin:8px 0 14px}
.mx42-picker-title{font-size:1.08rem;font-weight:950;color:#f8fafc;margin-bottom:2px}
.mx42-picker-sub{font-size:.70rem;color:#8fa4b9;line-height:1.35;margin-bottom:9px}
.mx42-roster-note{font-size:.62rem;color:#7890a6;margin:2px 0 7px}
@media(max-width:640px){.mx42-picker{padding:12px 12px;border-radius:16px}.mx42-picker-title{font-size:1rem}}
</style>
"""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _role(player: dict[str, Any]) -> tuple[str, int]:
    source = str(player.get("source") or "").upper()
    if "CONFIRMED LINEUP" in source:
        return "Confirmed", 0
    if "PROJECTED LINEUP" in source:
        return "Projected", 1
    return "Bench", 2


def _ordered_player_indices(players: list[dict[str, Any]]) -> list[int]:
    """Confirmed lineup, projected lineup, then bench; preserve batting order inside groups."""
    def sort_key(index: int):
        player = players[index]
        role_label, role_rank = _role(player)
        side_rank = 0 if str(player.get("side") or "").lower() == "away" else 1
        slot = _safe_int(player.get("slot"), 99)
        return role_rank, side_rank, slot, str(player.get("name") or "").lower(), role_label

    return sorted(range(len(players)), key=sort_key)


def _game_label(row: Any) -> str:
    away = str(row.get("away_team") or "Away")
    home = str(row.get("home_team") or "Home")
    first_pitch = str(row.get("first_pitch_et") or "TBD")
    return f"{away} @ {home} • {first_pitch} ET"


def _player_label(player: dict[str, Any]) -> str:
    role_label, _ = _role(player)
    slot = _safe_int(player.get("slot"), 99)
    slot_text = f"#{slot} • " if role_label != "Bench" and 1 <= slot <= 9 else ""
    name = str(player.get("name") or "Player")
    team = str(player.get("team") or "")
    position = str(player.get("position") or "").strip()
    details = " — ".join(x for x in (team, position, role_label) if x)
    return f"{slot_text}{name} — {details}" if details else f"{slot_text}{name}"


def _matches_search(player: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    role_label, _ = _role(player)
    haystack = " ".join(
        str(value or "")
        for value in (
            player.get("name"),
            player.get("team"),
            player.get("position"),
            role_label,
        )
    ).lower()
    return query.lower().strip() in haystack


def _render_picker(games_df) -> None:
    if games_df is None or games_df.empty:
        return

    st.markdown(_PICKER_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="mx42-picker"><div class="mx42-picker-title">Find a player</div>'
        '<div class="mx42-picker-sub">1. Pick the game &nbsp;→&nbsp; 2. Pick the hitter. '
        'Lineup players are listed before the bench.</div></div>',
        unsafe_allow_html=True,
    )

    game_options = list(range(len(games_df)))
    prior_game = _safe_int(st.session_state.get("mh12_game", 0), 0)
    game_default = prior_game if prior_game in game_options else 0
    game_index = st.selectbox(
        "Game",
        game_options,
        index=game_options.index(game_default),
        format_func=lambda i: _game_label(games_df.iloc[int(i)]),
        key="mx42_game",
    )
    game_index = _safe_int(game_index, 0)
    st.session_state["mh12_game"] = game_index

    row = games_df.iloc[game_index]
    players = roster._all_hitters_v14(row)
    if not players:
        st.warning("No active hitters are available for this matchup yet.")
        return

    game_pk = _safe_int(row.get("game_pk"), game_index)
    query = st.text_input(
        "Search player",
        placeholder="Name, team, position, confirmed/projected/bench",
        key=f"mx42_search_{game_pk}",
    ).strip()

    ordered = _ordered_player_indices(players)
    filtered = [i for i in ordered if _matches_search(players[i], query)]
    if not filtered:
        st.info("No players match that search. Clear the search to see the full roster.")
        prior_player = _safe_int(st.session_state.get("mh12_player", 0), 0)
        st.session_state["mh12_player"] = prior_player if 0 <= prior_player < len(players) else ordered[0]
        return

    prior_player = _safe_int(st.session_state.get("mh12_player", filtered[0]), filtered[0])
    default_player = prior_player if prior_player in filtered else filtered[0]
    selected = st.selectbox(
        "Player",
        filtered,
        index=filtered.index(default_player),
        format_func=lambda i: _player_label(players[int(i)]),
        key=f"mx42_player_{game_pk}",
    )
    st.session_state["mh12_player"] = _safe_int(selected, filtered[0])

    confirmed = sum(1 for p in players if _role(p)[0] == "Confirmed")
    projected = sum(1 for p in players if _role(p)[0] == "Projected")
    bench = sum(1 for p in players if _role(p)[0] == "Bench")
    st.markdown(
        f'<div class="mx42-roster-note">Confirmed {confirmed} • Projected {projected} • Bench/active {bench}</div>',
        unsafe_allow_html=True,
    )


def _legacy_selectbox_passthrough(original):
    """Return picker state for the two old selection widgets without drawing them twice."""
    def wrapped(label, options, *args, **kwargs):
        key = kwargs.get("key")
        if key in {"mh12_game", "mh12_player"}:
            values = list(options)
            if not values:
                return None
            wanted = _safe_int(st.session_state.get(key, values[0]), values[0])
            return wanted if wanted in values else values[0]
        return original(label, options, *args, **kwargs)

    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    _render_picker(games_df)

    original_selectbox = st.selectbox
    st.selectbox = _legacy_selectbox_passthrough(original_selectbox)
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_ordered_player_indices",
    "_player_label",
    "render_matchup_hub",
]
