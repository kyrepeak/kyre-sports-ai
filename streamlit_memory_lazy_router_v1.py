"""Kyre Sports AI Streamlit memory-safe lazy router.

This entrypoint loads exactly one sport/market stack per rerun. It replaces the
historical nested-app replay on Streamlit Community Cloud, where multiple frozen
wrappers eagerly imported MLB and WNBA production chains even when those routes
were not selected.

Model/projection math is not implemented here. Every route delegates to the
existing frozen/current production module for that market.
"""
from __future__ import annotations

import gc
from html import escape
import importlib
import sys
from typing import Any

import streamlit as st


MODEL_VERSION = "KYRE STREAMLIT MEMORY LAZY ROUTER V1"

MLB_MARKETS = [
    "Slate",
    "1+ Hit",
    "2+ Hits",
    "Home Run",
    "Hits + Runs + RBIs",
    "Pitcher Strikeouts",
    "Matchup Explorer",
    "Daily Game Picks",
    "Moneyline",
    "Run Line",
    "Game Total",
    "Live Game",
]

WNBA_MARKETS = [
    "Points",
    "Rebounds",
    "Assists",
    "Rebounds + Assists",
    "PRA",
    "Spread",
    "Moneyline",
    "Game Total",
    "Daily Picks",
]

NFL_MARKETS = [
    "Slate",
    "Moneyline",
    "Spread",
    "Game Total",
    "Passing Yards",
    "Rushing Yards",
    "Receiving Yards",
    "Receptions",
    "Passing TDs",
    "Anytime TD",
    "Daily Picks",
]

_ROUTE_MODULE_PREFIXES = (
    "wnba_",
    "mlb_",
    "hit_hub_",
    "moneyline_hub_",
    "spread_hub_",
    "totals_hub_",
    "live_game_hub_",
    "slate_hub_",
)
_ROUTE_TOKEN_KEY = "_ks_memory_lazy_route_v1"


def h(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def status_info(status: Any) -> tuple[str, str]:
    text = str(status or "Unknown")
    low = text.lower()
    if any(x in low for x in ("final", "game over", "completed")):
        return "FINAL", "ks-final"
    if any(x in low for x in ("in progress", "live", "delayed")):
        return "LIVE", "ks-live"
    return "PREGAME", "ks-pregame"


def team_logo(team_id: Any) -> str:
    if team_id is None:
        return ""
    try:
        tid = int(float(team_id))
    except (TypeError, ValueError):
        return ""
    return (
        f'<img class="ks-team-logo" '
        f'src="https://www.mlbstatic.com/team-logos/{tid}.svg" '
        f'alt="team logo" loading="lazy">'
    )


def section_header(title: Any, subtitle: Any = "") -> None:
    st.markdown(
        '<div class="ks-section">'
        f"<h2>{h(title)}</h2>"
        f'<div class="ks-kicker">{h(subtitle)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _apply_shell_css() -> None:
    st.markdown(
        r"""
<style>
:root{--ks-bg:#080d16;--ks-panel:#0f1726;--ks-border:rgba(148,163,184,.18);--ks-text:#f8fafc;--ks-muted:#94a3b8;--ks-blue:#38bdf8}
.stApp{background:radial-gradient(circle at 12% 0%,rgba(37,99,235,.14),transparent 32rem),var(--ks-bg)}
.block-container{max-width:1180px;padding-top:1rem;padding-bottom:4rem}
.ks-shell{border:1px solid var(--ks-border);border-radius:20px;padding:17px 19px;margin-bottom:13px;background:linear-gradient(135deg,rgba(37,99,235,.17),rgba(15,23,38,.96))}
.ks-eyebrow{color:var(--ks-blue);font-size:.72rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
.ks-title{color:var(--ks-text);font-size:clamp(1.8rem,5vw,2.8rem);font-weight:950;letter-spacing:-.04em;margin-top:4px}
.ks-sub{color:var(--ks-muted);font-size:.82rem;margin-top:5px}
.ks-section{margin:19px 0 9px}.ks-section h2{margin:0;color:var(--ks-text);font-size:1.35rem}.ks-kicker{color:var(--ks-muted);font-size:.78rem;margin-top:3px}
.ks-team-logo{width:34px;height:34px;object-fit:contain}
.ks-route{color:#9fd8ff;font-size:.70rem;font-weight:800;margin:2px 0 10px}
div[data-testid="stSelectbox"] div[data-baseweb="select"]>div{min-height:56px!important;border-radius:14px!important}
@media(max-width:640px){div[data-testid="stSelectbox"] div[data-baseweb="select"]>div{min-height:60px!important}}
</style>
""",
        unsafe_allow_html=True,
    )


def _route_token(sport: str, market: str, live_odds: bool = False) -> str:
    suffix = ":LIVE_ODDS" if live_odds else ""
    return f"{sport.upper()}:{market}{suffix}"


def _purge_route_modules_if_needed(token: str) -> int:
    """Release old sport/market module graphs only when the selected route changes."""
    previous = str(st.session_state.get(_ROUTE_TOKEN_KEY) or "")
    if previous == token:
        return 0

    removed = 0
    for name in list(sys.modules):
        if name == __name__:
            continue
        if name.startswith(_ROUTE_MODULE_PREFIXES):
            sys.modules.pop(name, None)
            removed += 1

    importlib.invalidate_caches()
    gc.collect()
    st.session_state[_ROUTE_TOKEN_KEY] = token
    return removed


def _import(name: str):
    return importlib.import_module(name)


def _install_step8f_for_market(market: str) -> None:
    if market not in {"Pitcher Strikeouts", "1+ Hit", "Hits + Runs + RBIs"}:
        return
    bridge = _import("mlb_step8f_player_prop_presentation_v1")
    bridge.install_step8f_player_prop_presentation()


def _load_mlb_schedule():
    import pandas as pd

    schedule = _import("mlb_schedule_v32")
    try:
        day = schedule.current_selected_date()
    except Exception:
        day = pd.Timestamp.now(tz="America/New_York").date().isoformat()

    try:
        day = schedule.render_slate_date_control()
    except Exception:
        pass

    try:
        games_df = schedule.games_for_date(day)
    except Exception as exc:
        games_df = pd.DataFrame()
        st.warning(f"MLB schedule could not be loaded: {type(exc).__name__}")

    return games_df, str(day)[:10]


def _render_mlb_live_odds() -> None:
    page = _import("mlb_live_odds_streamlit_v1")
    page.render_mlb_live_odds_page()


def _render_mlb(market: str) -> None:
    if market == "2+ Hits":
        section_header("MLB 2+ Hits", "Dedicated production module not enabled yet.")
        st.info("The current 1+ Hit model displays 2+ probability, but the standalone 2+ Hits route remains unbuilt.")
        return

    games_df, day = _load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")

    if market in {"1+ Hit", "Pitcher Strikeouts", "Hits + Runs + RBIs"}:
        _install_step8f_for_market(market)

    if market == "Slate":
        mod = _import("mlb_slate_hub_v32")
        mod.render_slate_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "1+ Hit":
        mod = _import("mlb_hit_hub_v1315")
        mod.render_hit_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Home Run":
        mod = _import("mlb_hr_hub_v11")
        mod.render_home_run_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Hits + Runs + RBIs":
        hit = _import("mlb_hit_hub_v1315")
        active = getattr(hit, "active", None)
        candidate_pool = getattr(active, "_candidate_pool", None)
        if candidate_pool is not None:
            hit._candidate_pool = candidate_pool
        mod = _import("mlb_hrrbi_hub_v115")
        mod.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Pitcher Strikeouts":
        mod = _import("mlb_pitcher_k_hub_v1017")
        mod.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Matchup Explorer":
        mod = _import("mlb_matchup_hub_v27")
        mod.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Daily Game Picks":
        mod = _import("mlb_daily_game_picks_v217_guard")
        mod.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
    elif market == "Moneyline":
        mod = _import("mlb_moneyline_hub_v164")
        mod.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Run Line":
        mod = _import("mlb_spread_hub_v157")
        mod.render_spread_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Game Total":
        mod = _import("mlb_totals_hub_v174")
        mod.render_totals_hub(games_df, section_header, status_info, team_logo, h)
    elif market == "Live Game":
        try:
            state_bridge = _import("mlb_step9c_live_state_consumer_v1")
            state_bridge.install_step9c_live_state_consumer()
        except Exception as exc:
            st.caption(f"Live state bridge fallback: {type(exc).__name__}")
        try:
            market_bridge = _import("mlb_step9e_live_market_consumer_v1")
            market_bridge.install_step9e_live_market_consumer()
        except Exception as exc:
            st.caption(f"Live market bridge fallback: {type(exc).__name__}")
        mod = _import("mlb_live_hub_v193")
        mod.render_live_hub(games_df, section_header, status_info, team_logo, h)
    else:
        st.error(f"Unknown MLB market: {market}")


def _install_wnba_schedule_bridge() -> None:
    try:
        bridge = _import("wnba_api_schedule_bridge_v1")
        bridge.install_wnba_api_schedule_bridge()
    except Exception as exc:
        st.caption(f"WNBA API schedule bridge fallback: {type(exc).__name__}")


def _render_wnba(market: str) -> None:
    _install_wnba_schedule_bridge()
    st.caption(f"🏀 WNBA • lazy route: {market}")

    if market == "Points":
        mod = _import("wnba_points_hub_v19847")
        mod.render_wnba_points_hub(section_header, status_info, None, h)
    elif market == "Rebounds":
        mod = _import("wnba_rebounds_hub_v12")
        mod.render_wnba_rebounds_hub(section_header, status_info, None, h)
    elif market == "Assists":
        mod = _import("wnba_assists_hub_v20")
        mod.render_wnba_assists_hub(section_header, status_info, None, h)
    elif market == "Rebounds + Assists":
        mod = _import("wnba_ra_hub_v1")
        mod.render_wnba_ra_hub(section_header, status_info, None, h)
    elif market == "PRA":
        mod = _import("wnba_pra_hub_v3612")
        mod.render_wnba_pra_hub(section_header, status_info, None, h)
    elif market == "Spread":
        mod = _import("wnba_spread_hub_v162")
        mod.render_wnba_spread_hub(section_header, status_info, None, h)
    elif market == "Moneyline":
        mod = _import("wnba_moneyline_hub_v15")
        mod.render_wnba_moneyline_hub(section_header, status_info, None, h)
    elif market == "Game Total":
        mod = _import("wnba_game_total_hub_v15")
        mod.render_wnba_game_total_hub(section_header, status_info, None, h)
    elif market == "Daily Picks":
        bridge = _import("wnba_step18c_consumer_bridge_v1")
        bridge.install_step18c_consumer_bridge()
        mod = _import("wnba_daily_picks_hub_v34")
        mod.render_wnba_daily_picks_hub(section_header, status_info, None, h)
    else:
        st.error(f"Unknown WNBA market: {market}")


def _render_nfl(market: str) -> None:
    st.caption(f"🏈 NFL • lazy route: {market}")
    mod = _import("nfl_hub_v18")
    mod.render_nfl_hub(market)


def render_app() -> None:
    st.set_page_config(
        page_title="Kyre Sports AI",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="auto",
    )
    _apply_shell_css()

    st.markdown(
        '<div class="ks-shell">'
        '<div class="ks-eyebrow">Sports projection intelligence</div>'
        '<div class="ks-title">🧠 KYRE SPORTS AI</div>'
        '<div class="ks-sub">Memory-safe lazy loading • one sport and one market stack at a time.</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    if str(st.session_state.get("ks_wnba_market_touch") or "") == "Live Games":
        st.session_state.pop("ks_wnba_market_touch", None)

    sport = st.selectbox(
        "🏟️ Sport",
        ["MLB", "WNBA", "NFL"],
        key="ks_sport_touch",
    )

    if sport == "MLB":
        market = st.selectbox(
            "🎯 MLB Market",
            MLB_MARKETS,
            key="ks_mlb_market_touch",
        )
    elif sport == "WNBA":
        if str(st.session_state.get("ks_wnba_market_touch") or "") not in WNBA_MARKETS:
            st.session_state.pop("ks_wnba_market_touch", None)
        market = st.selectbox(
            "🎯 WNBA Market",
            WNBA_MARKETS,
            index=4,
            key="ks_wnba_market_touch",
        )
    else:
        if str(st.session_state.get("ks_nfl_market_touch") or "") not in NFL_MARKETS:
            st.session_state.pop("ks_nfl_market_touch", None)
        market = st.selectbox(
            "🎯 NFL Market",
            NFL_MARKETS,
            key="ks_nfl_market_touch",
        )

    live_odds = bool(sport == "MLB" and st.session_state.get("ks_mlb_live_odds_route") is True)

    if sport == "MLB":
        if live_odds:
            st.sidebar.caption("MLB Live Odds is open.")
        elif st.sidebar.button("⚾ MLB Live Odds", key="ks_mlb_live_odds_launch", use_container_width=True):
            st.session_state["ks_mlb_live_odds_route"] = True
            st.rerun()

    token = _route_token(sport, market, live_odds=live_odds)
    removed = _purge_route_modules_if_needed(token)
    st.markdown(
        f'<div class="ks-route">{h(MODEL_VERSION)} • active: {h(sport)} → {h("MLB Live Odds" if live_odds else market)}'
        + (f" • released {removed} stale route modules" if removed else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    if live_odds:
        _render_mlb_live_odds()
        return

    if sport == "MLB":
        _render_mlb(market)
    elif sport == "WNBA":
        _render_wnba(market)
    else:
        _render_nfl(market)

    st.caption("Model probabilities are estimates — not guarantees.")


__all__ = [
    "MODEL_VERSION",
    "MLB_MARKETS",
    "WNBA_MARKETS",
    "NFL_MARKETS",
    "_purge_route_modules_if_needed",
    "_route_token",
    "render_app",
]
