"""MLB Matchup Explorer V4.8 — cleanup Step 3 grouped roster access.

Presentation-only wrapper over the certified V2 Step 12 Matchup Explorer.
Builds on Cleanup Step 2 game cards and replaces the remaining player dropdown
with fast grouped roster buttons: confirmed lineup, projected lineup, then
bench/active roster. Projection, probability, calibration and ranking math stay
frozen underneath.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

import mlb_matchup_hub_v14 as roster
import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v42 as step1
import mlb_matchup_hub_v43 as step2

VERSION = "MLB Matchup Hub V4.8 • Cleanup Step 3"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"
FROZEN_STEP1_PRESENTATION = "mlb_matchup_hub_v42"
FROZEN_STEP2_PRESENTATION = "mlb_matchup_hub_v43"

_ROSTER_CSS = r"""
<style>
.mx44-head{border:1px solid #253e57;background:linear-gradient(145deg,#0b1724,#08111c);border-radius:18px;padding:14px 15px;margin:10px 0 10px}
.mx44-head-title{font-size:1.02rem;font-weight:950;color:#f8fafc;margin-bottom:2px}
.mx44-head-sub{font-size:.68rem;color:#8fa4b9;line-height:1.38}
.mx44-selected{border:1px solid #2b4c68;background:#0a1622;border-radius:14px;padding:9px 11px;margin:6px 0 10px}
.mx44-selected-label{font-size:.54rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#69d9ff}
.mx44-selected-name{font-size:.88rem;font-weight:900;color:#f7fafc;margin-top:2px}
.mx44-group{font-size:.76rem;font-weight:900;color:#e8f2fb;margin:12px 0 5px}
.mx44-team{font-size:.59rem;font-weight:850;letter-spacing:.04em;text-transform:uppercase;color:#839bb1;margin:3px 0 5px}
.mx44-meta{font-size:.55rem;color:#7890a6;margin:-6px 0 7px 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mx44-counts{font-size:.59rem;color:#7890a6;margin:3px 0 7px}
@media(max-width:640px){.mx44-head{padding:12px;border-radius:16px}.mx44-head-title{font-size:.96rem}.mx44-selected-name{font-size:.82rem}.mx44-meta{font-size:.51rem}}
</style>
"""


def _safe_int(value: Any, default: int = 0) -> int:
    return step1._safe_int(value, default)


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _choose_player(index: int) -> None:
    st.session_state["mh12_player"] = int(index)
    st.session_state["mx44_last_player"] = int(index)


def _button_label(player: dict[str, Any], selected: bool = False) -> str:
    role_label, _ = step1._role(player)
    slot = _safe_int(player.get("slot"), 99)
    slot_text = f"#{slot} " if role_label != "Bench" and 1 <= slot <= 9 else ""
    mark = "✓ " if selected else ""
    return f"{mark}{slot_text}{str(player.get('name') or 'Player')}"


def _player_meta(player: dict[str, Any]) -> str:
    team = str(player.get("team") or "")
    position = str(player.get("position") or "").strip()
    return " • ".join(value for value in (team, position) if value) or "Active roster"


def _grouped_indices(players: list[dict[str, Any]], indices: list[int]) -> dict[str, list[int]]:
    groups = {"Confirmed": [], "Projected": [], "Bench": []}
    for index in indices:
        role_label, _ = step1._role(players[int(index)])
        groups.setdefault(role_label, []).append(int(index))
    return groups


def _team_split(players: list[dict[str, Any]], indices: list[int]) -> tuple[list[int], list[int]]:
    away = [i for i in indices if str(players[i].get("side") or "").lower() == "away"]
    home = [i for i in indices if str(players[i].get("side") or "").lower() == "home"]
    other = [i for i in indices if i not in away and i not in home]
    away.extend(other)
    return away, home


def _render_player_buttons(
    players: list[dict[str, Any]],
    indices: list[int],
    game_pk: int,
    group_key: str,
) -> None:
    if not indices:
        return

    away_indices, home_indices = _team_split(players, indices)
    columns = st.columns(2, gap="small")
    for side_name, side_indices, col in (
        ("Away", away_indices, columns[0]),
        ("Home", home_indices, columns[1]),
    ):
        with col:
            if side_indices:
                team_name = str(players[side_indices[0]].get("team") or side_name)
                st.markdown(f'<div class="mx44-team">{_esc(team_name)}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="mx44-team">{side_name}</div>', unsafe_allow_html=True)

            for player_index in side_indices:
                player = players[player_index]
                selected = _safe_int(st.session_state.get("mh12_player", 0), 0) == player_index
                player_id = _safe_int(player.get("id"), player_index)
                st.button(
                    _button_label(player, selected),
                    key=f"mx44_{group_key}_{game_pk}_{player_id}_{player_index}",
                    use_container_width=True,
                    disabled=selected,
                    on_click=_choose_player,
                    args=(player_index,),
                )
                st.markdown(
                    f'<div class="mx44-meta">{_esc(_player_meta(player))}</div>',
                    unsafe_allow_html=True,
                )


def _render_roster_groups(games_df, game_index: int) -> None:
    row = games_df.iloc[int(game_index)]
    players = roster._all_hitters_v14(row)
    if not players:
        st.warning("No active hitters are available for this matchup yet.")
        return

    game_pk = _safe_int(row.get("game_pk"), game_index)
    prior_player = _safe_int(st.session_state.get("mh12_player", 0), 0)
    if prior_player < 0 or prior_player >= len(players):
        prior_player = step1._ordered_player_indices(players)[0]
        st.session_state["mh12_player"] = prior_player

    st.markdown(_ROSTER_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="mx44-head"><div class="mx44-head-title">Choose a player</div>'
        '<div class="mx44-head-sub">Starters are separated from the bench so you can get to the right hitter without digging through one long dropdown.</div></div>',
        unsafe_allow_html=True,
    )

    selected_player = players[prior_player]
    selected_role, _ = step1._role(selected_player)
    st.markdown(
        '<div class="mx44-selected"><div class="mx44-selected-label">Selected player</div>'
        f'<div class="mx44-selected-name">{_esc(step1._player_label(selected_player))}</div></div>',
        unsafe_allow_html=True,
    )

    query = st.text_input(
        "Search player",
        placeholder="Name, team, position, confirmed/projected/bench",
        key=f"mx44_search_{game_pk}",
    ).strip()

    ordered = step1._ordered_player_indices(players)
    filtered = [i for i in ordered if step1._matches_search(players[i], query)]
    if not filtered:
        st.info("No players match that search. Clear the search to see the full roster.")
        return

    grouped = _grouped_indices(players, filtered)
    confirmed_total = sum(1 for p in players if step1._role(p)[0] == "Confirmed")
    projected_total = sum(1 for p in players if step1._role(p)[0] == "Projected")
    bench_total = sum(1 for p in players if step1._role(p)[0] == "Bench")
    st.markdown(
        f'<div class="mx44-counts">Confirmed {confirmed_total} • Projected {projected_total} • Bench/active {bench_total}</div>',
        unsafe_allow_html=True,
    )

    if grouped["Confirmed"]:
        st.markdown(
            f'<div class="mx44-group">✅ Confirmed lineup ({len(grouped["Confirmed"])})</div>',
            unsafe_allow_html=True,
        )
        _render_player_buttons(players, grouped["Confirmed"], game_pk, "confirmed")

    if grouped["Projected"]:
        st.markdown(
            f'<div class="mx44-group">🕒 Projected lineup ({len(grouped["Projected"])})</div>',
            unsafe_allow_html=True,
        )
        _render_player_buttons(players, grouped["Projected"], game_pk, "projected")

    if grouped["Bench"]:
        bench_selected = selected_role == "Bench"
        with st.expander(
            f"🪑 Bench / active roster ({len(grouped['Bench'])})",
            expanded=bool(query) or bench_selected,
        ):
            _render_player_buttons(players, grouped["Bench"], game_pk, "bench")


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    game_index = step2._render_game_cards(games_df)
    _render_roster_groups(games_df, game_index)

    original_selectbox = st.selectbox
    st.selectbox = step1._legacy_selectbox_passthrough(original_selectbox)
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP1_PRESENTATION",
    "FROZEN_STEP2_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_button_label",
    "_grouped_indices",
    "_render_roster_groups",
    "render_matchup_hub",
]
