"""NFL V3.5 routing wrapper — Passing Yards verified Kyre API + visual identity.

Preserves NFL V3.4 for every other NFL market and advances only Passing Yards
to V27. V27 fixes the nested V26/V25 Step 4 wrapper route so live Pressure V5
actually reaches the active page; V26 contains the live ESPN pressure source
recovery, V25 keeps the bounded exact-ID early-season gate over V24, V24 adds
exact-ID team/opponent matchup context over V23, V23 is CSS-only market-card
header polish over V22, V22 is the exact-ID QB headshot overlay over V21, and
V21 is the exact-ID team-logo overlay over V20. V20's Kyre Sports API Step 10
bridge, frozen projection/market math, 0.0% sportsbook projection influence,
stake sizing OFF, and fail-closed protections remain intact.
"""
from __future__ import annotations

import nfl_hub_v34 as base

MODEL_VERSION = "NFL V3.5 • PASSING YARDS V27 STEP 4 NESTED ROUTE FIX • V26/V25/V24/V23/V22/V21/V20 FROZEN • V3.4 PRESERVED"
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


def _render_certified_v24_contract():
    """Keep the certified V24 presentation route explicitly importable."""
    from nfl_passing_yards_hub_v24 import render_nfl_passing_yards_hub as render_v24
    return render_v24()


def _render_certified_v25_contract():
    """Keep the certified V25 Step 4 bounded-gate route explicitly importable."""
    from nfl_passing_yards_hub_v25 import render_nfl_passing_yards_hub as render_v25
    return render_v25()


def _render_certified_v26_contract():
    """Keep the V26 live-source-recovery route explicitly importable."""
    from nfl_passing_yards_hub_v26 import render_nfl_passing_yards_hub as render_v26
    return render_v26()


def render_nfl_hub(market: str = "Slate"):
    market = str(market or "Slate")
    if market == "Passing Yards":
        # V27 fixes only the nested Step 4 wrapper route; all prior contracts stay frozen.
        from nfl_passing_yards_hub_v27 import render_nfl_passing_yards_hub as render_v27
        return render_v27()
    return base.render_nfl_hub(market)


__all__ = ["MODEL_VERSION", "NFL_MARKETS", "load_nfl_slate", "ET", "render_nfl_hub"]
