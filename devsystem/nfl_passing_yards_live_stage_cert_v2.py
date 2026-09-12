"""NFL Passing Yards live-stage cert V2 — UTC-safe Step 3 bridge.

Wraps V1 certification unchanged except that Step 3 uses the production
pass-defense V3 wrapper, which normalizes verified ESPN schedule timestamps to
UTC before cutoff comparisons. No sportsbook input or projection math changes.
"""
from __future__ import annotations

import argparse

import nfl_passing_yards_defense_v3 as defense_v3
from devsystem import nfl_passing_yards_live_stage_cert_v1 as prior


def _run(func) -> None:
    original = prior.defense_v2.build_pass_defense_profile
    prior.defense_v2.build_pass_defense_profile = defense_v3.build_pass_defense_profile
    try:
        func()
    finally:
        prior.defense_v2.build_pass_defense_profile = original


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("profile", "matchup", "recent"), required=True)
    args = parser.parse_args()
    if args.stage == "profile":
        _run(prior.certify_profile)
    elif args.stage == "matchup":
        _run(prior.certify_matchup_inputs)
    else:
        _run(prior.certify_recent_variance)


if __name__ == "__main__":
    main()
