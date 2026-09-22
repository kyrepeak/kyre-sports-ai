"""Machine-readable frozen release contract for WNBA Step 8.

This module is declarative only. It binds the final Step-8 FastAPI surface to the
live-certified Step-8D Monte Carlo baseline and preserves the entire projection
stack as default-OFF. It does not start a scheduler, call a sportsbook, mutate
Supabase/persistence, or enable production runtime.
"""
from __future__ import annotations

RELEASE_ID = "wnba_step8_projection_probability_2026_regular_season_frozen_v1"
INTEGRATION_VERSION = "wnba_step8e_fastapi_projection_probability_v1"
CERTIFIED_STEP8D_SHA = "932e1baf05bf762cfb149de1f58be4f72bb7a526"
CERTIFIED_BRANCH = "wnba-step8-projection-contract-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"
DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False

ENDPOINT_PATH_TEMPLATE = "/api/v1/wnba/games/{game_id}/players/{player_id}/projection-probabilities"
DEFAULT_SIMULATIONS = 5_000_000
DEFAULT_BATCH_SIZE = 250_000
MAX_API_SIMULATIONS = 10_000_000

MODEL_VERSIONS = {
    "step8b": "wnba_step8b_neutral_official_box_rate_projection_2026_regular_v1",
    "step8c": "wnba_step8c_median_minutes_matchup_pace_2026_regular_v1",
    "step8d": "wnba_step8d_regularized_gaussian_copula_counts_2026_regular_v1",
}

CERTIFIED_SCOPE = {
    "step8a_certified_projection_handoff": True,
    "step8b_official_box_baseline": True,
    "step8b_neutral_deterministic_projection": True,
    "step8c_conservative_context_adjustment": True,
    "step8d_joint_discrete_probability_distribution": True,
    "step8d_five_million_monte_carlo": True,
    "step8e_fastapi_projection_probability_endpoint": True,
    "points_probability_mass": True,
    "rebounds_probability_mass": True,
    "assists_probability_mass": True,
    "pra_probability_mass": True,
    "optional_over_push_under_line_probabilities": True,
}

SAFETY_CONTRACT = {
    "production_runtime_enabled": False,
    "board_scheduler_enabled": False,
    "kyre_direct_sync_enabled": False,
    "kyre_reconciled_sync_enabled": False,
    "step6j_canary_enabled": False,
    "step6l_production_refresh_enabled": False,
    "sportsbook_calls_allowed": False,
    "supabase_mutation_allowed": False,
    "persistence_mutation_allowed": False,
    "step8_flags_default_enabled": False,
    "production_activation_allowed": False,
}
