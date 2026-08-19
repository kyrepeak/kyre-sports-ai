"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.3. Steps 1-13 remain preserved through the verified
V2.2.2 chain. V2.3 adds Step 14 same-book/same-line no-vig normalization using
only exact SportsGameOdds Over+Under pairs, while keeping market probabilities
fully isolated from the player rebound projection. Cold-start reliability and
subscription-safe SportsGameOdds behavior remain intact.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v23 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.3 • STEP 14 SAME-BOOK NO-VIG",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
