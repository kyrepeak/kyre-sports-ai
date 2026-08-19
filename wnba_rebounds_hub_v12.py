"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.8. Steps 1-8 retain the verified V1.7/V1.7.1 model and
persistent fast-start behavior. V1.8 adds only Step 9 position matchup context
(Guard / Wing / Big). Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v18 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.8 • STEP 9 POSITION MATCHUP — GUARD/WING/BIG",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
