"""NFL Passing Yards full live cert V2 — production UTC-safe Step 3 path.

Runs the existing V1 live certification while swapping only the Step 3 builder
to pass-defense V3. This mirrors production V17 after the timezone hotfix and
keeps the certified Step 7 math, exact ESPN identities, sportsbook influence
0.0%, and fail-closed behavior unchanged.
"""
from __future__ import annotations

import nfl_passing_yards_defense_v3 as defense_v3
from devsystem import nfl_passing_yards_live_cert_v1 as prior


def run_live_certification() -> dict:
    original = prior.defense_v2.build_pass_defense_profile
    prior.defense_v2.build_pass_defense_profile = defense_v3.build_pass_defense_profile
    try:
        return prior.run_live_certification()
    finally:
        prior.defense_v2.build_pass_defense_profile = original


if __name__ == "__main__":
    run_live_certification()
