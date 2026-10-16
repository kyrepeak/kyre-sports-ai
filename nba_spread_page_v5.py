"""NBA Spread Page 1 — Step 10 final decision / ranking layer.

Additive successor wrapper over frozen Step 9. It consumes only the Step-9
fair-spread / cover-probability snapshot and adds deterministic edge, production
grade, Pick Strength, slate ranking, and final spread pick presentation.
"""
from __future__ import annotations

from copy import deepcopy
from html import escape

import streamlit as st

import nba_spread_page_v4 as step9
from nba_spread_decision_v1 import decorate_and_rank_games

MODEL_VERSION = "NBA_SPREAD_PAGE_V5_STEP10_DECISION"
STEP10_HEARTBEAT = "NBA_SPREAD_STEP10_DECISION_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = True
MAY_ACTIVATE_EDGE = True
MAY_ACTIVATE_PICK = True

_ORIGINAL_STEP9_SCHEDULE_LOADER = step9._load_schedule_with_step9
_ORIGINAL_STEP9_GAME_CARD = step9._game_card_with_step9


def _load_schedule_with_step10() -> dict:
    schedule = _ORIGINAL_STEP9_SCHEDULE_LOADER()
    if schedule.get("verification") != "VERIFIED":
        return schedule
    ranked = decorate_and_rank_games(list(schedule.get("games") or []))
    out = deepcopy(schedule)
    out["games"] = ranked["games"]
    out["step10_play_count"] = ranked["play_count"]
    out["step10_top_pick_game_key"] = ranked["top_pick_game_key"]
    out["step10_verification"] = ranked["verification"]
    return out


def _pct(value: object) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _number(value: object, suffix: str = "") -> str:
    try:
        return f"{float(value):.1f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def _decision_card(record: dict) -> str:
    verification = str(record.get("verification") or "UNAVAILABLE")
    decision_state = str(record.get("decision_state") or "NO_PLAY")
    diagnostic = escape(str(record.get("diagnostic_state") or "STEP9_RECORD_REQUIRED"))
    phase = escape(str(record.get("phase") or "PREGAME"))
    if verification != "VERIFIED" or decision_state != "PLAY":
        return f"""
<div data-testid="nba-spread-step10-decision" style="border:1px dashed rgba(103,216,255,.22);border-radius:16px;padding:12px 14px;background:#09131f;margin:0 0 9px">
  <div style="font-size:.72rem;font-weight:950;color:#b9dceb">Final Decision • NO PLAY</div>
  <div style="font-size:.64rem;color:#71869a;margin-top:4px">Verified Step-9 inputs and at least a 2.0 percentage-point no-push edge are required.</div>
  <div style="font-size:.61rem;color:#61778b;margin-top:5px">{diagnostic} • {phase}</div>
</div>
"""

    team = escape(str(record.get("selected_team") or "—"))
    pick = escape(str(record.get("pick_text") or "NO PLAY"))
    strength = escape(str(record.get("pick_strength") or "NO PLAY"))
    grade = escape(str(record.get("production_grade") or "WATCH"))
    rank = record.get("slate_rank")
    rank_text = f"#{int(rank)}" if isinstance(rank, int) and rank > 0 else "—"
    top = " • TOP PICK" if record.get("top_pick") else ""
    cover = _pct(record.get("selected_cover_probability_no_push"))
    raw_cover = _pct(record.get("selected_cover_probability"))
    edge = _number(record.get("cover_edge_pp"), " pp")
    spread_edge = _number(record.get("spread_edge_points"), " pts")
    frozen = "Frozen pregame inputs" if record.get("snapshot_frozen") else "Pregame inputs"
    return f"""
<div data-testid="nba-spread-step10-decision" style="border:1px solid rgba(103,216,255,.38);border-radius:20px;background:linear-gradient(140deg,rgba(7,18,31,.99),rgba(8,38,58,.97));padding:14px;margin:0 0 10px">
  <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
    <div>
      <div style="font-size:.66rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase;color:#67d8ff">Final Spread Decision</div>
      <div style="font-size:1rem;font-weight:950;color:#f8fafc;margin-top:4px">{pick}</div>
      <div style="font-size:.61rem;color:#7690a5;margin-top:4px">{team} • {frozen} • {phase}</div>
    </div>
    <div style="font-size:.68rem;font-weight:950;color:#9bdff7">RANK {rank_text}{top}</div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:10px">
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:11px;padding:8px;background:rgba(5,12,20,.44)"><div style="font-size:.55rem;color:#71869a;font-weight:900">NO-PUSH COVER</div><div style="font-size:.83rem;color:#f8fafc;font-weight:950;margin-top:3px">{cover}</div></div>
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:11px;padding:8px;background:rgba(5,12,20,.44)"><div style="font-size:.55rem;color:#71869a;font-weight:900">RAW COVER</div><div style="font-size:.83rem;color:#f8fafc;font-weight:950;margin-top:3px">{raw_cover}</div></div>
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:11px;padding:8px;background:rgba(5,12,20,.44)"><div style="font-size:.55rem;color:#71869a;font-weight:900">Cover Edge</div><div style="font-size:.83rem;color:#f8fafc;font-weight:950;margin-top:3px">{edge}</div></div>
    <div style="border:1px solid rgba(148,163,184,.13);border-radius:11px;padding:8px;background:rgba(5,12,20,.44)"><div style="font-size:.55rem;color:#71869a;font-weight:900">SPREAD EDGE</div><div style="font-size:.83rem;color:#f8fafc;font-weight:950;margin-top:3px">{spread_edge}</div></div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;font-size:.62rem;font-weight:950;color:#dbeafe">
    <span>Pick Strength • {strength}</span><span>Production Grade • {grade}</span>
  </div>
  <div style="font-size:.57rem;color:#60788d;margin-top:7px">Decision-only layer • Step-9 model/probability unchanged • sportsbook projection influence 0.0</div>
</div>
"""


def _game_card_with_step10(game: dict) -> str:
    base_html = _ORIGINAL_STEP9_GAME_CARD(game)
    record = dict(game.get("step10_decision") or {})
    if not record:
        return base_html
    return _decision_card(record) + base_html


def render_nba_spread_page() -> None:
    st.markdown(
        f'<div data-testid="nba-spread-step10-decision-active" data-heartbeat="{STEP10_HEARTBEAT}" style="display:none!important"></div>',
        unsafe_allow_html=True,
    )
    original_loader = step9._load_schedule_with_step9
    original_card = step9._game_card_with_step9
    step9._load_schedule_with_step9 = _load_schedule_with_step10
    step9._game_card_with_step9 = _game_card_with_step10
    try:
        return step9.render_nba_spread_page()
    finally:
        step9._load_schedule_with_step9 = original_loader
        step9._game_card_with_step9 = original_card


__all__ = [
    "MODEL_VERSION",
    "STEP10_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_ACTIVATE_EDGE",
    "MAY_ACTIVATE_PICK",
    "render_nba_spread_page",
]
