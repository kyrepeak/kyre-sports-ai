"""WNBA Rebounds route wrapper — current isolated production build.

Route directly to V3.1. The verified Steps 1–20 model/market chain and V3.0
Production Readiness Guard remain unchanged. V3.1 adds only a responsive visual
Top-5 production-card section using the already-verified final-card state:
player faces, official WNBA team/opponent logos, exact sportsbook line/side/odds,
market-independent projection context, Monte Carlo range, model probability,
edge, EV, fair odds, projected minutes, H2H context, confidence, quote freshness
and game/tip status.

No Step 1–20 projection, probability, EV, qualification or ranking math changes.
No production-readiness rules change. Cold-start reliability and subscription-safe
SportsGameOdds behavior remain intact. Frozen Points/PRA/MLB modules remain
untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v31 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V3.1 • VISUAL TOP-5 PRODUCTION CARDS • V3.0 MODEL PRESERVED",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
