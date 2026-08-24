"""WNBA Rebounds + Assists hot-reload-safe compatibility boundary.

The application imports this historical V1 filename. Forward that exact boundary
to V6, which preserves verified Steps 1-4, the V5 projection + correlated
5,000,000-draw Monte Carlo and the V5.1 mobile run-control repair, then adds
Step 6 post-simulation qualification + strongest daily Top-5 selection.

No existing WNBA Rebounds, Assists, PRA, Points, Spread, Moneyline, Game Total,
Daily Picks, MLB or NFL model code is changed by this shim.
"""
from __future__ import annotations

import wnba_ra_hub_v6 as presentation

MODEL_VERSION = "WNBA REBOUNDS + ASSISTS V6 • VIA HOT-RELOAD-SAFE V1 BOUNDARY"


def render_wnba_ra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return presentation.render_wnba_ra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(presentation, name)


__all__ = ["MODEL_VERSION", "render_wnba_ra_hub"]
