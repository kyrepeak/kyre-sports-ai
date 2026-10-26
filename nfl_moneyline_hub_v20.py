"""NFL Moneyline V20 — Page 1 slate + selected-matchup Page 2 War Room."""
from __future__ import annotations

from datetime import date
from html import escape
from urllib.parse import quote

import pandas as pd
import streamlit as st

import nfl_moneyline_hub_v19 as prior
import nfl_moneyline_page2_war_room_v1 as war_room
from sports_api import nfl_moneyline_page2_v1 as page2_api

MODEL_VERSION = "NFL MONEYLINE V20 • PAGE2 WAR ROOM"
FROZEN_PRIOR = "nfl_moneyline_hub_v19"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        value = ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def _analysis_href(game: dict) -> str:
    gid = prior.presentation._gid(game)
    return f"?sport=nfl&market=moneyline&view=analysis&game={quote(str(gid), safe='')}"


def _page1() -> None:
    """Delegate Page 1 to V19 and inject only a selected-game analysis link."""
    original = prior.market_visual._market_matchup_html

    def _linked(game, final, edge_out, mc_out, snap, contexts, gameplans):
        html = original(game, final, edge_out, mc_out, snap, contexts, gameplans)
        href = _analysis_href(game)
        gid = escape(str(prior.presentation._gid(game)))
        link = (
            f'<div data-testid="nfl-moneyline-page2-link" data-game-id="{gid}" '
            'style="margin:.35rem .82rem .15rem">'
            f'<a href="{escape(href)}" target="_self" style="display:block;text-align:center;padding:10px 12px;'
            'border:1px solid rgba(88,201,255,.24);border-radius:10px;background:#071827;color:#8fdfff;'
            'font-size:.52rem;font-weight:950;letter-spacing:.045em;text-decoration:none">VIEW FULL ANALYSIS →</a></div>'
        )
        return html + link

    prior.market_visual._market_matchup_html = _linked
    try:
        prior.render_nfl_moneyline_hub()
    finally:
        prior.market_visual._market_matchup_html = original


def _selected_date() -> date:
    selected = st.session_state.get("nfl_v1_date") or st.session_state.get("nfl_active_slate_date") or date.today()
    try:
        return pd.to_datetime(selected).date()
    except Exception:
        return date.today()


def _page2(game_id: str) -> None:
    st.markdown('<div data-testid="nfl-moneyline-page2-runtime" style="display:none">NFL_MONEYLINE_PAGE2_WAR_ROOM_V1</div>', unsafe_allow_html=True)
    selected = _selected_date()
    prior.presentation._sync_frozen_date(selected)
    with st.spinner("Building selected-game Moneyline War Room…"):
        prior._silent_frozen_engine()

    pregame = list(st.session_state.get("nfl_moneyline_v3_pregame") or st.session_state.get("nfl_moneyline_v1_pregame") or [])
    game = next((dict(item) for item in pregame if str(prior.presentation._gid(item)) == str(game_id)), None)
    if game is None:
        st.markdown('<a href="?sport=nfl&market=moneyline" target="_self">← Back to Games</a>', unsafe_allow_html=True)
        st.warning("Selected Moneyline matchup is not available on the verified active slate. Return to Games and choose an upcoming matchup.")
        return

    gid = prior.presentation._gid(game)
    contexts = st.session_state.get("nfl_moneyline_v3_team_context") or st.session_state.get("nfl_moneyline_v2_team_context") or {}
    gameplans = st.session_state.get("nfl_moneyline_v3_gameplan_context") or {}
    edges = st.session_state.get("nfl_moneyline_v7_edge_outputs") or {}
    mc_outputs = st.session_state.get("nfl_moneyline_v6_mc_outputs") or {}
    snapshots = st.session_state.get("nfl_moneyline_v5_market_snapshots") or {}
    profiles = st.session_state.get("nfl_moneyline_v4_strength_profiles") or {}
    calibration = prior.presentation.frozen.v431.v43._fit_calibration_model()
    edge_out = edges.get(gid, {})
    mc_out = mc_outputs.get(gid, {})
    snap = snapshots.get(gid, {})
    final = prior.presentation.frozen._build_final(game, gid, edge_out, mc_out, snap, profiles, calibration)
    history = page2_api.load_matchup_history(game, limit=5, full_limit=100)
    context = page2_api.build_page2_context(
        game=game, final=final, edge_out=edge_out, mc_out=mc_out, snap=snap,
        profiles=profiles, contexts=contexts, gameplans=gameplans, history=history,
    )
    war_room.render_context(context)


def render_nfl_moneyline_hub() -> None:
    view = _query_value("view").lower()
    game_id = _query_value("game")
    if view == "analysis":
        return _page2(game_id)
    return _page1()


def render_nfl_hub(market: str = "Moneyline") -> None:
    if str(market or "Moneyline").lower() != "moneyline":
        raise RuntimeError("NFL Moneyline V20 handles Moneyline only.")
    return render_nfl_moneyline_hub()


__all__=["DISPLAY_ONLY","MODEL_VERSION","MONTE_CARLO_SIMULATIONS","PRESENTATION_ONLY","SPORTSBOOK_MODEL_INFLUENCE","SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED","render_nfl_hub","render_nfl_moneyline_hub"]