"""NFL Passing Yards V80 — expensive evidence cache.

Speed Phase Step 4. Reuses expensive verified football evidence for five minutes
across Streamlit reruns/full-analysis reloads. The cache wraps only frozen
football-data builders already used by the certified pipeline. It does not cache
sportsbook market input and does not alter projection/probability/market math.

The lazy V79 initial page stays unchanged; this optimization applies when full
analysis is explicitly opened.
"""
from __future__ import annotations

import streamlit as st

import nfl_passing_yards_defense_v3 as defense_v3
import nfl_passing_yards_environment_v2 as environment_v2
import nfl_passing_yards_hub_v8 as step7_ui
import nfl_passing_yards_hub_v79 as prior
import nfl_passing_yards_pressure_v2 as pressure_v2

MODEL_VERSION = "NFL PASSING YARDS V80 • SPEED STEP 4 VERIFIED EVIDENCE CACHE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v79"
SPEED_PHASE_STEP = 4
CACHE_VERSION = "v80"
CACHE_TTL_SECONDS = 300
PRESENTATION_ONLY = False
CACHE_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_SPORTSBOOK_BEHAVIOR = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_NAVIGATION_STATE = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_ORIGINAL_PROFILE = step7_ui.profile.build_qb_profile
_ORIGINAL_DEFENSE = defense_v3.build_pass_defense_profile
_ORIGINAL_PRESSURE = pressure_v2.build_pressure_matchup
_ORIGINAL_ENVIRONMENT = environment_v2.build_game_environment


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False, max_entries=96)
def _cached_profile(athlete_id: str, qb_name: str, year: int, season_type: int = 2):
    return _ORIGINAL_PROFILE(athlete_id, qb_name, year, season_type)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False, max_entries=96)
def _cached_defense(team_id: str, team_name: str, year: int, season_type: int, cutoff_date: str):
    return _ORIGINAL_DEFENSE(team_id, team_name, year, season_type, cutoff_date)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False, max_entries=128)
def _cached_pressure(
    offense_team_id: str,
    offense_team_name: str,
    defense_team_id: str,
    defense_team_name: str,
    year: int,
    season_type: int,
    cutoff_date: str,
):
    return _ORIGINAL_PRESSURE(
        offense_team_id,
        offense_team_name,
        defense_team_id,
        defense_team_name,
        year,
        season_type,
        cutoff_date,
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False, max_entries=64)
def _cached_environment(
    game: dict,
    away_ctx: dict,
    home_ctx: dict,
    year: int,
    season_type: int,
    cutoff_date: str,
):
    return _ORIGINAL_ENVIRONMENT(game, away_ctx, home_ctx, year, season_type, cutoff_date)


def render_nfl_passing_yards_hub() -> None:
    # Install wrappers only for this route/render and restore every owner after.
    original_profile = step7_ui.profile.build_qb_profile
    original_defense = defense_v3.build_pass_defense_profile
    original_pressure = pressure_v2.build_pressure_matchup
    original_environment = environment_v2.build_game_environment

    step7_ui.profile.build_qb_profile = _cached_profile
    defense_v3.build_pass_defense_profile = _cached_defense
    pressure_v2.build_pressure_matchup = _cached_pressure
    environment_v2.build_game_environment = _cached_environment
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.profile.build_qb_profile = original_profile
        defense_v3.build_pass_defense_profile = original_defense
        pressure_v2.build_pressure_matchup = original_pressure
        environment_v2.build_game_environment = original_environment


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V80 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "CACHE_ONLY","CACHE_TTL_SECONDS","CACHE_VERSION","FROZEN_PRIOR",
    "MAY_MODIFY_CONTEXT_MATH","MAY_MODIFY_MARKET_MATH","MAY_MODIFY_NAVIGATION_STATE",
    "MAY_MODIFY_PROBABILITY","MAY_MODIFY_PROJECTION","MAY_MODIFY_SPORTSBOOK_BEHAVIOR",
    "MAY_MODIFY_WIDGET_KEYS","MODEL_VERSION","SPEED_PHASE_STEP",
    "SPORTSBOOK_PROJECTION_INFLUENCE","STAKE_SIZING_ENABLED",
    "_cached_defense","_cached_environment","_cached_pressure","_cached_profile",
    "render_nfl_hub","render_nfl_passing_yards_hub",
]
