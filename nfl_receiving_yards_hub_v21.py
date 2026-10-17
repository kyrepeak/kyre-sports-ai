"""NFL Receiving Yards V21 — verified visual identity for Key Receiving Options.

Additive display-only wrapper over frozen V20. It preserves the full V20
multi-source exact-ID data, projections, market isolation and inherited
player-vs-defense history stack while adding a verified player headshot and
team logo to each compact identity proof card.
"""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v2 as base_page
import nfl_receiving_yards_hub_v20 as prior

MODEL_VERSION = "NFL RECEIVING YARDS V21 • VERIFIED VISUAL IDENTITY"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v20"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MULTI_SOURCE_REQUIRED = True
DISPLAY_ONLY = True

_CSS = r'''
<style>
.krecv21-id{display:grid;grid-template-columns:42px 1fr 30px;align-items:center;gap:7px;border:1px solid #294a37;border-radius:10px;background:#0a1510;padding:6px 7px;min-width:190px;line-height:1.22}
.krecv21-face{width:40px;height:40px;border-radius:50%;object-fit:cover;border:1px solid #355d45;background:#111923}
.krecv21-logo{width:28px;height:28px;object-fit:contain;justify-self:end}
.krecv21-copy b{display:block;color:#eef7f1;font-size:.59rem}.krecv21-copy span{display:block;color:#7f9988;font-size:.45rem;margin-top:2px}.krecv21-copy em{display:block;font-style:normal;color:#80dca2;font-size:.43rem;font-weight:800;margin-top:2px}
@media(max-width:760px){.krecv21-id{min-width:175px;flex:1 1 46%;grid-template-columns:38px 1fr 26px;padding:5px 6px}.krecv21-face{width:36px;height:36px}.krecv21-logo{width:24px;height:24px}}
</style>
'''


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _https_url(value: Any) -> str:
    text = _safe(value)
    return text if text.startswith("https://") else ""


def _team_id_cards_html_v21(team: dict[str, Any]) -> str:
    cards: list[str] = []
    abbr_raw = _safe(team.get("team_abbreviation"), "NFL").upper()
    abbr = escape(abbr_raw)
    team_logo = _https_url(base_page._team_logo_url(abbr_raw))
    for player in team.get("players") or []:
        if not isinstance(player, dict):
            continue
        athlete_id = _safe(player.get("official_athlete_id"))
        if not athlete_id.isdigit():
            continue
        raw_name = _safe(player.get("player_name"), "Verified receiver")
        name = escape(raw_name)
        pos = escape(_safe(player.get("position"), "REC").upper())
        jersey = _safe(player.get("jersey_number"))
        jersey_text = f" • #{escape(jersey)}" if jersey else ""
        headshot = _https_url(player.get("headshot_url")) or _https_url(base_page._headshot_url(athlete_id))
        face_html = (
            f'<img class="krecv21-face" src="{escape(headshot, quote=True)}" alt="{name} headshot" loading="lazy" />'
            if headshot else '<span class="krecv21-face" aria-hidden="true"></span>'
        )
        logo_html = (
            f'<img class="krecv21-logo" src="{escape(team_logo, quote=True)}" alt="{abbr} logo" loading="lazy" />'
            if team_logo else ''
        )
        cards.append(
            '<div class="krecv21-id">'
            f'{face_html}'
            '<div class="krecv21-copy">'
            f'<b>{name} • {pos}{jersey_text}</b>'
            f'<span>ESPN ID {escape(athlete_id)}</span>'
            '<em>VERIFIED • ESPN + NFLVERSE</em>'
            '</div>'
            f'{logo_html}'
            '</div>'
        )
    return '<div class="krecv20-proofrow">' + ''.join(cards) + '</div>' if cards else ''


def render_nfl_receiving_yards_hub() -> None:
    st.html(_CSS)
    original = prior._team_id_cards_html_v20
    prior._team_id_cards_html_v20 = _team_id_cards_html_v21
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        prior._team_id_cards_html_v20 = original


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V21 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "DISPLAY_ONLY", "FROZEN_PRIOR", "MODEL_VERSION", "MULTI_SOURCE_REQUIRED",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "_team_id_cards_html_v21",
    "render_nfl_hub", "render_nfl_receiving_yards_hub",
]
