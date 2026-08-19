"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.4.1. Steps 1-14 remain preserved through the verified V2.3
chain. V2.4.1 repairs Step 15 by reconciling its atomic basketball inputs
straight from the verified Step-9 and Step-10 player frames instead of assuming
Step 11/12 carried every upstream diagnostic column forward. V2.4 projection
math, weights, caps and sportsbook isolation remain unchanged. Cold-start
reliability and subscription-safe SportsGameOdds behavior remain intact.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v241 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.4.1 • STEP 15 SOURCE RECONCILIATION REPAIR",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
