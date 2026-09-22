"""Frozen release manifest for WNBA Step 10 full live-market board integration."""
from __future__ import annotations

import os
from typing import Mapping

RELEASE_ID = "wnba_step10_live_market_board_2026_regular_season_frozen_v1"
INTEGRATION_VERSION = "wnba_step10e_fastapi_live_market_board_v1"
SEASON = 2026
SEASON_TYPE = "Regular Season"
BRANCH = "wnba-step10e-live-pipeline-20260828"

STEP8_FROZEN_SHA = "8faf468b770f7a31244914df75390fc788f859a1"
STEP9_FROZEN_SHA = "bd228921ea993c8c74b6454ae56cee94711b0e94"
STEP10A_FROZEN_SHA = "4a8f822684c1d56d1ef062f0db25d5f671409def"
STEP10B_FROZEN_SHA = "1088358452ca2bc9e45a2bb3544b44331606d88c"
STEP10C_FROZEN_SHA = "a5264f40d2fe9f17e5cefa3c20e0d2ad31b73f3e"
STEP10D_FROZEN_SHA = "6d289d0a3d3bd74c9c18db7e54457728a57c1f3d"

ENDPOINT_PATH = "/api/v1/wnba/props/live-market-board"
ENDPOINT_METHOD = "POST"
STEP10_FASTAPI_ENABLED_ENV = "WNBA_STEP10_FASTAPI_ENABLED"
DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False

SAFETY_CONTRACT = {
    "production_runtime_enabled": False,
    "scheduler_started": False,
    "sportsbook_network_fetch_enabled": False,
    "retry_sleep_enabled": False,
    "supabase_mutated": False,
    "persistence_mutated": False,
    "direct_sync_enabled": False,
    "reconciled_sync_enabled": False,
    "canary_enabled": False,
    "production_refresh_enabled": False,
    "production_activation_allowed": False,
    "default_step10_fastapi_enabled": False,
}


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step10_fastapi_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP10_FASTAPI_ENABLED_ENV))
