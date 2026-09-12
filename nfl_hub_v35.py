"""NFL V3.5 routing wrapper — Passing Yards verified Kyre API + visual identity.

Preserves NFL V3.4 for every other NFL market and advances only Passing Yards
to V28. V28 upgrades Step 5 with exact-ID current weapon usage from verified
ESPN box scores while preserving the current injury/depth authority. V27 keeps
the certified nested Step 4 Pressure V5 route; V24 adds exact-ID matchup context,
V23 card-header polish, V22 exact-ID QB headshots, V21 exact-ID team logos, and
V20 the Kyre Sports API Step 10 bridge. Frozen projection/market math,
0.0% sportsbook projection influence, stake sizing OFF, and fail-closed
protections remain intact.
"""
from __future__ import annotations

import nfl_hub_v34 as base

MODEL_VERSION = "NFL V3.5 • PASSING YARDS V28 STEP 5 EXACT-ID WEAPONS + INJURIES • V27/V26/V25/V24/V23/V22/V21/V20 FROZEN • V3.4 PRESERVED"
NFL_MARKETS = base.NFL_MARKETS
load_nfl_slate = base.load_nfl_slate
ET = base.ET


def _render_certified_v22_contract():
    """Keep the certified V20/V21/V22 route chain explicitly importable."""
    from nfl_passing_yards_hub_v20 import render_nfl_passing_yards_hub
    from nfl_passing_yards_hub_v21 import render_nfl_passing_yards_hub as render_v21
    from nfl_passing_yards_hub_v22 import render_nfl_passing_yards_hub as render_v22
    _ = (render_nfl_passing_yards_hub, render_v21)
    return render_v22()


def _render_certified_v23_contract():
    from nfl_passing_yards_hub_v23 import render_nfl_passing_yards_hub as render_v23
    return render_v23()


def _render_certified_v24_contract():
    from nfl_passing_yards_hub_v24 import render_nfl_passing_yards_hub as render_v24
    return render_v24()


def _render_certified_v25_contract():
    from nfl_passing_yards_hub_v25 import render_nfl_passing_yards_hub as render_v25
    return render_v25()


def _render_certified_v26_contract():
    from nfl_passing_yards_hub_v26 import render_nfl_passing_yards_hub as render_v26
    return render_v26()


def _render_certified_v27_contract():
    """Keep the certified Step 4 V27 route explicitly importable."""
    from nfl_passing_yards_hub_v27 import render_nfl_passing_yards_hub as render_v27
    return render_v27()


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        # V28 advances only Step 5; V27 and all prior contracts remain frozen.
        from nfl_passing_yards_hub_v28 import render_nfl_passing_yards_hub as render_v28
        return render_v28()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
