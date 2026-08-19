"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.0. Steps 1-10 remain preserved through the verified V1.9
chain. V2.0 adds Step 11 lineup effects / rebound competition using only the
verified active rotation, projected minutes and Step-6 rebound-capture baseline.
It adds zero normal-load network requests and does not invent exact five-player
lineup overlap. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v20 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.0 • STEP 11 LINEUP EFFECTS / REBOUND COMPETITION",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
