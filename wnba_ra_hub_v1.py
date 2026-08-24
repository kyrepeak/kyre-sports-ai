"""WNBA Rebounds + Assists hot-reload-safe compatibility boundary.

The application imports this historical V1 filename. Forward that exact boundary
to V5, which preserves verified Steps 1-4 and adds Step 5: separate REB/AST
projection plus an on-demand correlated 5,000,000-draw R+A Monte Carlo.

No existing WNBA Rebounds, Assists, PRA, Points, Spread, Moneyline, Game Total,
Daily Picks, MLB or NFL model code is changed by this shim.
"""
from __future__ import annotations

import wnba_ra_hub_v5 as presentation

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V5 • VIA HOT-RELOAD-SAFE V1 BOUNDARY"


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return presentation.render_wnba_ra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(presentation, name)


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
