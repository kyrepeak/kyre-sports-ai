"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.2.1. Steps 1-12 remain preserved through the verified V2.1
chain. V2.2.1 keeps V2.2 exact SportsGameOdds WNBA rebound-line ingestion,
bookmaker separation and same-book/same-line O/U pairing, while making the
provider request subscription-safe by omitting explicit bookmakerIDs that may
be unavailable on the connected tier and filtering accessible target books
locally. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v221 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.2.1 • STEP 13 SUBSCRIPTION-SAFE SPORTSGAMEODDS",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
