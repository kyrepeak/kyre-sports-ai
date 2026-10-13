from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

VERSION = "UNIVERSAL_SPORTS_PROVIDER_REGISTRY_V1"
WORKSTREAM = "universal-sports-source-finalization-v1"
STEP = "2/8"
PROGRAM_STEPS = 8
ROUTING_UNIT = "DATA_FIELD"
FREEZE_TOKEN = "UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP2_CREDIBLE_PROVIDER_REGISTRY_FROZEN"

_PROVIDER_ID = re.compile(r"^[a-z0-9_]+$")
_SUPPORTED_SPORTS = {"mlb", "nba", "ncaab", "ncaaf", "nfl", "wnba"}
_REQUIRED_CAPABILITIES = {
    "schedule",
    "game_identity",
    "team_identity",
    "player_identity",
    "rosters",
    "injuries",
    "official_stats",
    "advanced_stats",
    "matchup_history",
    "sportsbook_lines",
    "line_movement",
    "public_bet_count",
    "public_bet_percentage",
    "money_percentage",
    "news_context",
}
_REQUIRED_TOP_LEVEL = {
    "version": VERSION,
    "workstream": WORKSTREAM,
    "step": STEP,
    "program_steps": PROGRAM_STEPS,
    "routing_unit": ROUTING_UNIT,
    "page_wide_source_authority": False,
    "approved_pool_is_active_pool": False,
    "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
    "network_calls": False,
    "product_runtime_mutation": False,
    "sports_model_mutation": False,
    "legacy_registry_mutation": False,
    "github_actions_fallback": 0,
    "fabrication": False,
    "freeze_token": FREEZE_TOKEN,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _registry_id(registry_without_id: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(registry_without_id).encode("utf-8")).hexdigest()[:24].upper()
    return f"USPR-{digest}"


def load_registry(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("REGISTRY_NOT_OBJECT")
    return value


def validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(registry, Mapping):
        raise ValueError("REGISTRY_NOT_OBJECT")

    raw = deepcopy(dict(registry))
    supplied_registry_id = str(raw.pop("registry_id", "") or "").strip().upper()
    for key, expected in _REQUIRED_TOP_LEVEL.items():
        if raw.get(key) != expected:
            raise ValueError(f"REGISTRY_CONTRACT_DRIFT:{key}")

    expected_registry_id = _registry_id(raw)
    if supplied_registry_id != expected_registry_id:
        raise ValueError("REGISTRY_FINGERPRINT_MISMATCH")

    supported_sports = raw.get("supported_sports")
    if not isinstance(supported_sports, list) or set(supported_sports) != _SUPPORTED_SPORTS:
        raise ValueError("SUPPORTED_SPORTS_DRIFT")
    if len(supported_sports) != len(set(supported_sports)):
        raise ValueError("SUPPORTED_SPORTS_DUPLICATE")

    capabilities = raw.get("capabilities")
    if not isinstance(capabilities, Mapping) or not _REQUIRED_CAPABILITIES <= set(capabilities):
        raise ValueError("CAPABILITY_CONTRACT_INCOMPLETE")

    semantic_ids: set[str] = set()
    for capability, record in capabilities.items():
        if not isinstance(record, Mapping):
            raise ValueError(f"CAPABILITY_RECORD_INVALID:{capability}")
        semantic_id = str(record.get("semantic_metric_id") or "").strip().upper()
        if not semantic_id or semantic_id in semantic_ids:
            raise ValueError(f"SEMANTIC_METRIC_ID_INVALID:{capability}")
        semantic_ids.add(semantic_id)
        substitutes = record.get("compatible_substitutes")
        if not isinstance(substitutes, list):
            raise ValueError(f"COMPATIBLE_SUBSTITUTES_INVALID:{capability}")

    for capability in ("public_bet_count", "public_bet_percentage", "money_percentage"):
        if capabilities[capability].get("compatible_substitutes") != []:
            raise ValueError(f"INCOMPATIBLE_BET_METRIC_SUBSTITUTION:{capability}")

    providers = raw.get("providers")
    if not isinstance(providers, list) or len(providers) < 12:
        raise ValueError("PROVIDER_POOL_TOO_SMALL")

    provider_ids: set[str] = set()
    capability_coverage = {capability: 0 for capability in _REQUIRED_CAPABILITIES}
    for provider in providers:
        if not isinstance(provider, Mapping):
            raise ValueError("PROVIDER_RECORD_INVALID")
        provider_id = str(provider.get("provider_id") or "").strip()
        if not _PROVIDER_ID.fullmatch(provider_id) or provider_id in provider_ids:
            raise ValueError("PROVIDER_ID_INVALID_OR_DUPLICATE")
        provider_ids.add(provider_id)

        if not str(provider.get("display_name") or "").strip():
            raise ValueError(f"PROVIDER_DISPLAY_NAME_REQUIRED:{provider_id}")
        if not str(provider.get("reference_domain") or "").strip():
            raise ValueError(f"PROVIDER_REFERENCE_DOMAIN_REQUIRED:{provider_id}")
        if not str(provider.get("source_type") or "").strip():
            raise ValueError(f"PROVIDER_SOURCE_TYPE_REQUIRED:{provider_id}")
        if provider.get("active") is not False:
            raise ValueError(f"APPROVED_POOL_MAY_NOT_MARK_ACTIVE:{provider_id}")
        if provider.get("page_wide_authority") is not False:
            raise ValueError(f"PAGE_WIDE_AUTHORITY_FORBIDDEN:{provider_id}")

        sports = provider.get("sports")
        if not isinstance(sports, list) or not sports:
            raise ValueError(f"PROVIDER_SPORTS_REQUIRED:{provider_id}")
        if len(sports) != len(set(sports)) or not set(sports) <= _SUPPORTED_SPORTS:
            raise ValueError(f"PROVIDER_SPORT_SCOPE_INVALID:{provider_id}")

        provider_capabilities = provider.get("capabilities")
        if not isinstance(provider_capabilities, list) or not provider_capabilities:
            raise ValueError(f"PROVIDER_CAPABILITIES_REQUIRED:{provider_id}")
        if len(provider_capabilities) != len(set(provider_capabilities)):
            raise ValueError(f"PROVIDER_CAPABILITIES_DUPLICATE:{provider_id}")
        unknown_capabilities = set(provider_capabilities) - set(capabilities)
        if unknown_capabilities:
            raise ValueError(f"PROVIDER_CAPABILITY_UNKNOWN:{provider_id}")
        for capability in provider_capabilities:
            if capability in capability_coverage:
                capability_coverage[capability] += 1

        access = provider.get("access")
        if not isinstance(access, Mapping):
            raise ValueError(f"PROVIDER_ACCESS_REQUIRED:{provider_id}")
        credential_required = access.get("credential_required")
        configuration_state = str(access.get("configuration_state") or "").strip().upper()
        reachability_state = str(access.get("reachability_state") or "").strip().upper()
        if credential_required not in (True, False):
            raise ValueError(f"PROVIDER_CREDENTIAL_FLAG_INVALID:{provider_id}")
        expected_configuration = "NOT_CLAIMED" if credential_required else "NOT_REQUIRED"
        if configuration_state != expected_configuration:
            raise ValueError(f"PROVIDER_CONFIGURATION_CLAIM_INVALID:{provider_id}")
        if reachability_state != "UNVERIFIED":
            raise ValueError(f"PROVIDER_REACHABILITY_MUST_BE_UNVERIFIED:{provider_id}")

    uncovered = sorted(capability for capability, count in capability_coverage.items() if count == 0)
    if uncovered:
        raise ValueError(f"CAPABILITY_WITHOUT_PROVIDER:{','.join(uncovered)}")

    return {
        "status": "GREEN",
        "version": VERSION,
        "workstream": WORKSTREAM,
        "step": STEP,
        "program_steps": PROGRAM_STEPS,
        "routing_unit": ROUTING_UNIT,
        "page_wide_source_authority": False,
        "approved_pool_is_active_pool": False,
        "active_provider_semantics": "ACTUALLY_CONSULTED_ONLY",
        "network_calls": False,
        "product_runtime_mutation": False,
        "sports_model_mutation": False,
        "legacy_registry_mutation": False,
        "github_actions_fallback": 0,
        "provider_count": len(providers),
        "capability_count": len(capabilities),
        "registry_id": supplied_registry_id,
        "freeze_token": FREEZE_TOKEN,
    }


def providers_for_capability(
    registry: Mapping[str, Any],
    *,
    capability: str,
    sport: str | None = None,
) -> list[dict[str, Any]]:
    validate_registry(registry)
    capability_key = str(capability or "").strip().lower()
    sport_key = str(sport or "").strip().lower()
    capabilities = registry.get("capabilities") or {}
    if capability_key not in capabilities:
        return []
    if sport_key and sport_key not in _SUPPORTED_SPORTS:
        return []

    rows = []
    for provider in registry.get("providers") or []:
        if capability_key not in (provider.get("capabilities") or []):
            continue
        if sport_key and sport_key not in (provider.get("sports") or []):
            continue
        rows.append(deepcopy(dict(provider)))
    return sorted(rows, key=lambda row: str(row["provider_id"]))
