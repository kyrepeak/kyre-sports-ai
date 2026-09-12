"""NFL Passing Yards Step 2 — descriptive quarterback passing profile.

This compatibility surface preserves the certified Step 2 contract while the
implementation lives in ``nfl_passing_yards_profile_v1_impl``. Step 2 remains
descriptive evidence and does not itself create a passing-yards projection.

The early-season bridge is verified-source only: current regular-season data
always wins, and the immediately prior regular season is used only when the new
regular season has no usable sample. No sportsbook input is accepted here.
"""
from __future__ import annotations

import nfl_passing_yards_profile_v1_impl as _impl

# Preserve the full public/private surface used by frozen tests and downstream
# modules without duplicating the implementation body.
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

_IMPL_BUILD_QB_PROFILE = _impl.build_qb_profile


def build_qb_profile(athlete_id: str, qb_name: str, year: int, season_type: int = 2) -> dict:
    """Delegate while honoring monkeypatched loader hooks on this module."""
    original_season_loader = _impl._season_stats_payload
    original_gamelog_loader = _impl._gamelog_payload
    _impl._season_stats_payload = globals()["_season_stats_payload"]
    _impl._gamelog_payload = globals()["_gamelog_payload"]
    try:
        return _IMPL_BUILD_QB_PROFILE(athlete_id, qb_name, year, season_type)
    finally:
        _impl._season_stats_payload = original_season_loader
        _impl._gamelog_payload = original_gamelog_loader


__all__ = [
    "MODEL_VERSION",
    "build_qb_profile",
    "parse_recent_passing",
    "parse_season_passing",
]
