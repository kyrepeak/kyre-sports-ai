"""WNBA Rebounds route wrapper — current isolated build.

Route directly to V2.6. Steps 1-16 remain preserved through the verified V2.5
chain. V2.6 adds Step 17 Monte Carlo simulation, convergence diagnostics and
bounded ±5% sensitivity testing from the market-independent Step-16 rebound PMF.
The production standard is 5,000,000 simulations per player in 20 deterministic
batches. Sportsbook lines/no-vig remain excluded from the simulation itself;
line-specific Over/Under probability is deferred to Step 18. Cold-start
reliability and subscription-safe SportsGameOdds behavior remain intact.
Frozen Points/PRA/MLB modules remain untouched.
"""
from __future__ import annotations

import wnba_rebounds_hub_v26 as _impl

MODEL_VERSION = getattr(
    _impl,
    "MODEL_VERSION",
    "WNBA REBOUNDS V2.6 • STEP 17 MONTE CARLO + CONVERGENCE / SENSITIVITY",
)


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
