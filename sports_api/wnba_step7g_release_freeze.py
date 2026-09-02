"""Machine-readable frozen release contract for WNBA Step 7G.

This module is declarative only. It does not install runtime seams or enable any
production, scheduler, sync, persistence, Supabase, or sportsbook behavior.
"""
from __future__ import annotations

RELEASE_ID = "wnba_step7g_first_party_2026_regular_season_frozen_v1"
INTEGRATION_VERSION = "wnba_step_7g_first_party_core_integration_v11_officiating_certified"
CERTIFIED_BASELINE_SHA = "368dbde84ea0aa6f570703688ae899285ecd7cfc"
CERTIFIED_BASELINE_BRANCH = "wnba-step7g-official-data-preflight-20260827"
SEASON = 2026
SEASON_TYPE = "Regular Season"
DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False

CERTIFIED_SCOPE = {
    "core_model_input_readiness": True,
    "current_availability_daily_schedule": True,
    "current_availability_roster": True,
    "current_availability_injury_report": True,
    "current_availability_coordinate_parser": True,
    "current_availability": True,
    "shot_context": True,
    "advanced_context": True,
    "officiating_context": True,
}

REQUIRED_RELEASE_DEFAULT_CHECKS = (
    "current_availability_available",
    "shot_context_coverage",
    "advanced_context_coverage",
    "officiating_context_coverage",
)

ALLOWED_NON_BLOCKING_WARNING_IDS = frozenset(
    {
        "optional_starter_bench_role",
        "optional_five_player_lineups",
    }
)

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
}
