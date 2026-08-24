"""WNBA Rebounds + Assists hot-reload-safe compatibility boundary.

The application imports this historical V1 filename. Forward that exact boundary
to V4, which preserves the verified Step-1 slate/player identity, Step-2 exact
SportsGameOdds combined Rebounds + Assists market verification and Step-3
player form/history, then adds Step 4 descriptive R+A opportunity + matchup
context.

No existing WNBA Rebounds, Assists, PRA, Points, Spread, Moneyline, Game Total,
Daily Picks, MLB or NFL model code is changed by this shim.
"""
from __future__ import annotations

import wnba_ra_hub_v4 as presentation

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V4 • VIA HOT-RELOAD-SAFE V1 BOUNDARY"


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return presentation.render_wnba_ra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(presentation, name)


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
