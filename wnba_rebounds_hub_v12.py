"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.2. Steps 1-12 remain preserved through the verified V2.1
chain. V2.2 adds Step 13 exact SportsGameOdds WNBA rebound-line ingestion with
bookmaker separation, exact same-book/same-line O/U pairing, verified NO MARKET
states, and no consensus substitution. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v22 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.2 • STEP 13 EXACT SPORTSGAMEODDS REBOUND LINES",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
