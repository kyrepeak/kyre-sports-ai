"""NBA Spread Page 1 — Step 9 Kyre Fair Spread + Cover Probability.

Additive successor wrapper over frozen Step 8. It computes a sportsbook-
independent fair spread from NBA Official + ESPN score history, then uses the
verified sportsbook spread only as the threshold for cover probability. The
pregame model freezes at LIVE and is preserved through FINAL.
"""
from __future__ import annotations

from copy import deepcopy
from html import escape
from statistics import median

import streamlit as st

import nba_spread_page_v3 as step8
import nba_spread_page_v2 as step7_page
from nba_spread_fair_spread_probability_v1 import (
    STEP9_STATE_KEY,
    build_fair_spread_context,
    reconcile_step9_history,
)
from nba_spread_performance_history_v1 import load_verified_performance_history
from nba_spread_sportsbook_observations_v1 import load_verified_sportsbook_observations

MODEL_VERSION = "NBA_SPREAD_PAGE_V4_STEP9_FAIR_SPREAD_COVER"
STEP9_HEARTBEAT = "NBA_SPREAD_STEP9_FAIR_SPREAD_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = True
MAY_MODIFY_PROJECTION = True
MAY_MODIFY_PROBABILITY = True
MAY_MODIFY_RANKING = False
MAY_ACTIVATE_EDGE = False
MAY_ACTIVATE_PICK = False

_ORIGINAL_STEP8_SCHEDULE_LOADER = step8._ORIGINAL_LOAD_VERIFIED_SCHEDULE
_ORIGINAL_STEP8_GAME_CARD = step8._ORIGINAL_GAME_CARD


@st.cache_data(ttl=600, show_spinner=False)
def _load_performance_history(games: list[dict]) -> dict:
    return load_verified_performance_history(games)


@st.cache_data(ttl=90, show_spinner=False)
def _load_sportsbook_observations(games: list[dict]) -> dict:
    return load_verified_sportsbook_observations(games)


def _market_home_lines(games: list[dict]) -> dict[tuple[str, str], float]:
    payload = _load_sportsbook_observations(games)
    if payload.get("verification") != "VERIFIED":
        return {}
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in payload.get("observations") or []:
        away = str(row.get("away_tricode") or "").strip().upper()
        home = str(row.get("home_tricode") or "").strip().upper()
        try:
            home_spread = float(row.get("home_spread"))
        except (TypeError, ValueError):
            continue
        if away and home:
            grouped.setdefault((away, home), []).append(home_spread)
    return {key: float(median(values)) for key, values in grouped.items() if values}


def _availability_map(games: list[dict]) -> dict[tuple[str, str], dict]:
    upcoming = [game for game in games if str(game.get("status") or "").upper() in {"UPCOMING", "DELAYED"}]
    if not upcoming:
        return {}
    try:
        payload = step7_page._load_injury_availability(upcoming)
    except Exception:
        return {}
    out: dict[tuple[str, str], dict] = {}
    for feature in payload.get("features") or []:
        away = str(feature.get("away_tricode") or "").strip().upper()
        home = str(feature.get("home_tricode") or "").strip().upper()
        if away and home:
            out[(away, home)] = deepcopy(dict(feature))
    return out


def _model_map(games: list[dict]) -> dict[str, dict]:
    performance = _load_performance_history(games)
    if performance.get("verification") != "VERIFIED":
        return {}
    official = list(performance.get("official_history") or [])
    espn = list(performance.get("espn_history") or [])
    market_lines = _market_home_lines(games)
    availability = _availability_map(games)
    models: dict[str, dict] = {}
    for game in games:
        if str(game.get("status") or "").upper() not in {"UPCOMING", "DELAYED"}:
            continue
        key = str(game.get("game_key") or "").strip()
        away = str(game.get("away_tricode") or "").strip().upper()
        home = str(game.get("home_tricode") or "").strip().upper()
        if not key or not away or not home:
            continue
        model = build_fair_spread_context(
            game,
            official,
            espn,
            market_home_spread=market_lines.get((away, home)),
            availability_context=availability.get((away, home)),
        )
        if model.get("verification") == "VERIFIED":
            models[key] = model
    return models


def _load_schedule_with_step9() -> dict:
    schedule = _ORIGINAL_STEP8_SCHEDULE_LOADER()
    if schedule.get("verification") != "VERIFIED":
        return schedule
    games = list(schedule.get("games") or [])
    history = st.session_state.get(STEP9_STATE_KEY)
    if not isinstance(history, dict):
        history = {}
    reconciled = reconcile_step9_history(games, history, model_by_game=_model_map(games))
    st.session_state[STEP9_STATE_KEY] = reconciled["history"]
    out = deepcopy(schedule)
    out["games"] = reconciled["games"]
    out["step9_model_history_count"] = len(reconciled["history"])
    return out


def _pct(value: object) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _line(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:+.1f}".replace("+.0", "+0.0")


def _fair_spread_card(record: dict) -> str:
    verification = str(record.get("verification") or "UNAVAILABLE")
    diagnostic = escape(str(record.get("diagnostic_state") or "PREGAME_MODEL_MISSING"))
    phase = escape(str(record.get("phase") or "PREGAME"))
    model = dict(record.get("pregame_model") or {})
    if verification != "VERIFIED" or not model:
        return f"""
<div data-testid="nba-spread-step9-fair-spread" style="border:1px dashed rgba(103,216,255,.22);border-radius:16px;
padding:12px 14px;background:#09131f;margin:0 0 9px">
  <div style="font-size:.72rem;font-weight:950;color:#b9dceb">Kyre Fair Spread unavailable</div>
  <div style="font-size:.65rem;color:#71869a;margin-top:4px">Two-source verified performance history is required. Nothing is invented.</div>
  <div style="font-size:.61rem;color:#61778b;margin-top:5px">{diagnostic} • {phase}</div>
</div>
"""

    away = escape(str(model.get("away_tricode") or "AWAY"))
    home = escape(str(model.get("home_tricode") or "HOME"))
    fair_away = _line(model.get("fair_away_spread"))
    fair_home = _line(model.get("fair_home_spread"))
    projected = _line(model.get("projected_home_margin"))
    sigma = _line(model.get("margin_sd"))
    cover_verified = str(model.get("cover_verification") or "UNAVAILABLE") == "VERIFIED"
    home_cover = _pct(model.get("home_cover_probability")) if cover_verified else "Market unavailable"
    away_cover = _pct(model.get("away_cover_probability")) if cover_verified else "Market unavailable"
    push = _pct(model.get("push_probability")) if cover_verified else "—"
    market_home = _line(model.get("market_home_spread")) if cover_verified else "—"
    lock_label = "Frozen pregame model" if record.get("snapshot_frozen") else "Pregame model"
    return f"""
<div data-testid="nba-spread-step9-fair-spread" style="border:1px solid rgba(103,216,255,.32);border-radius:20px;
background:linear-gradient(140deg,rgba(7,18,31,.98),rgba(8,32,51,.96));padding:14px;margin:0 0 10px">
  <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
    <div>
      <div style="font-size:.67rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase;color:#67d8ff">Kyre Fair Spread</div>
      <div style="font-size:.9rem;font-weight:950;color:#f8fafc;margin-top:4px">{away} {fair_away} • {home} {fair_home}</div>
    </div>
    <div style="font-size:.61rem;font-weight:900;color:#9bdff7">{lock_label} • {phase}</div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:10px">
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:11px;padding:8px;background:rgba(5,12,20,.44)">
      <div style="font-size:.57rem;color:#71869a;text-transform:uppercase;font-weight:900">Projected Home Margin</div>
      <div style="font-size:.85rem;color:#f8fafc;font-weight:950;margin-top:3px">{projected}</div>
    </div>
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:11px;padding:8px;background:rgba(5,12,20,.44)">
      <div style="font-size:.57rem;color:#71869a;text-transform:uppercase;font-weight:900">Market Home Spread</div>
      <div style="font-size:.85rem;color:#f8fafc;font-weight:950;margin-top:3px">{market_home}</div>
    </div>
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:11px;padding:8px;background:rgba(5,12,20,.44)">
      <div style="font-size:.57rem;color:#71869a;text-transform:uppercase;font-weight:900">Model SD</div>
      <div style="font-size:.85rem;color:#f8fafc;font-weight:950;margin-top:3px">{sigma}</div>
    </div>
  </div>
  <div style="font-size:.62rem;font-weight:950;color:#cbd5e1;margin-top:10px">Cover Probability</div>
  <div style="font-size:.69rem;color:#dbeafe;margin-top:4px">{away}: {away_cover} • {home}: {home_cover} • Push: {push}</div>
  <div style="font-size:.58rem;color:#60788d;margin-top:6px">NBA Official + ESPN NBA performance quorum • sportsbook projection influence 0.0 • no edge/ranking/pick logic</div>
</div>
"""


def _game_card_with_step9(game: dict) -> str:
    base_html = _ORIGINAL_STEP8_GAME_CARD(game)
    record = dict(game.get("step9_fair_spread") or {})
    if not record:
        return base_html
    return _fair_spread_card(record) + base_html


def render_nba_spread_page() -> None:
    st.markdown(
        f'<div data-testid="nba-spread-step9-fair-spread-active" data-heartbeat="{STEP9_HEARTBEAT}" style="display:none!important"></div>',
        unsafe_allow_html=True,
    )
    original_loader = step8._ORIGINAL_LOAD_VERIFIED_SCHEDULE
    original_card = step8._ORIGINAL_GAME_CARD
    step8._ORIGINAL_LOAD_VERIFIED_SCHEDULE = _load_schedule_with_step9
    step8._ORIGINAL_GAME_CARD = _game_card_with_step9
    try:
        return step8.render_nba_spread_page()
    finally:
        step8._ORIGINAL_LOAD_VERIFIED_SCHEDULE = original_loader
        step8._ORIGINAL_GAME_CARD = original_card


__all__ = [
    "MODEL_VERSION",
    "STEP9_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_ACTIVATE_EDGE",
    "MAY_ACTIVATE_PICK",
    "render_nba_spread_page",
]
