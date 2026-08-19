"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.9. Steps 1-19 remain preserved through the verified V2.8
chain. V2.9 adds Step 20 risk-adjusted qualification, transparent ranking and a
final card using only verified exact-book/exact-line Step-19 sides. Qualification
requires robust positive sensitivity edge, minimum no-vig edge and posted-price
EV; duplicate books/lines collapse to one best exact quote per player and five
selections are never forced. Projection/distribution math remains market-
independent. No staking/bet sizing is added. Cold-start reliability and
subscription-safe SportsGameOdds behavior remain intact. Frozen Points/PRA/MLB
modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v29 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.9 • STEP 20 RISK-ADJUSTED QUALIFICATION + FINAL CARD",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
