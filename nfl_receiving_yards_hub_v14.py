"""NFL Receiving Yards V14 — semantic player-card redesign.

Additive display-only wrapper over frozen V13. It reuses V10's certified
FAVORABLE / MEDIUM / TOUGH matchup classification and adds a compact Quick Read
header plus semantic presentation colors inspired by the Passing Yards page.
No projection, tier, market, probability, EV, staking, or wager math changes.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v10 as detailed_page
import nfl_receiving_yards_hub_v13 as prior
from nfl_receiving_yards_presentation_v1 import normalize_toughness, semantic_role

MODEL_VERSION = "NFL RECEIVING YARDS V14 • PLAYER CARD REDESIGN • SEMANTIC TOUGHNESS"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v13"
FROZEN_DETAILED_CARD = "nfl_receiving_yards_hub_v10"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_DETAILED_CARD_V10 = detailed_page._detailed_player_card_v10

_STEP14_CSS = r'''
<style>
.krecv14-player{border:1px solid #3a4350;border-radius:17px;background:linear-gradient(145deg,#11151b,#0d1116);padding:9px;margin:8px 0 11px;box-shadow:0 12px 28px rgba(0,0,0,.16)}
.krecv14-player.favorable{border-color:#3f7650}.krecv14-player.medium{border-color:#827038}.krecv14-player.tough{border-color:#844747}
.krecv14-quick{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;border:1px solid #343d4a;border-radius:12px;background:#151a21;padding:9px 10px;margin-bottom:7px}.krecv14-quick-copy{min-width:0}.krecv14-kicker{color:#8e9cb0;font-size:.38rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.krecv14-name{color:#f6f8fb;font-size:.72rem;font-weight:950;margin-top:2px}.krecv14-sub{color:#8f99a9;font-size:.43rem;font-weight:800;margin-top:2px;line-height:1.35}
.krecv14-badges{display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end}.krecv14-tier,.krecv14-model,.krecv14-info,.krecv14-evidence{border-radius:999px;padding:3px 6px;font-size:.34rem;font-weight:950;text-transform:uppercase;white-space:nowrap}.krecv14-tier.favorable{border:1px solid #3c8651;background:#102719;color:#8be2a2}.krecv14-tier.medium{border:1px solid #8a7432;background:#2b230d;color:#e8cf68}.krecv14-tier.tough{border:1px solid #8a4545;background:#2b1111;color:#f09191}.krecv14-model{border:1px solid #6552a6;background:#1c1730;color:#c6b6ff}.krecv14-info{border:1px solid #376d9a;background:#101f2c;color:#8bc5ef}.krecv14-evidence{border:1px solid #505965;background:#171b20;color:#aab2bd}
.krecv14-player > .krecv10-player > .krecv10-ribbon{display:none!important}
.krecv14-player .krecv6-wrap{border-color:#6552a6!important;background:linear-gradient(145deg,#171329,#0d1116)!important}
.krecv14-player .krecv7-wrap{border-color:#376d9a!important;background:#0d1720!important}
.krecv14-player .krecv7-col.support{border-color:#356f48!important;background:#0d1d14!important}.krecv14-player .krecv7-col.concern{border-color:#84633a!important;background:#21180d!important}
.krecv14-deep{display:flex;align-items:center;gap:6px;color:#788391;font-size:.39rem;font-weight:900;letter-spacing:.04em;text-transform:uppercase;margin:6px 2px 3px}.krecv14-deep:before{content:"";width:18px;height:1px;background:#4b5561}
@media(max-width:760px){.krecv14-quick{flex-direction:column}.krecv14-badges{justify-content:flex-start}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _player_card_v14(
    player: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
) -> str:
    """Wrap frozen V10 detail with a semantic quick-read presentation layer."""
    frozen_stack = _ORIGINAL_DETAILED_CARD_V10(player, team, opponent)
    grade = detailed_page._grade_for_team_opponent(team, opponent)
    tier = normalize_toughness(grade.get("tier"))
    role = semantic_role(tier)

    player_name = _safe(player.get("player_name"), _safe(player.get("name"), "Verified receiver"))
    position = _safe(player.get("position"), "REC")
    team_abbr = _safe(team.get("team_abbreviation"), "TEAM").upper()
    opponent_abbr = _safe(opponent.get("team_abbreviation"), "OPP").upper()
    athlete_id = _safe(player.get("official_athlete_id"), "—")

    quick = (
        '<div class="krecv14-quick">'
        '<div class="krecv14-quick-copy">'
        '<div class="krecv14-kicker">Quick Read • semantic player card</div>'
        f'<div class="krecv14-name">{escape(player_name)}</div>'
        f'<div class="krecv14-sub">{escape(position)} • {escape(team_abbr)} vs {escape(opponent_abbr)} • ESPN athlete {escape(athlete_id)}</div>'
        '</div><div class="krecv14-badges">'
        f'<span class="krecv14-tier {escape(role)}">MATCHUP TOUGHNESS • {escape(tier)}</span>'
        '<span class="krecv14-model">MODEL • FROZEN</span>'
        '<span class="krecv14-info">EXACT ESPN ID</span>'
        '<span class="krecv14-evidence">DEEP EVIDENCE BELOW</span>'
        '</div></div>'
    )
    return (
        f'<section class="krecv14-player {escape(role)}" data-toughness-tier="{escape(tier)}">'
        f'{quick}<div class="krecv14-deep">DEEP EVIDENCE</div>{frozen_stack}</section>'
    )


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP14_CSS, unsafe_allow_html=True)
    original_card = detailed_page._detailed_player_card_v10
    detailed_page._detailed_player_card_v10 = _player_card_v14
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        detailed_page._detailed_player_card_v10 = original_card


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V14 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_DETAILED_CARD",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_player_card_v14",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
