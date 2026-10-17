"""NFL Receiving Yards V20 — full-slate multi-source identity + ID proof cards."""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v2 as base_page
import nfl_receiving_yards_hub_v8 as market_page
import nfl_receiving_yards_hub_v18 as controller
import nfl_receiving_yards_hub_v19 as prior
import nfl_receiving_yards_multisource_v1 as multisource

MODEL_VERSION = "NFL RECEIVING YARDS V20 • FULL SLATE MULTI-SOURCE ID PROOF"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v19"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MULTI_SOURCE_REQUIRED = True
ALL_SLATE_GAMES_REQUIRED = True
_RAW_CONTEXT_LOADER = base_page._load_receiving_context

_CSS = r'''
<style>
.krecv20-proofrow{display:flex;flex-wrap:wrap;gap:5px;margin:4px 0 8px}
.krecv20-id{border:1px solid #294a37;border-radius:9px;background:#0a1510;padding:5px 7px;min-width:145px;line-height:1.22}
.krecv20-id b{display:block;color:#eef7f1;font-size:.59rem}.krecv20-id span{display:block;color:#7f9988;font-size:.45rem;margin-top:2px}
.krecv20-id em{font-style:normal;color:#80dca2;font-size:.43rem;font-weight:800}
.krecv20-sources{color:#769084;font-size:.48rem;margin:2px 0 6px}
@media(max-width:760px){.krecv20-id{min-width:128px;flex:1 1 44%;padding:5px 6px}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _team_id_cards_html_v20(team: dict[str, Any]) -> str:
    cards = []
    for player in team.get("players") or []:
        if not isinstance(player, dict):
            continue
        athlete_id = _safe(player.get("official_athlete_id"))
        if not athlete_id.isdigit():
            continue
        name = escape(_safe(player.get("player_name"), "Verified receiver"))
        pos = escape(_safe(player.get("position"), "REC").upper())
        jersey = _safe(player.get("jersey_number"))
        jersey_text = f" • #{escape(jersey)}" if jersey else ""
        cards.append(
            '<div class="krecv20-id">'
            f'<b>{name} • {pos}{jersey_text}</b>'
            f'<span>ESPN ID {escape(athlete_id)}</span>'
            '<em>VERIFIED • ESPN + NFLVERSE</em>'
            '</div>'
        )
    return '<div class="krecv20-proofrow">' + ''.join(cards) + '</div>' if cards else ''


def _load_context_v20(event_id: str) -> dict[str, Any]:
    context = multisource.load_multisource_context(
        str(event_id),
        raw_loader=_RAW_CONTEXT_LOADER,
        market_loader=market_page._load_receiving_market,
    )
    try:
        market = market_page._load_receiving_market(str(event_id))
    except Exception:
        market = {}
    return controller._filter_context_for_relevant_players(context, market)


def _render_player_board_v20(games) -> None:
    event_id = _safe(st.session_state.get(controller.EVENT_KEY))
    if not event_id.isdigit():
        return
    context = base_page._load_receiving_context(event_id)
    if context.get("ready") is not True:
        st.warning("Receiving Yards exact-ID context is not ready for this matchup. No player values were guessed.")
        return
    if context.get("data_available") is not True:
        st.info("No verified Receiving Yards player options are available for this matchup yet.")
        return

    event_row = controller._selected_event_row(games, event_id)
    st.markdown(
        '<div class="krecv18-match">'
        f'<b>{escape(_safe(event_row.get("away_team"), _safe(event_row.get("away_abbr"), "Away")))} @ '
        f'{escape(_safe(event_row.get("home_team"), _safe(event_row.get("home_abbr"), "Home")))}</b>'
        f'<span>{escape(_safe(event_row.get("game_date"), ""))} • ESPN {escape(event_id)} • key receiving options only</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    sources = " + ".join(context.get("sources_available") or ("ESPN", "NFLVERSE"))
    st.markdown(
        f'<div class="krecv20-sources">Identity/stat sources: {escape(sources)} • exact ESPN athlete IDs • FanDuel display-only • projection influence 0.0%</div>',
        unsafe_allow_html=True,
    )

    teams = [team for team in (context.get("teams") or []) if isinstance(team, dict)]
    teams.sort(key=lambda item: 0 if _safe(item.get("home_away")).lower() == "away" else 1)
    team_lookup = base_page._team_map(context)
    for team in teams:
        opponent = team_lookup.get(_safe(team.get("opponent_official_team_id")), {})
        abbr = _safe(team.get("team_abbreviation"), "NFL").upper()
        name = _safe(team.get("team_name"), abbr)
        players = [player for player in (team.get("players") or []) if isinstance(player, dict)]
        st.markdown(
            '<div class="krecv2-teamhead"><div>'
            f'<b>{escape(abbr)} • {escape(name)}</b>'
            f'<span>{len(players)} key receiving option{"s" if len(players) != 1 else ""}</span>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        id_html = _team_id_cards_html_v20(team)
        if id_html:
            st.markdown(id_html, unsafe_allow_html=True)
        if players:
            cards = "".join(base_page._player_card(player, team, opponent) for player in players)
            st.markdown(f'<div class="krecv2-grid">{cards}</div>', unsafe_allow_html=True)


def render_nfl_receiving_yards_hub() -> None:
    st.html(_CSS)
    original_loader = controller._load_relevant_context
    original_board = controller._render_clean_player_board
    controller._load_relevant_context = _load_context_v20
    controller._render_clean_player_board = _render_player_board_v20
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        controller._render_clean_player_board = original_board
        controller._load_relevant_context = original_loader


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V20 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "ALL_SLATE_GAMES_REQUIRED", "FROZEN_PRIOR", "MODEL_VERSION", "MULTI_SOURCE_REQUIRED",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "_load_context_v20", "_team_id_cards_html_v20",
    "render_nfl_hub", "render_nfl_receiving_yards_hub",
]
