"""NFL V3.5 routing wrapper — Passing Yards verified Kyre API + visual identity.

Preserves NFL V3.4 for every other NFL market and advances only Passing Yards
to V24. V24 adds exact-ID team/opponent matchup context over certified V23;
V23 is CSS-only market-card header polish over V22; V22 is the exact-ID QB
headshot overlay over V21; V21 is the exact-ID team-logo overlay over V20.
V20's Kyre Sports API Step 10 bridge, frozen projection math, market evaluator,
0.0% sportsbook projection influence, and fail-closed protections remain intact.
"""
from __future__ import annotations

import nfl_hub_v34 as base

MODEL_VERSION = "NFL V3.5 • PASSING YARDS V24 MATCHUP CONTEXT + V23 CARD POLISH + V22 HEADSHOTS + V21 TEAM LOGOS • V20 FROZEN • V3.4 PRESERVED"
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
    """Keep the certified V23 presentation route explicitly importable."""
    from nfl_passing_yards_hub_v23 import render_nfl_passing_yards_hub as render_v23
    return render_v23()


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        # V24 wraps V23 and changes presentation only; all prior contracts stay frozen.
        from nfl_passing_yards_hub_v24 import render_nfl_passing_yards_hub as render_v24
        return render_v24()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
