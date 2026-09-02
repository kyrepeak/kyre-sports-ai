"""Frozen release manifest for WNBA Step 9 market-board API integration."""
from __future__ import annotations

import os
from typing import Mapping

RELEASE_ID = "wnba_step9_market_board_2026_regular_season_frozen_v1"
INTEGRATION_VERSION = "wnba_step9e_fastapi_market_board_v1"
SEASON = 2026
SEASON_TYPE = "Regular Season"
BRANCH = "wnba-step9e-fastapi-freeze-20260828"

STEP8_FROZEN_SHA = "8faf468b770f7a31244914df75390fc788f859a1"
STEP9A_FROZEN_SHA = "3b9acde91250d0e7a1767f3861765d4366f510ba"
STEP9B_FROZEN_SHA = "45cd3b43ca2771ae01f6fa3c7345ef0b9a444394"
STEP9C_FROZEN_SHA = "7372d5a22665e84cd0179c2346939d953e52c31a"
STEP9D_FROZEN_SHA = "c05908fa6cb79f44921d08ba0bd3ef8f2998c4eb"

MODEL_VERSIONS = {
    "step9a": "wnba_step9a_post_step8_threshold_pricing_2026_regular_v1",
    "step9b": "wnba_step9b_post_projection_market_comparison_2026_regular_v1",
    "step9c": "wnba_step9c_same_line_consensus_best_offer_2026_regular_v1",
    "step9d": "wnba_step9d_qualified_probability_value_ranking_2026_regular_v1",
}

ENDPOINT_PATH = "/api/v1/wnba/props/market-board"
ENDPOINT_METHOD = "POST"
STEP9_FASTAPI_ENABLED_ENV = "WNBA_STEP9_FASTAPI_ENABLED"
DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False

DEFAULT_TOP_N = 5
DEFAULT_MINIMUM_MODEL_PROBABILITY = 0.55
DEFAULT_MINIMUM_EV = 0.05
DEFAULT_MINIMUM_CONSENSUS_EDGE = 0.03
DEFAULT_MINIMUM_BOOKS_AT_LINE = 2
DEFAULT_MAXIMUM_CONSENSUS_RANGE_PERCENTAGE_POINTS = 8.0
DEFAULT_MAX_BOARD_SNAPSHOT_SPREAD_SECONDS = 300
DEFAULT_MAX_PROP_SNAPSHOT_SPREAD_SECONDS = 120
DEFAULT_MAX_MARKET_AGE_MINUTES = 10

SAFETY_CONTRACT = {
    "production_runtime_enabled": False,
    "scheduler_started": False,
    "sportsbook_network_fetch_enabled": False,
    "supabase_mutated": False,
    "persistence_mutated": False,
    "direct_sync_enabled": False,
    "reconciled_sync_enabled": False,
    "canary_enabled": False,
    "production_refresh_enabled": False,
    "production_activation_allowed": False,
    "default_step9_fastapi_enabled": False,
}


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step9_fastapi_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP9_FASTAPI_ENABLED_ENV))
