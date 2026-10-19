"""Minimal NBA Spread selected-game presentation seam.

This is an additive view over the exact selected-game consumer. It does not own
model, projection, probability, decision, or ranking math.
"""
from __future__ import annotations

from html import escape
from collections.abc import Mapping
from typing import Any

import streamlit as st

MODEL_VERSION = "NBA_SPREAD_PAGE2_SELECTED_GAME_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_FROZEN_STEPS = False

_CSS = r"""
<style>
.nba2-shell{border:1px solid rgba(56,189,248,.26);border-radius:20px;background:linear-gradient(145deg,#08131f,#0d2233);padding:16px 17px;margin:8px 0 12px}.nba2-kicker{font-size:.68rem;font-weight:950;letter-spacing:.1em;color:#67d8ff;text-transform:uppercase}.nba2-match{font-size:clamp(1.55rem,5vw,2.15rem);font-weight:950;color:#f8fafc;margin-top:4px}.nba2-sub{font-size:.78rem;color:#8ea4b7;margin-top:4px}.nba2-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:14px}.nba2-metric{border:1px solid rgba(148,163,184,.13);border-radius:12px;background:rgba(4,12,20,.46);padding:10px}.nba2-metric small{display:block;color:#738b9f;font-size:.62rem;font-weight:950;text-transform:uppercase}.nba2-metric b{display:block;color:#edf5fa;font-size:.86rem;margin-top:4px;line-height:1.35}.nba2-decision{border:1px solid rgba(103,216,255,.18);border-radius:12px;background:rgba(21,49,69,.45);padding:10px 11px;margin-top:10px}.nba2-decision strong{color:#f8fafc}.nba2-decision span{display:block;color:#8ca4b7;font-size:.72rem;margin-top:3px}.nba2-empty{border:1px dashed rgba(148,163,184,.18);border-radius:14px;padding:14px;color:#8da1b2}.nba2-inj{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.nba2-inj div{font-size:.73rem;color:#9bb0c0;background:rgba(5,13,20,.45);border-radius:10px;padding:8px}
@media(max-width:600px){.nba2-grid{grid-template-columns:1fr 1fr}.nba2-inj{grid-template-columns:1fr}}
</style>
"""


def _clean(value: object) -> str:
    return str(value or "").strip()


def _line(value: object) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{parsed:+g}" if parsed != 0 else "PK"


def _pct(value: object) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _selected_game_html(
    state: Mapping[str, Any],
    *,
    market: Mapping[str, Any],
    injuries: Mapping[str, Any],
) -> str:
    if state.get("verification") != "VERIFIED" or not isinstance(state.get("game"), Mapping):
        return '<div class="nba2-empty">Selected game is unavailable. Return to the NBA Spread slate and choose a verified matchup.</div>'

    game = dict(state.get("game") or {})
    away = _clean(game.get("away_tricode")).upper() or "AWAY"
    home = _clean(game.get("home_tricode")).upper() or "HOME"
    away_name = _clean(game.get("away_name")) or away
    home_name = _clean(game.get("home_name")) or home
    tip = _clean(game.get("tip_phoenix")) or "Time pending"
    date = _clean(game.get("game_date_phoenix")) or "Date pending"
    venue = _clean(game.get("venue"))

    fair_record = dict(state.get("fair_record") or {})
    fair_model = dict(fair_record.get("pregame_model") or {}) if isinstance(fair_record.get("pregame_model"), Mapping) else {}
    fair_verified = fair_record.get("verification") == "VERIFIED" and fair_model.get("verification") == "VERIFIED"
    fair_text = f"{away} {_line(fair_model.get('fair_away_spread'))} • {home} {_line(fair_model.get('fair_home_spread'))}" if fair_verified else "Verification pending"

    cover_verified = fair_verified and fair_model.get("cover_verification") == "VERIFIED"
    cover_text = f"{away} {_pct(fair_model.get('away_cover_probability'))} • {home} {_pct(fair_model.get('home_cover_probability'))}" if cover_verified else "Market threshold pending"

    market_text = "Market verification pending"
    market_label = _clean(market.get("label"))
    if market.get("verification") == "VERIFIED":
        market_text = f"{away} {_line(market.get('away_spread'))} • {home} {_line(market.get('home_spread'))}"
        if market_label:
            market_text += f" • {market_label}"

    decision = dict(state.get("decision_record") or {})
    if decision.get("verification") == "VERIFIED" and decision.get("decision_state") == "PLAY":
        decision_title = _clean(decision.get("pick_text")) or "VERIFIED PLAY"
        detail = " • ".join(item for item in (_clean(decision.get("pick_strength")), _clean(decision.get("production_grade"))) if item) or "Verified Step-10 decision"
    else:
        decision_title = "NO VERIFIED PLAY"
        detail = "Frozen Step-10 thresholds are not currently satisfied"

    away_inj = _clean(injuries.get("away_summary")) or f"{away}: status pending"
    home_inj = _clean(injuries.get("home_summary")) or f"{home}: status pending"
    venue_bit = f" • {escape(venue)}" if venue else ""

    return f'''<div class="nba2-shell" data-testid="nba-spread-selected-game-v1">
      <div class="nba2-kicker">KYRE SPORTS AI • NBA SPREAD • SELECTED GAME</div>
      <div class="nba2-match">{escape(away)} @ {escape(home)}</div>
      <div class="nba2-sub">{escape(away_name)} at {escape(home_name)} • {escape(tip)} • {escape(date)} Phoenix{venue_bit}</div>
      <div class="nba2-grid">
        <div class="nba2-metric"><small>Market</small><b>{escape(market_text)}</b></div>
        <div class="nba2-metric"><small>Kyre Fair Spread</small><b>{escape(fair_text)}</b></div>
        <div class="nba2-metric"><small>Cover Probability</small><b>{escape(cover_text)}</b></div>
        <div class="nba2-metric"><small>Model Boundary</small><b>Frozen Step-9 / Step-10</b></div>
      </div>
      <div class="nba2-inj"><div>{escape(away_inj)}</div><div>{escape(home_inj)}</div></div>
      <div class="nba2-decision"><strong>{escape(decision_title)}</strong><span>{escape(detail)}</span></div>
    </div>'''


def render_selected_game(
    state: Mapping[str, Any],
    *,
    market: Mapping[str, Any],
    injuries: Mapping[str, Any],
) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(_selected_game_html(state, market=market, injuries=injuries), unsafe_allow_html=True)


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_FROZEN_STEPS",
    "_selected_game_html",
    "render_selected_game",
]
