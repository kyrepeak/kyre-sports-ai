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

MODEL_VERSION = "NFL MONEYLINE V20 • SIMPLE PAGE1 • PAGE2 WAR ROOM"
FROZEN_PRIOR = "nfl_moneyline_hub_v19"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000


_PAGE1_SIMPLE_CSS = r"""
<style data-nfl-moneyline-page1-simple="true">
.kml20-simple,.kml20-simple *{box-sizing:border-box}
.kml20-simple{margin:.58rem 0 .72rem;border:1px solid rgba(88,201,255,.22);border-radius:16px;background:linear-gradient(155deg,#091522,#061018);overflow:hidden;box-shadow:0 12px 32px rgba(0,0,0,.18)}
.kml20-simple-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:.76rem .82rem;border-bottom:1px solid rgba(88,201,255,.11)}
.kml20-simple-head small{display:block;color:#58c9ff;font-size:.47rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase}
.kml20-simple-head b{display:block;margin-top:2px;color:#f4f8fc;font-size:.9rem;line-height:1.2}
.kml20-action{flex:0 0 auto;border:1px solid #35536a;border-radius:999px;padding:5px 8px;color:#aac0d2;font-size:.48rem;font-weight:950;letter-spacing:.05em}
.kml20-action.play{border-color:#287b61;color:#79efbd}.kml20-action.lean{border-color:#806d2e;color:#f2d77b}.kml20-action.pass{border-color:#7e4f38;color:#efb37e}
.kml20-simple-grid{display:grid;grid-template-columns:1.15fr 1.15fr .8fr 1fr;gap:7px;padding:.75rem .82rem}
.kml20-cell{min-width:0;padding:.58rem .62rem;border:1px solid rgba(88,201,255,.11);border-radius:11px;background:#07131e}
.kml20-cell span{display:block;color:#72899e;font-size:.42rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}
.kml20-cell b{display:block;margin-top:.24rem;color:#edf6fc;font-size:.69rem;line-height:1.25;white-space:normal}
.kml20-cell strong{color:#8fe3ff;font-size:.77rem}.kml20-cell small{display:block;margin-top:2px;color:#6f879c;font-size:.44rem}
.kml20-link{padding:0 .82rem .78rem}.kml20-link a{display:block;text-align:center;padding:9px 11px;border:1px solid rgba(88,201,255,.24);border-radius:10px;background:#071827;color:#8fdfff;font-size:.51rem;font-weight:950;letter-spacing:.045em;text-decoration:none}
.kml20-link a:hover{border-color:rgba(88,201,255,.48);background:#0a2133}
@media(max-width:760px){.kml20-simple-grid{grid-template-columns:1fr 1fr}.kml20-simple-head{padding:.7rem}.kml20-simple-grid{padding:.68rem}.kml20-link{padding:0 .68rem .68rem}}
@media(max-width:430px){.kml20-simple-grid{grid-template-columns:1fr}.kml20-cell{padding:.55rem .58rem}}
</style>
"""


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


def _display_action(state: str) -> str:
    """Map the frozen final state to a display-only quick-decision label."""
    normalized = str(state or "").strip().upper()
    if normalized == "QUALIFIED":
        return "PLAY"
    if normalized == "LEAN / WATCH":
        return "LEAN"
    return "PASS"


def _display_confidence(state: str) -> str:
    """Human-facing confidence label derived only from the frozen final state."""
    normalized = str(state or "").strip().upper()
    if normalized == "QUALIFIED":
        return "HIGH"
    if normalized == "LEAN / WATCH":
        return "MEDIUM"
    if normalized in {"HIGH UNCERTAINTY", "NO PLAY"}:
        return "LOW"
    return "CHECK"


def _simple_matchup_html(
    game: dict,
    final: dict,
    edge_out: dict,
    mc_out: dict,
    snap: dict,
    contexts: dict,
    gameplans: dict,
) -> str:
    """Render Page 1 as a compact decision card without Page 2 analysis blocks."""
    del mc_out, snap, contexts, gameplans

    away = prior.presentation._safe(game.get("away_team"), "Away")
    home = prior.presentation._safe(game.get("home_team"), "Home")
    away_abbr = prior.presentation._safe(game.get("away_abbr"), "AWAY").upper()
    home_abbr = prior.presentation._safe(game.get("home_abbr"), "HOME").upper()
    tip = prior.presentation._safe(game.get("tip_et"), "TBD")
    venue = prior.presentation._safe(game.get("venue"), "Venue TBD")
    broadcast = prior.presentation._safe(game.get("broadcast"), "")

    state = prior.presentation._safe(final.get("state"), "GATED").upper()
    leader_side = prior.presentation._safe(final.get("leader_side"), "away").lower()
    if leader_side not in {"away", "home"}:
        leader_side = "away"
    leader_team = away if leader_side == "away" else home
    leader_edge = (edge_out or {}).get(leader_side) or {}

    model_p = leader_edge.get("model_p")
    if model_p is None:
        model_p = final.get("winner_probability_final")
    if model_p is None:
        model_p = final.get("winner_probability")

    best_price = leader_edge.get("best_price")
    best_book = prior.presentation._safe(leader_edge.get("best_book"), "Unavailable")
    edge = leader_edge.get("edge")
    action = _display_action(state)
    confidence = _display_confidence(state)
    action_class = action.lower()
    href = _analysis_href(game)
    gid = escape(str(prior.presentation._gid(game)))

    broadcast_html = f" • {escape(broadcast)}" if broadcast else ""
    return (
        f'<article class="kml20-simple" data-testid="nfl-moneyline-page1-simple-card" data-game-id="{gid}">'
        '<header class="kml20-simple-head"><div>'
        '<small>NFL MONEYLINE</small>'
        f'<b>{escape(away_abbr)} @ {escape(home_abbr)}</b>'
        f'</div><span class="kml20-action {action_class}">{escape(action)}</span></header>'
        '<div class="kml20-simple-grid">'
        '<div class="kml20-cell"><span>GAME TIME / VENUE</span>'
        f'<b>{escape(tip)}</b><small>{escape(venue)}{broadcast_html}</small></div>'
        '<div class="kml20-cell"><span>MODEL PICK / PROBABILITY</span>'
        f'<b>{escape(leader_team)}</b><strong>{prior.presentation._pct(model_p)}</strong></div>'
        '<div class="kml20-cell"><span>BEST ML</span>'
        f'<b>{prior.presentation._ml(best_price)}</b><small>{escape(best_book)}</small></div>'
        '<div class="kml20-cell"><span>EDGE / CONFIDENCE</span>'
        f'<b>{prior.presentation._pp(edge)}</b><small>{escape(confidence)}</small></div>'
        '</div>'
        f'<div class="kml20-link" data-testid="nfl-moneyline-page2-link"><a href="{escape(href)}" target="_self">VIEW FULL ANALYSIS →</a></div>'
        '</article>'
    )


def _page1() -> None:
    """Render the compact Page 1 while V19 continues to own frozen engine execution."""
    original_matchup = prior.market_visual._market_matchup_html
    original_diagnostics = prior._diagnostics
    original_css = prior._composed_css

    prior.market_visual._market_matchup_html = _simple_matchup_html
    prior._diagnostics = lambda *args, **kwargs: None
    prior._composed_css = lambda: original_css() + _PAGE1_SIMPLE_CSS
    try:
        prior.render_nfl_moneyline_hub()
    finally:
        prior._composed_css = original_css
        prior._diagnostics = original_diagnostics
        prior.market_visual._market_matchup_html = original_matchup


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