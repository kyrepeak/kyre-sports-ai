"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.5. Steps 1-15 remain preserved through the verified V2.4.1
chain. V2.5 adds Step 16 uncertainty + rebound distribution calibration from the
market-independent Step-15 mean plus direct verified Step-5 multi-window rebound
rate anchors. Sportsbook lines/no-vig remain fully isolated; Monte Carlo remains
off until Step 17. Cold-start reliability and subscription-safe SportsGameOdds
behavior remain intact. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v25 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.5 • STEP 16 UNCERTAINTY + REBOUND DISTRIBUTION CALIBRATION",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
