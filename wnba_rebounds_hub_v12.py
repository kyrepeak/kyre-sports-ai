"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V1.9. Steps 1-9 remain preserved through the verified V1.8.4
chain. V1.9 adds Step 10 pace + expected shot volume using the same six-hour
ESPN team-stat payload already shared by Steps 7-8, with direct pace preferred
and a verified FGA + 0.44*FTA - OREB + TOV possession fallback when needed.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v19 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V1.9 • STEP 10 PACE + EXPECTED SHOT VOLUME",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
