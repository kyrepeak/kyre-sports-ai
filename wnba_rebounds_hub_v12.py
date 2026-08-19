"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.4. Steps 1-14 remain preserved through the verified V2.3
chain. V2.4 adds Step 15 market-independent rebound projection synthesis using
only verified basketball inputs, with explicit double-count guards and bounded
context adjustments. Sportsbook lines, prices and no-vig probabilities remain
fully isolated from the player projection. Cold-start reliability and
subscription-safe SportsGameOdds behavior remain intact.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v24 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.4 • STEP 15 MARKET-INDEPENDENT PROJECTION SYNTHESIS",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
