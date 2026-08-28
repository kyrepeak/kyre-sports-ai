from __future__ import annotations

import os
from typing import Mapping

SOURCE = "Kyre Sports API WNBA Step 11 final live-market shadow release freeze"
SCHEMA_VERSION = "wnba_step_11_final_release_freeze_v1"
INTEGRATION_VERSION = "wnba_step11e_controlled_automation_shadow_freeze_v1"
RELEASE_ID = "wnba_step11_live_multibook_shadow_2026_regular_season_frozen_v1"
SEASON = 2026
SEASON_TYPE = "Regular Season"
BRANCH = "wnba-step11e-controlled-automation-freeze-20260828"

STEP11A_FROZEN_SHA = "695e7b45bd74fcb70c4f4fa6a886b4a054d06810"
STEP11B_FROZEN_SHA = "26072ea38f3d540dc5771405e5c9df728a15f4ff"
STEP11C_FROZEN_SHA = "d33422b3b3807afa256ab6dca56ddea4fef24933"
STEP11D_FROZEN_SHA = "61c57370529cbcfa0802a83e61fc45f15303b006"
STEP10_FROZEN_SHA = "4341d178aa65806e9bc001c8759eccb4a003ea63"
STEP9_FROZEN_SHA = "bd228921ea993c8c74b6454ae56cee94711b0e94"
STEP8_FROZEN_SHA = "8faf468b770f7a31244914df75390fc788f859a1"

STEP11E_CONTROLLED_AUTOMATION_ENABLED_ENV = "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
BACKGROUND_SCHEDULER_ALLOWED = False
PERSISTENCE_ALLOWED = False
SUPABASE_WRITE_ALLOWED = False
WAGERING_ALLOWED = False
PAID_ODDS_VENDOR_REQUIRED = False
SPORTSBOOKS = ("DraftKings", "FanDuel")
SPORTSBOOK_HTTP_METHODS = ("GET",)

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_activation": False,
    "background_scheduler": False,
    "public_fastapi_activation": False,
    "direct_sync": False,
    "reconciled_sync": False,
    "canary": False,
    "production_refresh": False,
    "supabase_write": False,
    "persistence": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "paid_odds_vendor": False,
    "step8_projection_change": False,
    "basketball_model_change": False,
}


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step11e_controlled_automation_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP11E_CONTROLLED_AUTOMATION_ENABLED_ENV))
