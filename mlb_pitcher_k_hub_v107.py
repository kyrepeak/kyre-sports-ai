"""MLB Pitcher Strikeouts O/U V1.0.7 — team logos on ranked pitcher cards.

Presentation-only upgrade. Projection math, workload model, sportsbook parsing,
line grading, simulations and rankings remain V1.0.6 unchanged.
"""
from __future__ import annotations

import mlb_pitcher_k_hub_v106 as v106
import mlb_pitcher_k_hub_v101 as v101

engine = v106.engine
MODEL_VERSION = "Pitcher K V1.0.7"

TEAM_IDS = {
    "Arizona Diamondbacks":109,"Atlanta Braves":144,"Baltimore Orioles":110,
    "Boston Red Sox":111,"Chicago Cubs":112,"Chicago White Sox":145,
    "Cincinnati Reds":113,"Cleveland Guardians":114,"Colorado Rockies":115,
    "Detroit Tigers":116,"Houston Astros":117,"Kansas City Royals":118,
    "Los Angeles Angels":108,"Los Angeles Dodgers":119,"Miami Marlins":146,
    "Milwaukee Brewers":158,"Minnesota Twins":142,"New York Mets":121,
    "New York Yankees":147,"Athletics":133,"Oakland Athletics":133,
    "Philadelphia Phillies":143,"Pittsburgh Pirates":134,"San Diego Padres":135,
    "San Francisco Giants":137,"Seattle Mariners":136,"St. Louis Cardinals":138,
    "Tampa Bay Rays":139,"Texas Rangers":140,"Toronto Blue Jays":141,
    "Washington Nationals":120,
}


def _logo_url(team):
    tid = TEAM_IDS.get(str(team or "").strip())
    return f"https://www.mlbstatic.com/team-logos/{tid}.svg" if tid else ""


# V1.0.1 executes the original V1.0 source into its own module globals, so the
# live card renderer is v101._card (not engine._card).
_base_card = v101._card


def _card_with_logo(r, rank):
    html = _base_card(r, rank)
    team = r.get("team")
    logo = _logo_url(team)
    if not logo:
        return html

    name = v101._e(r.get("player_name"))
    team_esc = v101._e(team)
    old = f'<div class="pk-name">{name}</div>'
    new = (
        '<div class="pk-player-row" style="display:flex;align-items:center;gap:10px;'
        'margin-top:8px;margin-bottom:3px;min-height:33px">'
        f'<img src="{logo}" alt="{team_esc} logo" '
        'style="width:33px;height:33px;object-fit:contain;object-position:center;'
        'flex:0 0 33px;display:block">'
        f'<div class="pk-name" style="margin:0;display:flex;align-items:center;'
        f'min-height:33px;line-height:1.1">{name}</div>'
        '</div>'
    )
    return html.replace(old, new, 1)


# Every later compatibility layer ultimately calls v101.render_pitcher_k_hub,
# whose globals resolve _card at render time. Patch that exact symbol only.
v101._card = _card_with_logo


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    return v106.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
