"""NFL Passing Yards V62 — live-matchup timezone runtime hotfix.

Additive runtime-only wrapper over frozen V61. The verified 2026-09-24 public
matchup exposed a pandas tz-aware vs tz-naive comparison inside the legacy V1
pass-defense recent-form path. The repository already contains the certified
UTC-normalized event parser in pass-defense V3; V62 installs only that parser
for the duration of the frozen V61 render and restores the legacy function
immediately afterward.

No projection, probability, market, sportsbook, grading, identity, picker,
detail, or presentation behavior changes.
"""
from __future__ import annotations

import nfl_passing_yards_defense_v1 as defense_base
import nfl_passing_yards_defense_v3 as defense_hardened
import nfl_passing_yards_hub_v61 as prior

MODEL_VERSION = "NFL PASSING YARDS V62 • LIVE MATCHUP UTC RUNTIME HOTFIX"
FROZEN_PRIOR = "nfl_passing_yards_hub_v61"
RUNTIME_HOTFIX = True
UTC_EVENT_PARSER = "nfl_passing_yards_defense_v3._completed_event_rows_utc"
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_PRESENTATION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


def _install_utc_safe_event_parser():
    original = defense_base._completed_event_rows
    defense_base._completed_event_rows = defense_hardened._completed_event_rows_utc
    return original


def render_nfl_passing_yards_hub() -> None:
    original = _install_utc_safe_event_parser()
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        defense_base._completed_event_rows = original


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V62 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PRESENTATION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "RUNTIME_HOTFIX",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "UTC_EVENT_PARSER",
    "_install_utc_safe_event_parser",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
