"""MLB Step 11A — provider-neutral core market contract.

Step 10 froze durable persistence and recovery. Step 11A starts the provider
expansion block with a pure, fail-closed normalization contract only. It does
not call any sportsbook, change the production API, activate a second provider,
or write to persistence.

The contract is deliberately narrow: one provider, one exact official MLB
gamePk, one market phase, and only the certified core game markets (moneyline,
run line, total). Missing prices stay missing; no synthetic IDs, fuzzy matching,
or price fabrication is permitted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Mapping

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP10_FINAL_FREEZE_STATUS,
)

DATA_TYPE = "mlb_market_provider_game_snapshot_v1"
SCHEMA_VERSION = 1
STEP11A_BASE_MAIN_SHA = "6de8d3b466f661477a1e676fb397e6b9bbdb977a"
CONTRACT_STATUS = "STEP11A_PROVIDER_NEUTRAL_CORE_MARKET_CONTRACT_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP11A_PROVIDER_CONTRACT_GREEN"

SUPPORTED_MARKET_PHASES = ("PREGAME", "IN_PLAY")
SUPPORTED_CORE_MARKETS = ("moneyline", "run_line", "total")
_PROVIDER_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_MARKET_ALLOWED_KEYS = {
    "moneyline": {
        "market_id",
        "market_time_utc",
        "away_odds",
        "home_odds",
        "away_selection_id",
        "home_selection_id",
    },
    "run_line": {
        "market_id",
        "market_time_utc",
        "away_line",
        "away_odds",
        "home_line",
        "home_odds",
        "away_selection_id",
        "home_selection_id",
    },
    "total": {
        "market_id",
        "market_time_utc",
        "line",
        "over_odds",
        "under_odds",
        "over_selection_id",
        "under_selection_id",
    },
}


class MLBProviderContractError(ValueError):
    """Candidate provider data violates the Step 11A contract."""


def provider_contract_manifest() -> dict[str, Any]:
    """Return the immutable Step 11A provider contract boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step11a_base_main_sha": STEP11A_BASE_MAIN_SHA,
        "contract_status": CONTRACT_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step10_final_freeze_status_required": STEP10_FINAL_FREEZE_STATUS,
        "step10_final_certification_marker_required": STEP10_FINAL_CERTIFICATION_MARKER,
        "supported_market_phases": list(SUPPORTED_MARKET_PHASES),
        "supported_core_markets": list(SUPPORTED_CORE_MARKETS),
        "exact_official_game_id_required": True,
        "provider_key_required": True,
        "provider_event_id_required": True,
        "source_payload_sha256_required": True,
        "missing_markets_must_be_omitted": True,
        "partial_market_objects_allowed": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "team_name_join_allowed_downstream": False,
        "network_io_added_by_step11a": False,
        "second_provider_activated_by_step11a": False,
        "production_runtime_wiring_added_by_step11a": False,
        "persistence_schema_changed_by_step11a": False,
        "automatic_production_writes_enabled": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        **PROTECTED_INVARIANTS,
    }


def _nonempty_text(value: Any, field: str, *, max_length: int = 256) -> str:
    if not isinstance(value, str):
        raise MLBProviderContractError(f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise MLBProviderContractError(f"{field} must not be empty")
    if len(normalized) > max_length:
        raise MLBProviderContractError(f"{field} exceeds maximum length {max_length}")
    if any(ord(char) < 32 for char in normalized):
        raise MLBProviderContractError(f"{field} contains control characters")
    return normalized


def _provider_key(value: Any) -> str:
    value = _nonempty_text(value, "provider_key", max_length=32)
    if _PROVIDER_KEY_RE.fullmatch(value) is None:
        raise MLBProviderContractError(
            "provider_key must match ^[a-z0-9][a-z0-9_-]{0,31}$"
        )
    return value


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MLBProviderContractError(f"{field} must be a positive integer")
    return value


def _exact_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise MLBProviderContractError(f"{field} must be a boolean")
    return value


def _utc_rfc3339(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MLBProviderContractError(f"{field} must be UTC RFC3339 ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBProviderContractError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBProviderContractError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _optional_utc_rfc3339(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _utc_rfc3339(value, field)


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise MLBProviderContractError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


def _american_odds(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MLBProviderContractError(f"{field} must be an integer American price")
    if abs(value) < 100 or abs(value) > 100000:
        raise MLBProviderContractError(f"{field} is outside supported American-odds bounds")
    return value


def _finite_line(
    value: Any,
    field: str,
    *,
    minimum: float = -100.0,
    maximum: float = 100.0,
) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise MLBProviderContractError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise MLBProviderContractError(f"{field} is outside supported finite bounds")
    return result


def _selection_id(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise MLBProviderContractError(f"{field} must be a string, integer, or None")
    normalized = str(value).strip()
    if not normalized or len(normalized) > 256:
        raise MLBProviderContractError(f"{field} is invalid")
    return normalized


def _market_mapping(value: Any, market_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBProviderContractError(f"{market_name} must be a mapping")
    if not value:
        raise MLBProviderContractError(f"{market_name} must not be empty")
    unknown = set(value) - _MARKET_ALLOWED_KEYS[market_name]
    if unknown:
        raise MLBProviderContractError(
            f"{market_name} contains unsupported keys: {sorted(unknown)!r}"
        )
    return value


def _market_common(value: Mapping[str, Any], market_name: str) -> dict[str, Any]:
    return {
        "market_id": _nonempty_text(
            value.get("market_id"), f"{market_name}.market_id", max_length=256
        ),
        "market_time_utc": _optional_utc_rfc3339(
            value.get("market_time_utc"), f"{market_name}.market_time_utc"
        ),
    }


def _normalize_moneyline(value: Any) -> dict[str, Any]:
    market = _market_mapping(value, "moneyline")
    result = _market_common(market, "moneyline")
    result.update(
        {
            "away_odds": _american_odds(market.get("away_odds"), "moneyline.away_odds"),
            "home_odds": _american_odds(market.get("home_odds"), "moneyline.home_odds"),
            "away_selection_id": _selection_id(
                market.get("away_selection_id"), "moneyline.away_selection_id"
            ),
            "home_selection_id": _selection_id(
                market.get("home_selection_id"), "moneyline.home_selection_id"
            ),
        }
    )
    return result


def _normalize_run_line(value: Any) -> dict[str, Any]:
    market = _market_mapping(value, "run_line")
    result = _market_common(market, "run_line")
    away_line = _finite_line(market.get("away_line"), "run_line.away_line")
    home_line = _finite_line(market.get("home_line"), "run_line.home_line")
    if not math.isclose(away_line, -home_line, abs_tol=1e-9):
        raise MLBProviderContractError("run_line away_line and home_line must be exact opposites")
    result.update(
        {
            "away_line": away_line,
            "away_odds": _american_odds(market.get("away_odds"), "run_line.away_odds"),
            "home_line": home_line,
            "home_odds": _american_odds(market.get("home_odds"), "run_line.home_odds"),
            "away_selection_id": _selection_id(
                market.get("away_selection_id"), "run_line.away_selection_id"
            ),
            "home_selection_id": _selection_id(
                market.get("home_selection_id"), "run_line.home_selection_id"
            ),
        }
    )
    return result


def _normalize_total(value: Any) -> dict[str, Any]:
    market = _market_mapping(value, "total")
    result = _market_common(market, "total")
    result.update(
        {
            "line": _finite_line(
                market.get("line"), "total.line", minimum=0.0, maximum=100.0
            ),
            "over_odds": _american_odds(market.get("over_odds"), "total.over_odds"),
            "under_odds": _american_odds(market.get("under_odds"), "total.under_odds"),
            "over_selection_id": _selection_id(
                market.get("over_selection_id"), "total.over_selection_id"
            ),
            "under_selection_id": _selection_id(
                market.get("under_selection_id"), "total.under_selection_id"
            ),
        }
    )
    return result


def _normalize_markets(markets: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(markets, Mapping):
        raise MLBProviderContractError("markets must be a mapping")
    unknown = set(markets) - set(SUPPORTED_CORE_MARKETS)
    if unknown:
        raise MLBProviderContractError(f"unsupported core market keys: {sorted(unknown)!r}")
    if not markets:
        raise MLBProviderContractError(
            "provider game snapshot requires at least one real priced core market"
        )

    result: dict[str, dict[str, Any]] = {}
    if "moneyline" in markets:
        result["moneyline"] = _normalize_moneyline(markets["moneyline"])
    if "run_line" in markets:
        result["run_line"] = _normalize_run_line(markets["run_line"])
    if "total" in markets:
        result["total"] = _normalize_total(markets["total"])
    return result


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_market_provider_game_snapshot(
    *,
    provider_key: str,
    provider_name: str,
    provider_event_id: str,
    official_game_id: int,
    observed_at_utc: str,
    source_collected_at_utc: str,
    market_phase: str,
    transport: str,
    source_payload_sha256: str,
    markets: Mapping[str, Any],
    source_complete: bool,
    exact_official_game_id_verified: bool,
    fuzzy_matching_used: bool,
    synthetic_game_id_used: bool,
    price_fabrication_used: bool,
    step10_final_freeze_status: str,
    step10_final_certification_marker: str,
) -> dict[str, Any]:
    """Build one provider-neutral, exact-game core market snapshot.

    Missing markets are represented only by omission from ``markets``. A caller
    may never pass placeholder/partial market objects or fabricated prices.
    """
    key = _provider_key(provider_key)
    display_name = _nonempty_text(provider_name, "provider_name", max_length=64)
    event_id = _nonempty_text(provider_event_id, "provider_event_id", max_length=256)
    game_id = _positive_int(official_game_id, "official_game_id")
    observed = _utc_rfc3339(observed_at_utc, "observed_at_utc")
    source_collected = _utc_rfc3339(source_collected_at_utc, "source_collected_at_utc")
    if source_collected > observed:
        raise MLBProviderContractError("source_collected_at_utc must not be after observed_at_utc")

    if not isinstance(market_phase, str) or market_phase not in SUPPORTED_MARKET_PHASES:
        raise MLBProviderContractError(
            f"market_phase must be one of {SUPPORTED_MARKET_PHASES!r}"
        )
    normalized_transport = _nonempty_text(transport, "transport", max_length=128)
    payload_hash = _sha256(source_payload_sha256, "source_payload_sha256")
    normalized_markets = _normalize_markets(markets)

    complete = _exact_bool(source_complete, "source_complete")
    exact_id = _exact_bool(
        exact_official_game_id_verified, "exact_official_game_id_verified"
    )
    fuzzy = _exact_bool(fuzzy_matching_used, "fuzzy_matching_used")
    synthetic = _exact_bool(synthetic_game_id_used, "synthetic_game_id_used")
    fabricated = _exact_bool(price_fabrication_used, "price_fabrication_used")

    if exact_id is not True:
        raise MLBProviderContractError("exact official MLB gamePk verification is required")
    if fuzzy is not False:
        raise MLBProviderContractError("fuzzy matching is forbidden")
    if synthetic is not False:
        raise MLBProviderContractError("synthetic game IDs are forbidden")
    if fabricated is not False:
        raise MLBProviderContractError("price fabrication is forbidden")
    if step10_final_freeze_status != STEP10_FINAL_FREEZE_STATUS:
        raise MLBProviderContractError("Step 10 final freeze status mismatch")
    if step10_final_certification_marker != STEP10_FINAL_CERTIFICATION_MARKER:
        raise MLBProviderContractError("Step 10 final certification marker mismatch")

    market_availability = {
        name: name in normalized_markets for name in SUPPORTED_CORE_MARKETS
    }
    record_key = (
        f"mlb:{game_id}:provider:{key}:{market_phase}:"
        f"{observed}:{payload_hash}"
    )
    snapshot: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "record_key": record_key,
        "provider_key": key,
        "provider_name": display_name,
        "provider_event_id": event_id,
        "official_game_id": game_id,
        "observed_at_utc": observed,
        "source_collected_at_utc": source_collected,
        "market_phase": market_phase,
        "transport": normalized_transport,
        "source_payload_sha256": payload_hash,
        "markets": normalized_markets,
        "market_availability": market_availability,
        "market_count": len(normalized_markets),
        "fully_priced": all(market_availability.values()),
        "source_complete": complete,
        "exact_official_game_id_verified": True,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "price_fabrication_used": False,
        "step10_final_freeze_status": STEP10_FINAL_FREEZE_STATUS,
        "step10_final_certification_marker": STEP10_FINAL_CERTIFICATION_MARKER,
    }
    snapshot["snapshot_sha256"] = hashlib.sha256(
        _canonical_json(snapshot).encode("utf-8")
    ).hexdigest()
    return snapshot


def validate_market_provider_game_snapshot(
    snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Fail closed and non-mutatingly re-build a Step 11A snapshot."""
    failures: list[str] = []
    if not isinstance(snapshot, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "snapshot_valid": False,
            "failures": ["STEP11A_SNAPSHOT_NOT_MAPPING"],
        }

    try:
        rebuilt = build_market_provider_game_snapshot(
            provider_key=snapshot.get("provider_key"),
            provider_name=snapshot.get("provider_name"),
            provider_event_id=snapshot.get("provider_event_id"),
            official_game_id=snapshot.get("official_game_id"),
            observed_at_utc=snapshot.get("observed_at_utc"),
            source_collected_at_utc=snapshot.get("source_collected_at_utc"),
            market_phase=snapshot.get("market_phase"),
            transport=snapshot.get("transport"),
            source_payload_sha256=snapshot.get("source_payload_sha256"),
            markets=snapshot.get("markets"),
            source_complete=snapshot.get("source_complete"),
            exact_official_game_id_verified=snapshot.get(
                "exact_official_game_id_verified"
            ),
            fuzzy_matching_used=snapshot.get("fuzzy_matching_used"),
            synthetic_game_id_used=snapshot.get("synthetic_game_id_used"),
            price_fabrication_used=snapshot.get("price_fabrication_used"),
            step10_final_freeze_status=snapshot.get("step10_final_freeze_status"),
            step10_final_certification_marker=snapshot.get(
                "step10_final_certification_marker"
            ),
        )
    except Exception as exc:
        failures.append(f"STEP11A_REBUILD_FAILED:{type(exc).__name__}:{exc}")
    else:
        if dict(snapshot) != rebuilt:
            failures.append("STEP11A_SNAPSHOT_EXACT_CONTRACT_MISMATCH")

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "snapshot_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP11A_BASE_MAIN_SHA",
    "CONTRACT_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "SUPPORTED_MARKET_PHASES",
    "SUPPORTED_CORE_MARKETS",
    "MLBProviderContractError",
    "provider_contract_manifest",
    "build_market_provider_game_snapshot",
    "validate_market_provider_game_snapshot",
]
