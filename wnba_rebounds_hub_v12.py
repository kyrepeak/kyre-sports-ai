"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.1. Steps 1-11 remain preserved through the verified V2.0
chain. V2.1 adds Step 12 player-vs-opponent rebound history using immutable ESPN
PLAYER_ID joins and completed current-team matchup-series box scores from the
current and previous season. Verified no-sample players remain explicitly labeled;
no history is guessed. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v21 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.1 • STEP 12 PLAYER VS OPPONENT REBOUND HISTORY",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
