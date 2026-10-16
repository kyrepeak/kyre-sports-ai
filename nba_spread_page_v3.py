"""NBA Spread Page 1 — Step 8 Kyre Sports Preview / Live-Final behavior.

Additive wrapper over the frozen Step-7 injury/availability page. It decorates
the verified schedule with an in-session pregame snapshot lifecycle, then adds
small preview-state callouts to existing game cards. Steps 1-7 remain delegated
unchanged; Step 8 does not add a fair spread, probability, edge, or ranking.
"""
from __future__ import annotations

from copy import deepcopy
from html import escape

import streamlit as st

import nba_spread_page_v2 as step7
import nba_spread_page_v1 as page_v1
from nba_spread_live_final_v1 import PREVIEW_STATE_KEY, reconcile_preview_history

MODEL_VERSION = "NBA_SPREAD_PAGE_V3_STEP8_LIVE_FINAL_BEHAVIOR"
STEP8_HEARTBEAT = "NBA_SPREAD_STEP8_LIVE_FINAL_ACTIVE"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False

_ORIGINAL_LOAD_VERIFIED_SCHEDULE = page_v1._load_verified_schedule
_ORIGINAL_GAME_CARD = page_v1._game_card


def _context_for_game(game: dict) -> dict:
    """Capture only descriptive verified pregame identity/context owned by Steps 1-7."""
    return {
        "tip_phoenix": game.get("tip_phoenix"),
        "game_date_phoenix": game.get("game_date_phoenix"),
        "venue": game.get("venue"),
        "confirming_sources": deepcopy(game.get("confirming_sources") or []),
        "source_game_ids": deepcopy(game.get("source_game_ids") or {}),
    }


def _load_schedule_with_preview() -> dict:
    schedule = _ORIGINAL_LOAD_VERIFIED_SCHEDULE()
    if schedule.get("verification") != "VERIFIED":
        return schedule

    games = list(schedule.get("games") or [])
    history = st.session_state.get(PREVIEW_STATE_KEY)
    if not isinstance(history, dict):
        history = {}
    context_by_game = {
        str(game.get("game_key")): _context_for_game(game)
        for game in games
        if str(game.get("game_key") or "").strip()
    }
    reconciled = reconcile_preview_history(
        games,
        history,
        context_by_game=context_by_game,
    )
    st.session_state[PREVIEW_STATE_KEY] = reconciled["history"]
    out = deepcopy(schedule)
    out["games"] = reconciled["games"]
    out["step8_preview_history_count"] = len(reconciled["history"])
    return out


def _preview_banner(preview: dict) -> str:
    phase = str(preview.get("phase") or "PREGAME")
    verification = str(preview.get("verification") or "UNAVAILABLE")
    diagnostic = escape(str(preview.get("diagnostic_state") or "UNKNOWN"))

    if verification != "VERIFIED":
        return f"""
<div data-testid="nba-spread-step8-preview" style="border:1px dashed rgba(103,216,255,.22);border-radius:14px;
padding:9px 12px;background:#09131f;margin:0 0 8px;color:#7890a5;font-size:.68rem">
  Preview history unavailable • {diagnostic} • no pregame state reconstructed after tip-off
</div>
"""

    if phase == "PREGAME":
        label = "🟦 Kyre Sports Preview • Pregame tracking active"
        detail = "Verified context may refresh before tip-off; it becomes immutable once the game goes live."
    elif phase == "LIVE":
        label = "🔒 Kyre Sports Preview • Pregame snapshot frozen • LIVE"
        detail = "The pregame snapshot is locked; live updates cannot rewrite it."
    else:
        label = "🏁 Kyre Sports Preview • Pregame snapshot retained • FINAL"
        detail = "The exact frozen pregame snapshot remains attached to the completed matchup history."

    return f"""
<div data-testid="nba-spread-step8-preview" style="border:1px solid rgba(103,216,255,.24);border-radius:14px;
padding:9px 12px;background:rgba(8,22,36,.86);margin:0 0 8px">
  <div style="font-size:.69rem;font-weight:900;color:#9bdff7">{escape(label)}</div>
  <div style="font-size:.64rem;color:#71869a;margin-top:3px">{escape(detail)}</div>
</div>
"""


def _game_card_with_preview(game: dict) -> str:
    base_html = _ORIGINAL_GAME_CARD(game)
    preview = dict(game.get("step8_preview") or {})
    if not preview:
        return base_html
    return _preview_banner(preview) + base_html


def render_nba_spread_page() -> None:
    st.markdown(
        f'<div data-testid="nba-spread-step8-live-final-active" data-heartbeat="{STEP8_HEARTBEAT}" style="display:none!important"></div>',
        unsafe_allow_html=True,
    )
    original_loader = page_v1._load_verified_schedule
    original_card = page_v1._game_card
    page_v1._load_verified_schedule = _load_schedule_with_preview
    page_v1._game_card = _game_card_with_preview
    try:
        return step7.render_nba_spread_page()
    finally:
        page_v1._load_verified_schedule = original_loader
        page_v1._game_card = original_card


__all__ = [
    "MODEL_VERSION",
    "STEP8_HEARTBEAT",
    "PREVIEW_STATE_KEY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "render_nba_spread_page",
]
