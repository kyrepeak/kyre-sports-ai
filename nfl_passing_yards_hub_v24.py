"""NFL Passing Yards V24 — exact-ID matchup context on Step 10 cards.

Presentation-only wrapper over certified V23. V24 adds a compact team/opponent
context line beneath each quarterback name using only the same already-verified
ESPN matchup identity used by the frozen V20/V21/V22 chain.

Identity rules remain strict:
- exact verified ESPN team context for both sides;
- exact verified ESPN QB athlete ID for the card's side;
- certified away/home card order only;
- away card renders TEAM • @ OPPONENT; home card renders TEAM • vs OPPONENT;
- no fuzzy matching, no player-name identity authority, no synthetic IDs;
- missing/invalid matchup context fails soft and preserves the V23 card.

No projection, probability, fair-odds, no-vig, EV, grading, confidence, market,
API, or sportsbook logic is changed. Sportsbook projection influence remains
0.0%. Stake sizing remains OFF.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v11 as step10_ui
import nfl_passing_yards_hub_v23 as prior
import nfl_passing_yards_hub_v8 as step7_ui

MODEL_VERSION = "NFL PASSING YARDS V24 • EXACT ESPN MATCHUP CONTEXT • V23/V22/V21/V20 FROZEN"
FROZEN_PRIOR = "nfl_passing_yards_hub_v23"

_MATCHUP_CSS = r"""
<style>
.kpy24-matchup{
  margin-top:3px;
  font-size:.56rem;
  line-height:1.2;
  font-weight:850;
  letter-spacing:.035em;
  color:#9eb6c8;
  text-transform:uppercase;
}
@media(max-width:820px){
  .kpy24-matchup{font-size:.52rem;margin-top:2px}
}
</style>
"""

_TEAM_ABBR_RE = re.compile(r"^[A-Z]{2,4}$")
_SUB_MARKER = '<div class="kpy10-sub">'


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _verified_side(ctx: dict) -> bool:
    qb = (ctx or {}).get("qb1") or {}
    team_id = _safe((ctx or {}).get("team_id"))
    athlete_id = _safe(qb.get("athlete_id"))
    abbr = _safe((ctx or {}).get("abbr")).upper()
    return bool(
        (ctx or {}).get("identity_verified")
        and team_id.isdigit()
        and athlete_id.isdigit()
        and _TEAM_ABBR_RE.fullmatch(abbr)
    )


def _exact_matchup_visuals(identity_result: dict) -> list[dict]:
    """Return away/home display context only when both exact ESPN sides verify."""
    identity_result = identity_result or {}
    away = identity_result.get("away") or {}
    home = identity_result.get("home") or {}
    if not (_verified_side(away) and _verified_side(home)):
        return [{"ready": False, "side": "away"}, {"ready": False, "side": "home"}]

    away_abbr = _safe(away.get("abbr")).upper()
    home_abbr = _safe(home.get("abbr")).upper()
    return [
        {
            "ready": True,
            "side": "away",
            "team_abbr": away_abbr,
            "opponent_abbr": home_abbr,
            "venue_token": "@",
        },
        {
            "ready": True,
            "side": "home",
            "team_abbr": home_abbr,
            "opponent_abbr": away_abbr,
            "venue_token": "vs",
        },
    ]


def _matchup_text(visual: dict) -> str:
    if not (visual or {}).get("ready"):
        return ""
    team = _safe((visual or {}).get("team_abbr")).upper()
    opponent = _safe((visual or {}).get("opponent_abbr")).upper()
    venue = _safe((visual or {}).get("venue_token"))
    if _TEAM_ABBR_RE.fullmatch(team) is None or _TEAM_ABBR_RE.fullmatch(opponent) is None:
        return ""
    if venue not in {"@", "vs"}:
        return ""
    return f"{team} • {venue} {opponent}"


def _inject_matchup_context(card_html: str, visual: dict) -> str:
    """Add a small matchup line without changing frozen market-card content."""
    context = _matchup_text(visual)
    if not context or _SUB_MARKER not in card_html:
        return card_html
    matchup = f'<div class="kpy24-matchup">{escape(context)}</div>'
    return card_html.replace(_SUB_MARKER, matchup + _SUB_MARKER, 1)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_MATCHUP_CSS, unsafe_allow_html=True)

    visuals: list[dict] = []
    card_index = 0
    original_identity_builder = step7_ui.identity.resolve_matchup_identity
    original_market_card = step10_ui._market_card

    def capture_identity(*args, **kwargs):
        result = original_identity_builder(*args, **kwargs)
        visuals[:] = _exact_matchup_visuals(result or {})
        return result

    def market_card_with_matchup(row: dict) -> str:
        nonlocal card_index
        html = original_market_card(row)
        idx = card_index
        card_index += 1
        visual = visuals[idx] if 0 <= idx < len(visuals) else {}
        return _inject_matchup_context(html, visual)

    # V23 -> V22 -> V21 nest their certified visual wrappers. This outer V24
    # capture reuses the same exact identity and card order; it adds display text only.
    step7_ui.identity.resolve_matchup_identity = capture_identity
    step10_ui._market_card = market_card_with_matchup
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.identity.resolve_matchup_identity = original_identity_builder
        step10_ui._market_card = original_market_card

    st.caption(
        f"{MODEL_VERSION} • exact-ID team/opponent context only • frozen market/model logic preserved • sportsbook projection influence = 0.0% • stake sizing OFF"
    )


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_exact_matchup_visuals",
    "_inject_matchup_context",
    "_matchup_text",
    "render_nfl_passing_yards_hub",
]
