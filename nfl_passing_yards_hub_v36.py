"""NFL Passing Yards V36 — compact dashboard presentation shell.

Additive UI-only wrapper over certified V35. This layer introduces the stable
presentation hooks used by the Compact Dashboard First redesign while leaving
all certified Passing Yards data owners, projection math, probability math,
market logic, ESPN identity contracts, and transport behavior untouched.

Frozen:
- V35 production transport + caption cleanup;
- V34 player-first composition until individual presentation sections are
  deliberately migrated into this V36 display layer;
- V33/V28 analytical values and fail-closed rules;
- exact ESPN team-logo / QB-headshot identity contracts;
- sportsbook projection influence = 0.0%;
- stake sizing OFF.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v35 as prior


MODEL_VERSION = "NFL PASSING YARDS V36 • COMPACT DASHBOARD SHELL"
FROZEN_PRIOR = "nfl_passing_yards_hub_v35"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
COMPACT_DASHBOARD_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


_COMPACT_DASHBOARD_CSS = """
<style>
/* Stable V36 hooks. Later presentation steps fill these surfaces without
   changing any certified Passing Yards calculation owner. */
.monster-pass-dashboard {
    width: 100%;
    max-width: 1180px;
    margin: 0 auto;
}
.monster-matchup-header {
    width: 100%;
}
.monster-qb-hero-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
}
.monster-why-projection {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: .65rem;
}
.monster-deep-evidence {
    width: 100%;
}

@media (max-width: 760px) {
    .monster-qb-hero-grid,
    .monster-why-projection {
        grid-template-columns: 1fr;
    }
}
</style>
"""


def _install_compact_dashboard_shell(streamlit_module: Any = st) -> None:
    """Install presentation-only V36 hooks; no data or model mutation occurs."""
    streamlit_module.markdown(_COMPACT_DASHBOARD_CSS, unsafe_allow_html=True)


def render_nfl_passing_yards_hub() -> None:
    """Install V36 UI hooks, then render certified V35 unchanged."""
    _install_compact_dashboard_shell()
    return prior.render_nfl_passing_yards_hub()


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V36 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "COMPACT_DASHBOARD_ONLY",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
