"""WNBA Step 12D: final Step-12 runtime release freeze.

This module does not add runtime behavior. It freezes the certified Step-12A/B/C
lineage and the safety contract that must remain intact before Step 13 may add an
external scheduler. Step 12 remains caller-driven, shadow-only, read-only, and
default-OFF.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Mapping

from sports_api import wnba_step11_release_freeze as step11_release
from sports_api import wnba_step12_shadow_runner as step12a
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step12c_live_board_runtime as step12c

SOURCE = "Kyre Sports API WNBA Step 12 final live-board runtime release freeze"
SCHEMA_VERSION = "wnba_step_12_final_runtime_release_freeze_v1"
INTEGRATION_VERSION = "wnba_step12d_live_runtime_freeze_v1"
RELEASE_ID = "wnba_step12_live_board_runtime_2026_regular_season_frozen_v1"
SEASON = 2026
SEASON_TYPE = "Regular Season"
BRANCH = "wnba-step12d-final-runtime-freeze-20260828"

STEP12A_FROZEN_SHA = "4523abb8b230e8e29d9f9d298232dfb8948fc883"
STEP12B_FROZEN_SHA = "a109be6116fde66e6857d6c676c0f08790a334f3"
STEP12C_FROZEN_SHA = "26902667212e670903b19002f7166ea435b238c2"
STEP11E_FROZEN_SHA = "f96d580e398aaa199c424e3b70b7a8f1386a8452"
STEP11A_FROZEN_SHA = step11_release.STEP11A_FROZEN_SHA
STEP11B_FROZEN_SHA = step11_release.STEP11B_FROZEN_SHA
STEP11C_FROZEN_SHA = step11_release.STEP11C_FROZEN_SHA
STEP11D_FROZEN_SHA = step11_release.STEP11D_FROZEN_SHA
STEP10_FROZEN_SHA = step11_release.STEP10_FROZEN_SHA
STEP9_FROZEN_SHA = step11_release.STEP9_FROZEN_SHA
STEP8_FROZEN_SHA = step11_release.STEP8_FROZEN_SHA

STEP12D_FINAL_RUNTIME_FREEZE_ENABLED_ENV = "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
BACKGROUND_SCHEDULER_ALLOWED = False
PERSISTENCE_ALLOWED = False
SUPABASE_WRITE_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
PAID_ODDS_VENDOR_REQUIRED = False
RUNTIME_MUTATION_ALLOWED = False
SPORTSBOOKS = ("DraftKings", "FanDuel")
SPORTSBOOK_HTTP_METHODS = ("GET",)
CERTIFIED_SIMULATIONS = 5_000_000
CERTIFIED_BATCH_SIZE = step12c.CERTIFIED_BATCH_SIZE

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
    "runtime_mutation": False,
    "step8_distribution_change": False,
    "basketball_model_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
    "step12c_presentation_reranking": False,
}

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

_REQUIRED_TRUE_ENV_KEYS = (
    "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
    "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
    "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
    "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
)


class WNBAStep12FinalFreezeDisabledError(RuntimeError):
    """Raised when the Step-12 final freeze certification gate is not isolated."""


class WNBAStep12FinalFreezeIntegrityError(RuntimeError):
    """Raised when frozen Step-12 lineage or safety constants drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step12d_final_runtime_freeze_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP12D_FINAL_RUNTIME_FREEZE_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _assert_release_integrity(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step12d_final_runtime_freeze_enabled(source):
        raise WNBAStep12FinalFreezeDisabledError(
            f"Step 12D requires {STEP12D_FINAL_RUNTIME_FREEZE_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep12FinalFreezeDisabledError(
            "Step 12D refuses production/scheduler/persistence/write switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep12FinalFreezeDisabledError(
            "Step 12D requires frozen Step-12 runtime gates: " + ", ".join(missing)
        )

    exact = {
        "step12c_parent": step12c.STEP12B_FROZEN_SHA == STEP12B_FROZEN_SHA,
        "step12b_parent": step12b.STEP12A_FROZEN_SHA == STEP12A_FROZEN_SHA,
        "step12a_parent": step12a.STEP11E_FROZEN_SHA == STEP11E_FROZEN_SHA,
        "step8_lineage": step12b.STEP8_FROZEN_SHA == STEP8_FROZEN_SHA,
        "simulation_count": step12c.CERTIFIED_SIMULATIONS == CERTIFIED_SIMULATIONS,
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise WNBAStep12FinalFreezeIntegrityError(
            "Step 12D frozen lineage drift: " + ", ".join(failed)
        )

    constants = {
        "step12d_default": DEFAULT_ENABLED,
        "step12d_production": PRODUCTION_ACTIVATION_ALLOWED,
        "step12d_public_api": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step12d_scheduler": BACKGROUND_SCHEDULER_ALLOWED,
        "step12d_persistence": PERSISTENCE_ALLOWED,
        "step12d_supabase": SUPABASE_WRITE_ALLOWED,
        "step12d_wagering": WAGERING_ALLOWED,
        "step12d_authentication": AUTHENTICATION_ALLOWED,
        "step12d_cookies": COOKIES_ALLOWED,
        "step12d_runtime_mutation": RUNTIME_MUTATION_ALLOWED,
        "step12c_default": step12c.DEFAULT_ENABLED,
        "step12c_production": step12c.PRODUCTION_ACTIVATION_ALLOWED,
        "step12c_scheduler": step12c.BACKGROUND_SCHEDULER_ALLOWED,
        "step12c_persistence": step12c.PERSISTENCE_ALLOWED,
        "step12c_supabase": step12c.SUPABASE_WRITE_ALLOWED,
        "step12c_public_api": step12c.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step12c_wagering": step12c.WAGERING_ALLOWED,
        "step12b_default": step12b.DEFAULT_ENABLED,
        "step12b_production": step12b.PRODUCTION_ACTIVATION_ALLOWED,
        "step12b_scheduler": step12b.BACKGROUND_SCHEDULER_ALLOWED,
        "step12b_persistence": step12b.PERSISTENCE_ALLOWED,
        "step12b_supabase": step12b.SUPABASE_WRITE_ALLOWED,
        "step12b_public_api": step12b.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step12b_wagering": step12b.WAGERING_ALLOWED,
        "step12a_default": step12a.DEFAULT_ENABLED,
        "step12a_production": step12a.PRODUCTION_ACTIVATION_ALLOWED,
        "step12a_scheduler": step12a.BACKGROUND_SCHEDULER_ALLOWED,
        "step12a_persistence": step12a.PERSISTENCE_ALLOWED,
        "step12a_supabase": step12a.SUPABASE_WRITE_ALLOWED,
        "step12a_public_api": step12a.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step12a_wagering": step12a.WAGERING_ALLOWED,
    }
    drift = [name for name, value in constants.items() if value is not False]
    if drift:
        raise WNBAStep12FinalFreezeIntegrityError(
            "Step 12D safety constant drift: " + ", ".join(drift)
        )


def build_step12d_release_manifest(
    *, env: Mapping[str, str] | None = None, generated_at_utc: str | None = None
) -> dict[str, Any]:
    """Return a content-addressed manifest for the certified Step-12 frozen release."""
    _assert_release_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": "wnba_step12_final_runtime_release_freeze",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "integration_version": INTEGRATION_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": generated,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "branch": BRANCH,
        "lineage": {
            "step12a_frozen_sha": STEP12A_FROZEN_SHA,
            "step12b_frozen_sha": STEP12B_FROZEN_SHA,
            "step12c_frozen_sha": STEP12C_FROZEN_SHA,
            "step11e_frozen_sha": STEP11E_FROZEN_SHA,
            "step11a_frozen_sha": STEP11A_FROZEN_SHA,
            "step11b_frozen_sha": STEP11B_FROZEN_SHA,
            "step11c_frozen_sha": STEP11C_FROZEN_SHA,
            "step11d_frozen_sha": STEP11D_FROZEN_SHA,
            "step10_frozen_sha": STEP10_FROZEN_SHA,
            "step9_frozen_sha": STEP9_FROZEN_SHA,
            "step8_frozen_sha": STEP8_FROZEN_SHA,
        },
        "runtime_contract": {
            "caller_driven": True,
            "shadow_only": True,
            "read_only": True,
            "sportsbooks": list(SPORTSBOOKS),
            "sportsbook_http_methods": list(SPORTSBOOK_HTTP_METHODS),
            "official_wnba_identity_reconciliation_required": True,
            "exact_line_multibook_consensus_required": True,
            "certified_simulations_per_projection": CERTIFIED_SIMULATIONS,
            "certified_batch_size": CERTIFIED_BATCH_SIZE,
            "frozen_step9_ranking_preserved": True,
            "frozen_step9_qualification_preserved": True,
            "step12c_presentation_only": True,
            "top_five_never_forced": True,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step12_complete": True,
            "step13_scheduler_not_started": True,
            "step14_persistence_not_started": True,
            "production_not_started": True,
        },
    }
    hash_surface = deepcopy(result)
    hash_surface.pop("generated_at_utc", None)
    result["release_content_sha256"] = _canonical_hash(hash_surface)
    _assert_release_integrity(env)
    return result


__all__ = [
    "BRANCH",
    "CERTIFIED_BATCH_SIZE",
    "CERTIFIED_SIMULATIONS",
    "DEFAULT_ENABLED",
    "INTEGRATION_VERSION",
    "RELEASE_ID",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SEASON",
    "SEASON_TYPE",
    "SOURCE",
    "STEP12A_FROZEN_SHA",
    "STEP12B_FROZEN_SHA",
    "STEP12C_FROZEN_SHA",
    "STEP12D_FINAL_RUNTIME_FREEZE_ENABLED_ENV",
    "WNBAStep12FinalFreezeDisabledError",
    "WNBAStep12FinalFreezeIntegrityError",
    "build_step12d_release_manifest",
    "step12d_final_runtime_freeze_enabled",
]
