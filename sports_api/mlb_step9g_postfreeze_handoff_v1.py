"""MLB Step 9G — post-freeze production handoff attestation.

Step 9F already froze the certified Step 9 live API/consumer integration chain.
Step 9G is therefore deliberately non-behavioral: it may only prove that the
merged Step 9F freeze is still intact and that the deployed read-only live-state
and live-market boundaries continue to honor that frozen contract.

This module performs no network I/O and changes no runtime/model behavior.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP9F_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP9F_FINAL_FREEZE_STATUS,
    PROTECTED_INVARIANTS,
    STEP9_STAGE_CHAIN,
    final_freeze_manifest,
)

DATA_TYPE = "mlb_step9g_postfreeze_handoff_v1"
SCHEMA_VERSION = 1
STEP9G_BASE_MAIN_SHA = "00f117a612817ab8476412fe0cadb6b840910517"
HANDOFF_STATUS = "STEP9_POSTFREEZE_PRODUCTION_HANDOFF_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP9G_POSTFREEZE_PRODUCTION_HANDOFF_GREEN"


def handoff_manifest() -> dict[str, Any]:
    """Return the immutable Step 9G non-behavioral handoff contract."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step9g_base_main_sha": STEP9G_BASE_MAIN_SHA,
        "handoff_status": HANDOFF_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step9f_final_freeze_status": STEP9F_FINAL_FREEZE_STATUS,
        "step9f_final_certification_marker": STEP9F_FINAL_CERTIFICATION_MARKER,
        "stage_chain": list(STEP9_STAGE_CHAIN),
        "read_only_handoff": True,
        "step9f_frozen_prerequisite_required": True,
        "automatic_runtime_mutation": False,
        "runtime_files_changed_by_step9g": False,
        "network_io_in_module": False,
        "exact_official_game_id_required": True,
        "team_name_matching_allowed": False,
        "player_name_matching_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "stale_live_state_context_allowed": False,
        "stale_live_market_context_allowed": False,
        "missing_live_market_price_fabrication_allowed": False,
        "live_game_state_api_first": True,
        "live_market_api_first": True,
        **PROTECTED_INVARIANTS,
    }


def validate_postfreeze_handoff(
    *,
    step9f_manifest: Mapping[str, Any] | None,
    runtime_base_sha: str | None,
    live_state_contract_ok: bool,
    live_market_contract_ok: bool,
    no_price_fabrication_ok: bool,
) -> dict[str, Any]:
    """Fail closed unless the frozen Step 9F state and production checks are exact."""
    failures: list[str] = []
    expected_step9f = final_freeze_manifest()

    if str(runtime_base_sha or "") != STEP9G_BASE_MAIN_SHA:
        failures.append("STEP9G_RUNTIME_BASE_SHA_MISMATCH")

    if not isinstance(step9f_manifest, Mapping):
        failures.append("STEP9F_FREEZE_MANIFEST_MISSING")
    elif dict(step9f_manifest) != expected_step9f:
        failures.append("STEP9F_FREEZE_MANIFEST_MISMATCH")

    if live_state_contract_ok is not True:
        failures.append("STEP9G_LIVE_STATE_CONTRACT_NOT_PROVEN")
    if live_market_contract_ok is not True:
        failures.append("STEP9G_LIVE_MARKET_CONTRACT_NOT_PROVEN")
    if no_price_fabrication_ok is not True:
        failures.append("STEP9G_NO_PRICE_FABRICATION_NOT_PROVEN")

    result = handoff_manifest()
    result.update(
        {
            "handoff_eligible": not failures,
            "handoff_status": HANDOFF_STATUS if not failures else "STEP9_POSTFREEZE_HANDOFF_REJECTED",
            "runtime_base_sha": str(runtime_base_sha or ""),
            "step9f_freeze_intact": isinstance(step9f_manifest, Mapping)
            and dict(step9f_manifest) == expected_step9f,
            "live_state_contract_ok": live_state_contract_ok is True,
            "live_market_contract_ok": live_market_contract_ok is True,
            "no_price_fabrication_ok": no_price_fabrication_ok is True,
            "failures": failures,
        }
    )
    return result


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP9G_BASE_MAIN_SHA",
    "HANDOFF_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "handoff_manifest",
    "validate_postfreeze_handoff",
]
