"""NFL Passing Yards full live cert V2 — production UTC-safe Step 3 path.

Runs the existing V1 live certification while swapping only the Step 3 builder
to pass-defense V3. This mirrors production V17 after the timezone hotfix and
keeps the certified Step 7 math, exact ESPN identities, sportsbook influence
0.0%, and fail-closed behavior unchanged.

The V1 cert's defense module reference is proxied rather than mutating the
shared V2 module function object. V3 can therefore delegate internally to the
real V2 implementation without recursively calling itself.
"""
from __future__ import annotations

import nfl_passing_yards_defense_v3 as defense_v3
from devsystem import nfl_passing_yards_live_cert_v1 as prior


class _DefenseProxy:
    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name):
        if name == "build_pass_defense_profile":
            return defense_v3.build_pass_defense_profile
        return getattr(self._wrapped, name)


def run_live_certification() -> dict:
    original_module = prior.defense_v2
    prior.defense_v2 = _DefenseProxy(original_module)
    try:
        return prior.run_live_certification()
    finally:
        prior.defense_v2 = original_module


if __name__ == "__main__":
    run_live_certification()
