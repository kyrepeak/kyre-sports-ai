"""Step 10B: provider payload adapters -> frozen Step-10A market contract.

This layer converts supported caller-supplied provider shapes into the exact frozen
Step-10A live-market record contract. It performs no sportsbook/network fetches and
never changes basketball projections, model probabilities, vig, edge, EV, consensus,
ranking, persistence, scheduling, or production state.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping, Sequence

from sports_api import wnba_step10_live_market_input as step10a

SOURCE = "Kyre Sports API WNBA Step 10B strict sportsbook market adapters"
SCHEMA_VERSION = "wnba_step_10b_market_adapter_v1"
MODEL_VERSION = "wnba_step10b_strict_provider_adapter_2026_regular_v1"
RELEASE_ID = "wnba_step10b_market_adapter_2026_regular_season_v1"
STEP10B_MARKET_ADAPTER_ENABLED_ENV = "WNBA_STEP10B_MARKET_ADAPTER_ENABLED"
STEP10A_FROZEN_HEAD_SHA = "4a8f822684c1d56d1ef062f0db25d5f671409def"

ADAPTER_FLAT_TWO_WAY_V1 = "flat_two_way_v1"
ADAPTER_OUTCOMES_TWO_WAY_V1 = "outcomes_two_way_v1"
SUPPORTED_ADAPTERS = (ADAPTER_FLAT_TWO_WAY_V1, ADAPTER_OUTCOMES_TWO_WAY_V1)
SUPPORTED_PRICE_FORMATS = ("american", "decimal")
MAX_PROVIDER_LABEL = 100
MAX_DECIMAL_ODDS = 1_001.0

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep10MarketAdapterDisabledError(RuntimeError):
    """Raised when Step 10B is not isolated behind its certification gates."""


class WNBAStep10MarketAdapterPayloadError(ValueError):
    """Raised when a provider payload is structurally ambiguous or unsupported."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step10b_market_adapter_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP10B_MARKET_ADAPTER_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep10MarketAdapterDisabledError(
            "Step 10B refuses to run while production switches are enabled: "
            + ", ".join(bad)
        )
    if not _truthy(source.get(STEP10B_MARKET_ADAPTER_ENABLED_ENV)):
        raise WNBAStep10MarketAdapterDisabledError(
            f"Step 10B requires {STEP10B_MARKET_ADAPTER_ENABLED_ENV}=true."
        )
    if not step10a.step10a_live_market_input_enabled(source):
        raise WNBAStep10MarketAdapterDisabledError(
            "Step 10B requires the frozen Step-10A input gate to be explicitly enabled."
        )


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _strict_keys(value: Mapping[str, Any], *, allowed: set[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise WNBAStep10MarketAdapterPayloadError(f"WNBA Step 10B {label} must be an object.")
    extras = sorted(str(key) for key in value if key not in allowed)
    missing = sorted(key for key in allowed if key not in value)
    if extras:
        raise WNBAStep10MarketAdapterPayloadError(
            f"WNBA Step 10B rejects unknown {label} fields: " + ", ".join(extras)
        )
    if missing:
        raise WNBAStep10MarketAdapterPayloadError(
            f"WNBA Step 10B missing required {label} fields: " + ", ".join(missing)
        )


def _clean_provider(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text or len(text) > MAX_PROVIDER_LABEL:
        raise WNBAStep10MarketAdapterPayloadError(
            f"WNBA Step 10B provider must contain 1 through {MAX_PROVIDER_LABEL} characters."
        )
    return text


def _price_format(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text not in SUPPORTED_PRICE_FORMATS:
        raise WNBAStep10MarketAdapterPayloadError(
            "WNBA Step 10B price_format must be 'american' or 'decimal'."
        )
    return text


def _american_from_price(value: Any, *, price_format: str) -> int:
    if isinstance(value, bool):
        raise WNBAStep10MarketAdapterPayloadError("WNBA Step 10B price must be numeric.")
    if price_format == "american":
        if isinstance(value, float) and not value.is_integer():
            raise WNBAStep10MarketAdapterPayloadError(
                "WNBA Step 10B American prices must be integers."
            )
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise WNBAStep10MarketAdapterPayloadError(
                "WNBA Step 10B American prices must be integers."
            ) from exc
        if abs(result) < 100 or abs(result) > step10a.MAX_AMERICAN_ODDS:
            raise WNBAStep10MarketAdapterPayloadError(
                "WNBA Step 10B American price is outside the Step-10A contract."
            )
        return result

    try:
        decimal = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep10MarketAdapterPayloadError(
            "WNBA Step 10B decimal prices must be numeric."
        ) from exc
    if not math.isfinite(decimal) or not 1.001 <= decimal <= MAX_DECIMAL_ODDS:
        raise WNBAStep10MarketAdapterPayloadError(
            f"WNBA Step 10B decimal prices must be from 1.001 through {MAX_DECIMAL_ODDS:g}."
        )
    if decimal >= 2.0:
        american = int(round((decimal - 1.0) * 100.0))
    else:
        american = int(round(-100.0 / (decimal - 1.0)))
    if abs(american) < 100 or abs(american) > step10a.MAX_AMERICAN_ODDS:
        raise WNBAStep10MarketAdapterPayloadError(
            "WNBA Step 10B decimal price converts outside the Step-10A American-odds contract."
        )
    return american


def _flat_records(payload: Mapping[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    _strict_keys(payload, allowed={"provider", "price_format", "records"}, label="flat payload")
    provider = _clean_provider(payload["provider"])
    price_format = _price_format(payload["price_format"])
    rows = payload["records"]
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence) or not rows:
        raise WNBAStep10MarketAdapterPayloadError(
            "WNBA Step 10B flat payload records must be a nonempty sequence."
        )
    allowed = {
        "game_id", "player_id", "player_name", "sportsbook", "stat", "line",
        "over_price", "under_price", "market_captured_at",
    }
    adapted: list[dict[str, Any]] = []
    for row in rows:
        _strict_keys(row, allowed=allowed, label="flat record")
        adapted.append({
            "game_id": row["game_id"],
            "player_id": row["player_id"],
            "player_name": row["player_name"],
            "sportsbook": row["sportsbook"],
            "stat": row["stat"],
            "line": row["line"],
            "over_odds": _american_from_price(row["over_price"], price_format=price_format),
            "under_odds": _american_from_price(row["under_price"], price_format=price_format),
            "market_captured_at_utc": row["market_captured_at"],
        })
    return provider, price_format, adapted


def _outcomes_records(payload: Mapping[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    _strict_keys(payload, allowed={"provider", "price_format", "markets"}, label="outcomes payload")
    provider = _clean_provider(payload["provider"])
    price_format = _price_format(payload["price_format"])
    markets = payload["markets"]
    if isinstance(markets, (str, bytes)) or not isinstance(markets, Sequence) or not markets:
        raise WNBAStep10MarketAdapterPayloadError(
            "WNBA Step 10B outcomes payload markets must be a nonempty sequence."
        )
    market_allowed = {
        "game_id", "player_id", "player_name", "sportsbook", "stat",
        "market_captured_at", "outcomes",
    }
    outcome_allowed = {"side", "price", "line"}
    adapted: list[dict[str, Any]] = []
    for market in markets:
        _strict_keys(market, allowed=market_allowed, label="outcomes market")
        outcomes = market["outcomes"]
        if isinstance(outcomes, (str, bytes)) or not isinstance(outcomes, Sequence) or len(outcomes) != 2:
            raise WNBAStep10MarketAdapterPayloadError(
                "WNBA Step 10B outcomes markets require exactly two outcomes: Over and Under."
            )
        by_side: dict[str, Mapping[str, Any]] = {}
        for outcome in outcomes:
            _strict_keys(outcome, allowed=outcome_allowed, label="outcome")
            side = str(outcome["side"] or "").strip().casefold()
            if side not in {"over", "under"} or side in by_side:
                raise WNBAStep10MarketAdapterPayloadError(
                    "WNBA Step 10B outcomes require exactly one Over and one Under side."
                )
            by_side[side] = outcome
        if set(by_side) != {"over", "under"}:
            raise WNBAStep10MarketAdapterPayloadError(
                "WNBA Step 10B outcomes require exactly one Over and one Under side."
            )
        try:
            over_line = float(by_side["over"]["line"])
            under_line = float(by_side["under"]["line"])
        except (TypeError, ValueError) as exc:
            raise WNBAStep10MarketAdapterPayloadError(
                "WNBA Step 10B outcome lines must be numeric."
            ) from exc
        if not math.isfinite(over_line) or not math.isfinite(under_line) or over_line != under_line:
            raise WNBAStep10MarketAdapterPayloadError(
                "WNBA Step 10B refuses mixed Over/Under lines in one two-way market."
            )
        adapted.append({
            "game_id": market["game_id"],
            "player_id": market["player_id"],
            "player_name": market["player_name"],
            "sportsbook": market["sportsbook"],
            "stat": market["stat"],
            "line": over_line,
            "over_odds": _american_from_price(by_side["over"]["price"], price_format=price_format),
            "under_odds": _american_from_price(by_side["under"]["price"], price_format=price_format),
            "market_captured_at_utc": market["market_captured_at"],
        })
    return provider, price_format, adapted


def adapt_step10b_market_payload(
    adapter_type: str,
    payload: Mapping[str, Any],
    *,
    evaluated_at: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Adapt one caller-supplied provider payload through the frozen Step-10A contract."""
    _assert_safe_environment(env)
    adapter = str(adapter_type or "").strip().casefold()
    if adapter not in SUPPORTED_ADAPTERS:
        raise WNBAStep10MarketAdapterPayloadError(
            "Unsupported WNBA Step 10B adapter. Supported adapters: "
            + ", ".join(SUPPORTED_ADAPTERS)
            + "."
        )
    if adapter == ADAPTER_FLAT_TWO_WAY_V1:
        provider, price_format, adapted = _flat_records(payload)
    else:
        provider, price_format, adapted = _outcomes_records(payload)

    # Step 10B is forbidden from bypassing Step 10A. All adapter output is run through
    # the exact frozen validator/normalizer before it can leave this boundary.
    step10a_snapshot = step10a.build_step10a_live_market_input_snapshot(
        adapted,
        evaluated_at=evaluated_at,
        env=env,
    )
    if step10a_snapshot.get("schema_version") != step10a.SCHEMA_VERSION:
        raise RuntimeError("Step 10B received unexpected Step-10A schema drift.")

    result = {
        "data_type": "wnba_sportsbook_market_adapter_snapshot",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "adapter": {
            "adapter_type": adapter,
            "provider": provider,
            "input_price_format": price_format,
            "input_record_count": len(adapted),
            "output_record_count": step10a_snapshot["snapshot"]["record_count"],
        },
        "step10a_snapshot": step10a_snapshot,
        "lineage": {
            "step10a_release_id": step10a.RELEASE_ID,
            "step10a_model_version": step10a.MODEL_VERSION,
            "step10a_schema_version": step10a.SCHEMA_VERSION,
            "step10a_frozen_head_sha": STEP10A_FROZEN_HEAD_SHA,
            "step10a_snapshot_content_sha256": step10a_snapshot["snapshot_content_sha256"],
        },
        "contract": {
            "raw_provider_payload_source": "caller_supplied_only",
            "provider_network_fetch_allowed": False,
            "adapter_output_must_pass_frozen_step10a": True,
            "two_way_market_only": True,
            "over_under_lines_must_match_within_market": True,
            "supported_input_price_formats": list(SUPPORTED_PRICE_FORMATS),
            "step10c_owns_cross_snapshot_reconciliation": True,
        },
        "guardrails": {
            "raw_provider_payload_consumed": True,
            "sportsbook_adapter_applied": True,
            "sportsbook_network_fetch_performed": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9_called": False,
            "vig_removed": False,
            "edge_calculated": False,
            "expected_value_calculated": False,
            "cross_sportsbook_consensus_calculated": False,
            "line_movement_calculated": False,
            "cross_prop_ranking_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    hash_surface = {
        "data_type": result["data_type"],
        "schema_version": result["schema_version"],
        "source": result["source"],
        "model_version": result["model_version"],
        "release_id": result["release_id"],
        "adapter": result["adapter"],
        "lineage": result["lineage"],
        "contract": result["contract"],
        "guardrails": result["guardrails"],
    }
    result["adapter_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return result
