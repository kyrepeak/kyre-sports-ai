"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.8. Steps 1-18 remain preserved through the verified V2.7
chain. V2.8 adds Step 19 model-vs-market edge and exact posted-price expected
value for both Over and Under at each same-book/same-line rebound market, with
explicit push handling and ±5% sensitivity robustness. The player projection
and distribution remain market-independent. Ranking/staking/final-card logic is
deferred to Step 20. Cold-start reliability and subscription-safe
SportsGameOdds behavior remain intact. Frozen Points/PRA/MLB modules remain
untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v28 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.8 • STEP 19 MODEL-VS-MARKET EDGE + EXPECTED VALUE",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
