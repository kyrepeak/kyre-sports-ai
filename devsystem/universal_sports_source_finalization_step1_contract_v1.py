from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

VERSION = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP1_CONTRACT"
WORKSTREAM = "universal-sports-source-finalization-v1"
STEP = "1/8"
PROGRAM_STEPS = 8
ROUTING_UNIT = "DATA_FIELD"
FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP1_ARCHITECTURE_CONTRACT_FROZEN"

_REQUIRED = {
    "version": VERSION,
    "workstream": WORKSTREAM,
    "step": STEP,
    "program_steps": PROGRAM_STEPS,
    "routing_unit": ROUTING_UNIT,
    "page_wide_source_authority": False,
    "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
    "incompatible_metric_substitution": False,
    "minimum_quorum_early_stop": True,
    "render_dependency": False,
    "github_actions_fallback": 0,
    "legacy_registry_mutation": False,
    "freeze_token": FREEZE_TOKEN,
}


def load_contract(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("STEP1_CONTRACT_NOT_OBJECT")
    return value


def certify_contract(contract: Mapping[str, Any], spec_text: str) -> dict[str, Any]:
    if not isinstance(contract, Mapping):
        raise ValueError("STEP1_CONTRACT_NOT_OBJECT")
    raw = deepcopy(dict(contract))
    for key, expected in _REQUIRED.items():
        if raw.get(key) != expected:
            raise ValueError(f"STEP1_CONTRACT_DRIFT:{key}")

    provider_semantics = raw.get("provider_semantics")
    if not isinstance(provider_semantics, Mapping):
        raise ValueError("STEP1_PROVIDER_SEMANTICS_REQUIRED")
    if provider_semantics.get("approved_pool_is_active_pool") is not False:
        raise ValueError("STEP1_APPROVED_ACTIVE_POOL_COLLISION")
    if provider_semantics.get("active_means_consulted") is not True:
        raise ValueError("STEP1_ACTIVE_PROVIDER_SEMANTICS_DRIFT")
    if provider_semantics.get("category_ownership_required") is not True:
        raise ValueError("STEP1_CATEGORY_OWNERSHIP_REQUIRED")

    compatibility = raw.get("semantic_compatibility")
    if not isinstance(compatibility, Mapping):
        raise ValueError("STEP1_SEMANTIC_COMPATIBILITY_REQUIRED")
    forbidden = compatibility.get("forbidden_substitutions")
    if not isinstance(forbidden, Mapping):
        raise ValueError("STEP1_FORBIDDEN_SUBSTITUTIONS_REQUIRED")
    bet_count_forbidden = set(forbidden.get("public_bet_count") or [])
    if not {"public_bet_percentage", "money_percentage"} <= bet_count_forbidden:
        raise ValueError("STEP1_BET_COUNT_SUBSTITUTION_DRIFT")

    text = str(spec_text or "")
    for marker in (WORKSTREAM, ROUTING_UNIT, FREEZE_TOKEN):
        if marker not in text:
            raise ValueError(f"STEP1_SPEC_BINDING_MISSING:{marker}")

    return {
        "status": "GREEN",
        "workstream": WORKSTREAM,
        "step": STEP,
        "program_steps": PROGRAM_STEPS,
        "routing_unit": ROUTING_UNIT,
        "page_wide_source_authority": False,
        "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
        "incompatible_metric_substitution": False,
        "minimum_quorum_early_stop": True,
        "render_dependency": False,
        "github_actions_fallback": 0,
        "legacy_registry_mutation": False,
        "freeze_token": FREEZE_TOKEN,
    }
