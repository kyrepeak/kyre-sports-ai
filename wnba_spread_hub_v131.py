"""WNBA Spread V1.3.1 — Step-4 integrity wrapper.

Keeps the V1.3 page/UI and installs the spread-specific SportsGameOdds adapter
that measures side-specific spread freshness and requires exact provider
away/home orientation. No model, probability or Monte Carlo math is changed.
"""
from __future__ import annotations

import wnba_spread_hub_v13 as base
import wnba_spread_market_v131 as market

MODEL_VERSION = "WNBA SPREAD V1.3.1 • EXACT SPREAD + SIDE-SPECIFIC FRESHNESS"

# V1.3's Step-4 renderer resolves this global at call time, so replacing it here
# upgrades only the sportsbook verification contract while preserving the entire
# verified slate/context/availability UI and lock sequence.
base._spread_market_snapshot = market.spread_market_snapshot


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return base.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
