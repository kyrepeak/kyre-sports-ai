"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.7. Steps 1-17 remain preserved through the verified V2.6
chain. V2.7 adds Step 18 line-specific Over/Under/Push probability and fair odds
by evaluating the market-independent Step-16 PMF at each exact verified Step-14
same-book/same-line threshold. Integer-line pushes are explicit and fair odds
condition on a non-push result. Sportsbook/no-vig data never changes the player
projection or distribution. EV/ranking remains deferred to Step 19.
Cold-start reliability and subscription-safe SportsGameOdds behavior remain
intact. Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v27 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.7 • STEP 18 LINE-SPECIFIC O/U PROBABILITY + FAIR ODDS",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
