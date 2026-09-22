"""Step 10C: reconcile frozen Step-10B WNBA market adapter snapshots.

This layer validates content-addressed Step-10B outputs, reconciles repeated quote
updates, excludes stale or unsynchronized quotes, reports market coverage/missing
books, and optionally compares against one prior Step-10C snapshot for line/price
movement metadata. It performs no provider network fetches, model calculations,
vig removal, edge/EV math, Step-9 calls, persistence, scheduling, or production work.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from typing import Any, Mapping, Sequence

from sports_api import wnba_step10_live_market_input as step10a
from sports_api import wnba_step10_market_adapters as step10b

SOURCE = "Kyre Sports API WNBA Step 10C reconciled live market snapshot"
SCHEMA_VERSION = "wnba_step_10c_market_snapshot_v1"
MODEL_VERSION = "wnba_step10c_reconciled_fresh_market_snapshot_2026_regular_v1"
RELEASE_ID = "wnba_step10c_market_snapshot_2026_regular_season_v1"
STEP10C_MARKET_SNAPSHOT_ENABLED_ENV = "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED"
STEP10B_FROZEN_HEAD_SHA = "1088358452ca2bc9e45a2bb3544b44331606d88c"

DEFAULT_MAX_QUOTE_AGE_SECONDS = 600
DEFAULT_MAX_MARKET_SYNC_SECONDS = 120
DEFAULT_MAX_BOARD_SYNC_SECONDS = 300
MAX_ADAPTER_SNAPSHOTS = 100
MAX_EXPECTED_SPORTSBOOKS = 100

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep10MarketSnapshotDisabledError(RuntimeError):
    """Raised when Step 10C is not isolated behind its certification gates."""


class WNBAStep10MarketSnapshotIntegrityError(ValueError):
    """Raised when an upstream Step-10B/10A or prior Step-10C hash fails."""


class WNBAStep10MarketSnapshotConflictError(ValueError):
    """Raised when equally-timed provider records disagree for one quote identity."""


class WNBAStep10MarketSnapshotNotReadyError(RuntimeError):
    """Raised when no usable or board-synchronized market snapshot can be formed."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step10c_market_snapshot_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP10C_MARKET_SNAPSHOT_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep10MarketSnapshotDisabledError(
            "Step 10C refuses to run while production switches are enabled: "
            + ", ".join(bad)
        )
    if not _truthy(source.get(STEP10C_MARKET_SNAPSHOT_ENABLED_ENV)):
        raise WNBAStep10MarketSnapshotDisabledError(
            f"Step 10C requires {STEP10C_MARKET_SNAPSHOT_ENABLED_ENV}=true."
        )
    if not step10b.step10b_market_adapter_enabled(source):
        raise WNBAStep10MarketSnapshotDisabledError(
            "Step 10C requires the frozen Step-10B adapter gate to be explicitly enabled."
        )
    if not step10a.step10a_live_market_input_enabled(source):
        raise WNBAStep10MarketSnapshotDisabledError(
            "Step 10C requires the frozen Step-10A input gate to be explicitly enabled."
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


def _parse_timestamp(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"WNBA {label} is required.")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"WNBA {label} must be ISO-8601 with timezone.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"WNBA {label} must include a timezone offset.")
    return parsed.astimezone(timezone.utc)


def _evaluation_time(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("WNBA evaluated_at must be timezone-aware.")
    return result.astimezone(timezone.utc)


def _positive_seconds(value: Any, label: str, *, maximum: float = 86_400.0) -> float:
    if isinstance(value, bool):
        raise ValueError(f"WNBA {label} must be a positive number of seconds.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"WNBA {label} must be a positive number of seconds.") from exc
    if not math.isfinite(result) or not 0.0 < result <= maximum:
        raise ValueError(f"WNBA {label} must be greater than 0 and at most {maximum:g}.")
    return result


def _step10a_hash_surface(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for record in snapshot.get("records", []):
        row = dict(record)
        row.pop("market_age_seconds_at_evaluation", None)
        records.append(row)
    snap = dict(snapshot.get("snapshot", {}))
    snap.pop("future_clock_tolerance_seconds", None)
    return {
        "data_type": snapshot.get("data_type"),
        "schema_version": snapshot.get("schema_version"),
        "source": snapshot.get("source"),
        "model_version": snapshot.get("model_version"),
        "release_id": snapshot.get("release_id"),
        "snapshot": snap,
        "records": records,
        "lineage": snapshot.get("lineage"),
        "contract": snapshot.get("contract"),
        "guardrails": snapshot.get("guardrails"),
    }


def _verify_step10a_snapshot(snapshot: Mapping[str, Any]) -> None:
    if not isinstance(snapshot, Mapping):
        raise WNBAStep10MarketSnapshotIntegrityError("Step 10C requires a Step-10A snapshot object.")
    if snapshot.get("data_type") != "wnba_live_player_prop_market_input_snapshot":
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected Step-10A data_type.")
    if snapshot.get("schema_version") != step10a.SCHEMA_VERSION:
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected Step-10A schema version.")
    if snapshot.get("model_version") != step10a.MODEL_VERSION:
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected Step-10A model version.")
    if snapshot.get("release_id") != step10a.RELEASE_ID:
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected Step-10A release ID.")
    expected = _canonical_hash(_step10a_hash_surface(snapshot))
    if snapshot.get("snapshot_content_sha256") != expected:
        raise WNBAStep10MarketSnapshotIntegrityError("Step-10A snapshot content hash mismatch.")
    records = snapshot.get("records")
    if not isinstance(records, list) or not records:
        raise WNBAStep10MarketSnapshotIntegrityError("Step-10A snapshot contains no records.")
    if snapshot.get("snapshot", {}).get("record_count") != len(records):
        raise WNBAStep10MarketSnapshotIntegrityError("Step-10A record count does not match records.")


def _step10b_hash_surface(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "data_type": snapshot.get("data_type"),
        "schema_version": snapshot.get("schema_version"),
        "source": snapshot.get("source"),
        "model_version": snapshot.get("model_version"),
        "release_id": snapshot.get("release_id"),
        "adapter": snapshot.get("adapter"),
        "lineage": snapshot.get("lineage"),
        "contract": snapshot.get("contract"),
        "guardrails": snapshot.get("guardrails"),
    }


def _verify_step10b_snapshot(snapshot: Mapping[str, Any]) -> None:
    if not isinstance(snapshot, Mapping):
        raise WNBAStep10MarketSnapshotIntegrityError("Step 10C adapter snapshots must be objects.")
    if snapshot.get("data_type") != "wnba_sportsbook_market_adapter_snapshot":
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected Step-10B data_type.")
    if snapshot.get("schema_version") != step10b.SCHEMA_VERSION:
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected Step-10B schema version.")
    if snapshot.get("model_version") != step10b.MODEL_VERSION:
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected Step-10B model version.")
    if snapshot.get("release_id") != step10b.RELEASE_ID:
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected Step-10B release ID.")
    expected = _canonical_hash(_step10b_hash_surface(snapshot))
    if snapshot.get("adapter_content_sha256") != expected:
        raise WNBAStep10MarketSnapshotIntegrityError("Step-10B adapter content hash mismatch.")
    lineage = snapshot.get("lineage", {})
    if lineage.get("step10a_frozen_head_sha") != step10b.STEP10A_FROZEN_HEAD_SHA:
        raise WNBAStep10MarketSnapshotIntegrityError("Step-10B frozen Step-10A lineage drift.")
    nested = snapshot.get("step10a_snapshot")
    _verify_step10a_snapshot(nested)
    if lineage.get("step10a_snapshot_content_sha256") != nested.get("snapshot_content_sha256"):
        raise WNBAStep10MarketSnapshotIntegrityError("Step-10B lineage does not bind its Step-10A snapshot.")
    adapter = snapshot.get("adapter", {})
    if adapter.get("adapter_type") not in step10b.SUPPORTED_ADAPTERS:
        raise WNBAStep10MarketSnapshotIntegrityError("Step-10B adapter type is not certified.")
    if adapter.get("output_record_count") != len(nested.get("records", [])):
        raise WNBAStep10MarketSnapshotIntegrityError("Step-10B output count does not match Step-10A records.")
    guardrails = snapshot.get("guardrails", {})
    for key in (
        "sportsbook_network_fetch_performed", "basketball_projection_changed",
        "step8_distribution_changed", "step9_called", "vig_removed", "edge_calculated",
        "expected_value_calculated", "cross_sportsbook_consensus_calculated",
        "cross_prop_ranking_calculated", "supabase_mutated", "persistence_mutated",
        "scheduler_started", "production_runtime_enabled", "production_activation_allowed",
    ):
        if guardrails.get(key) is not False:
            raise WNBAStep10MarketSnapshotIntegrityError(f"Unsafe Step-10B guardrail drift: {key}.")


def _quote_identity(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(record["game_id"]), int(record["player_id"]), str(record["stat"]),
        str(record["sportsbook"]).casefold(), float(record["line"]),
    )


def _market_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (str(record["game_id"]), int(record["player_id"]), str(record["stat"]), float(record["line"]))


def _family_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (str(record["game_id"]), int(record["player_id"]), str(record["stat"]))


def _book_family_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(record["game_id"]), int(record["player_id"]), str(record["stat"]),
        str(record["sportsbook"]).casefold(),
    )


def _strip_step10a_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "game_id": record["game_id"],
        "player_id": record["player_id"],
        "player_name": record["player_name"],
        "sportsbook": record["sportsbook"],
        "stat": record["stat"],
        "line": record["line"],
        "over_odds": record["over_odds"],
        "under_odds": record["under_odds"],
        "market_captured_at_utc": record["market_captured_at_utc"],
    }


def _normalize_expected_books(values: Sequence[str] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError("WNBA expected_sportsbooks must be a sequence of sportsbook names.")
    if len(values) > MAX_EXPECTED_SPORTSBOOKS:
        raise ValueError(f"WNBA expected_sportsbooks cannot exceed {MAX_EXPECTED_SPORTSBOOKS} entries.")
    by_fold: dict[str, str] = {}
    for value in values:
        text = " ".join(str(value or "").strip().split())
        if not text or len(text) > 80:
            raise ValueError("WNBA expected sportsbook names must contain 1 through 80 characters.")
        folded = text.casefold()
        if folded in by_fold:
            raise ValueError("WNBA expected_sportsbooks contains a duplicate sportsbook name.")
        by_fold[folded] = text
    return sorted(by_fold.values(), key=str.casefold)


def _reconcile_updates(flattened: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in flattened:
        grouped[_quote_identity(row)].append(row)

    reconciled: list[dict[str, Any]] = []
    for identity, rows in grouped.items():
        rows = sorted(
            rows,
            key=lambda row: (
                _parse_timestamp(row["market_captured_at_utc"], "market_captured_at_utc"),
                str(row["source_provider"]).casefold(),
                str(row["source_adapter_content_sha256"]),
            ),
        )
        latest_time = _parse_timestamp(rows[-1]["market_captured_at_utc"], "market_captured_at_utc")
        latest_rows = [
            row for row in rows
            if _parse_timestamp(row["market_captured_at_utc"], "market_captured_at_utc") == latest_time
        ]
        outcome_signatures = {
            (int(row["over_odds"]), int(row["under_odds"]), str(row["quote_id"]))
            for row in latest_rows
        }
        if len(outcome_signatures) != 1:
            raise WNBAStep10MarketSnapshotConflictError(
                "Step 10C found conflicting equally-timed updates for quote identity "
                f"{identity}."
            )
        chosen = dict(latest_rows[0])
        source_hashes = sorted({str(row["source_adapter_content_sha256"]) for row in latest_rows})
        source_providers = sorted({str(row["source_provider"]) for row in latest_rows}, key=str.casefold)
        older = [row for row in rows if row not in latest_rows]
        chosen["source_adapter_content_sha256"] = source_hashes[0]
        chosen["source_adapter_content_sha256_all"] = source_hashes
        chosen["source_providers"] = source_providers
        chosen["superseded_update_count"] = len(older)
        if older:
            chosen["earliest_seen_capture_utc"] = min(
                _parse_timestamp(row["market_captured_at_utc"], "market_captured_at_utc") for row in rows
            ).isoformat()
        else:
            chosen["earliest_seen_capture_utc"] = chosen["market_captured_at_utc"]
        reconciled.append(chosen)

    reconciled.sort(
        key=lambda row: (
            row["game_id"], int(row["player_id"]), row["stat"], float(row["line"]),
            str(row["sportsbook"]).casefold(), row["market_captured_at_utc"],
        )
    )
    return reconciled


def _previous_hash_surface(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in snapshot.items()
        if key not in {"generated_at_utc", "snapshot_content_sha256"}
    }


def _verify_previous_snapshot(snapshot: Mapping[str, Any]) -> None:
    if not isinstance(snapshot, Mapping):
        raise WNBAStep10MarketSnapshotIntegrityError("Previous Step-10C snapshot must be an object.")
    if snapshot.get("data_type") != "wnba_reconciled_live_market_snapshot":
        raise WNBAStep10MarketSnapshotIntegrityError("Unexpected previous Step-10C data_type.")
    if snapshot.get("schema_version") != SCHEMA_VERSION or snapshot.get("model_version") != MODEL_VERSION:
        raise WNBAStep10MarketSnapshotIntegrityError("Previous Step-10C schema/model drift.")
    if snapshot.get("release_id") != RELEASE_ID:
        raise WNBAStep10MarketSnapshotIntegrityError("Previous Step-10C release drift.")
    expected = _canonical_hash(_previous_hash_surface(snapshot))
    if snapshot.get("snapshot_content_sha256") != expected:
        raise WNBAStep10MarketSnapshotIntegrityError("Previous Step-10C snapshot content hash mismatch.")


def _movement_metadata(
    current: Sequence[Mapping[str, Any]],
    previous_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if previous_snapshot is None:
        return {
            "previous_snapshot_supplied": False,
            "exact_line_price_changes": [],
            "unique_line_changes": [],
            "missing_since_previous": [],
        }

    previous = previous_snapshot.get("records", [])
    previous_by_identity = {_quote_identity(row): row for row in previous}
    current_by_identity = {_quote_identity(row): row for row in current}

    price_changes = []
    for identity in sorted(set(previous_by_identity) & set(current_by_identity), key=str):
        old = previous_by_identity[identity]
        new = current_by_identity[identity]
        if int(old["over_odds"]) != int(new["over_odds"]) or int(old["under_odds"]) != int(new["under_odds"]):
            price_changes.append({
                "game_id": new["game_id"],
                "player_id": int(new["player_id"]),
                "stat": new["stat"],
                "sportsbook": new["sportsbook"],
                "line": float(new["line"]),
                "previous_over_odds": int(old["over_odds"]),
                "current_over_odds": int(new["over_odds"]),
                "previous_under_odds": int(old["under_odds"]),
                "current_under_odds": int(new["under_odds"]),
            })

    prev_by_family: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    curr_by_family: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in previous:
        prev_by_family[_book_family_key(row)].append(row)
    for row in current:
        curr_by_family[_book_family_key(row)].append(row)

    line_changes = []
    for key in sorted(set(prev_by_family) & set(curr_by_family), key=str):
        old_rows = prev_by_family[key]
        new_rows = curr_by_family[key]
        old_lines = sorted({float(row["line"]) for row in old_rows})
        new_lines = sorted({float(row["line"]) for row in new_rows})
        if len(old_lines) == 1 and len(new_lines) == 1 and old_lines[0] != new_lines[0]:
            sample = new_rows[0]
            line_changes.append({
                "game_id": sample["game_id"],
                "player_id": int(sample["player_id"]),
                "stat": sample["stat"],
                "sportsbook": sample["sportsbook"],
                "previous_line": old_lines[0],
                "current_line": new_lines[0],
                "line_delta": round(new_lines[0] - old_lines[0], 6),
                "alternate_line_ambiguity": False,
            })

    missing = []
    for identity in sorted(set(previous_by_identity) - set(current_by_identity), key=str):
        row = previous_by_identity[identity]
        missing.append({
            "game_id": row["game_id"],
            "player_id": int(row["player_id"]),
            "stat": row["stat"],
            "sportsbook": row["sportsbook"],
            "line": float(row["line"]),
        })
    return {
        "previous_snapshot_supplied": True,
        "previous_snapshot_content_sha256": previous_snapshot["snapshot_content_sha256"],
        "exact_line_price_changes": price_changes,
        "unique_line_changes": line_changes,
        "missing_since_previous": missing,
    }


def build_step10c_market_snapshot(
    adapter_snapshots: Sequence[Mapping[str, Any]],
    *,
    evaluated_at: datetime | None = None,
    previous_snapshot: Mapping[str, Any] | None = None,
    expected_sportsbooks: Sequence[str] | None = None,
    max_quote_age_seconds: float = DEFAULT_MAX_QUOTE_AGE_SECONDS,
    max_market_sync_seconds: float = DEFAULT_MAX_MARKET_SYNC_SECONDS,
    max_board_sync_seconds: float = DEFAULT_MAX_BOARD_SYNC_SECONDS,
    require_board_synchronized: bool = True,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build one current, content-addressed market snapshot from Step-10B outputs."""
    _assert_safe_environment(env)
    if isinstance(adapter_snapshots, (str, bytes)) or not isinstance(adapter_snapshots, Sequence):
        raise ValueError("WNBA Step 10C adapter_snapshots must be a sequence.")
    if not 1 <= len(adapter_snapshots) <= MAX_ADAPTER_SNAPSHOTS:
        raise ValueError(f"WNBA Step 10C requires 1 through {MAX_ADAPTER_SNAPSHOTS} adapter snapshots.")
    if not isinstance(require_board_synchronized, bool):
        raise ValueError("WNBA require_board_synchronized must be boolean.")

    quote_age_limit = _positive_seconds(max_quote_age_seconds, "max_quote_age_seconds")
    market_sync_limit = _positive_seconds(max_market_sync_seconds, "max_market_sync_seconds")
    board_sync_limit = _positive_seconds(max_board_sync_seconds, "max_board_sync_seconds")
    evaluated = _evaluation_time(evaluated_at)
    expected_books = _normalize_expected_books(expected_sportsbooks)

    if previous_snapshot is not None:
        _verify_previous_snapshot(previous_snapshot)

    flattened: list[dict[str, Any]] = []
    adapter_lineage = []
    for snapshot in adapter_snapshots:
        _verify_step10b_snapshot(snapshot)
        adapter_hash = str(snapshot["adapter_content_sha256"])
        provider = str(snapshot["adapter"]["provider"])
        adapter_lineage.append({
            "provider": provider,
            "adapter_type": snapshot["adapter"]["adapter_type"],
            "adapter_content_sha256": adapter_hash,
            "step10a_snapshot_content_sha256": snapshot["step10a_snapshot"]["snapshot_content_sha256"],
        })
        for record in snapshot["step10a_snapshot"]["records"]:
            row = dict(record)
            row["source_provider"] = provider
            row["source_adapter_content_sha256"] = adapter_hash
            flattened.append(row)

    reconciled = _reconcile_updates(flattened)

    stale_ids: set[tuple[Any, ...]] = set()
    ages: dict[tuple[Any, ...], float] = {}
    for row in reconciled:
        captured = _parse_timestamp(row["market_captured_at_utc"], "market_captured_at_utc")
        delta = (evaluated - captured).total_seconds()
        if delta < -step10a.MARKET_FUTURE_TOLERANCE_SECONDS:
            raise ValueError("WNBA Step 10C found a quote too far in the future.")
        age = max(0.0, delta)
        identity = _quote_identity(row)
        ages[identity] = age
        if age > quote_age_limit:
            stale_ids.add(identity)

    fresh = [row for row in reconciled if _quote_identity(row) not in stale_ids]
    if not fresh:
        raise WNBAStep10MarketSnapshotNotReadyError("Step 10C has no fresh quotes after reconciliation.")

    fresh_by_market: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in fresh:
        fresh_by_market[_market_key(row)].append(row)

    out_of_sync_ids: set[tuple[Any, ...]] = set()
    market_sync: dict[tuple[Any, ...], dict[str, Any]] = {}
    for key, rows in fresh_by_market.items():
        captures = [_parse_timestamp(row["market_captured_at_utc"], "market_captured_at_utc") for row in rows]
        latest = max(captures)
        earliest = min(captures)
        spread = (latest - earliest).total_seconds()
        cutoff = latest - timedelta(seconds=market_sync_limit)
        for row in rows:
            captured = _parse_timestamp(row["market_captured_at_utc"], "market_captured_at_utc")
            if captured < cutoff:
                out_of_sync_ids.add(_quote_identity(row))
        market_sync[key] = {
            "capture_spread_seconds_before_exclusion": round(spread, 3),
            "latest_capture_utc": latest.isoformat(),
        }

    eligible = [
        row for row in fresh
        if _quote_identity(row) not in out_of_sync_ids
    ]
    if not eligible:
        raise WNBAStep10MarketSnapshotNotReadyError(
            "Step 10C has no synchronized quotes after market-level reconciliation."
        )

    eligible.sort(
        key=lambda row: (
            row["game_id"], int(row["player_id"]), row["stat"], float(row["line"]),
            str(row["sportsbook"]).casefold(), row["market_captured_at_utc"],
        )
    )
    eligible_captures = [_parse_timestamp(row["market_captured_at_utc"], "market_captured_at_utc") for row in eligible]
    board_earliest, board_latest = min(eligible_captures), max(eligible_captures)
    board_spread = (board_latest - board_earliest).total_seconds()
    board_synchronized = board_spread <= board_sync_limit
    if require_board_synchronized and not board_synchronized:
        raise WNBAStep10MarketSnapshotNotReadyError(
            f"Step 10C board capture spread {board_spread:.3f}s exceeds {board_sync_limit:.3f}s."
        )

    excluded = []
    for row in reconciled:
        identity = _quote_identity(row)
        reason = None
        if identity in stale_ids:
            reason = "stale"
        elif identity in out_of_sync_ids:
            reason = "market_out_of_sync"
        if reason:
            excluded.append({
                **_strip_step10a_record(row),
                "quote_id": row["quote_id"],
                "reason": reason,
                "market_age_seconds_at_evaluation": round(ages[identity], 3),
            })

    # Re-run the eligible current quote set through the exact frozen Step-10A contract.
    # This is a second independent structural check after cross-snapshot reconciliation.
    reconciled_step10a = step10a.build_step10a_live_market_input_snapshot(
        [_strip_step10a_record(row) for row in eligible],
        evaluated_at=evaluated,
        env=env,
    )

    market_groups = []
    eligible_by_market: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        eligible_by_market[_market_key(row)].append(row)
    for key in sorted(eligible_by_market, key=str):
        rows = eligible_by_market[key]
        books = sorted({str(row["sportsbook"]) for row in rows}, key=str.casefold)
        captures = [_parse_timestamp(row["market_captured_at_utc"], "market_captured_at_utc") for row in rows]
        sample = rows[0]
        market_groups.append({
            "game_id": sample["game_id"],
            "player_id": int(sample["player_id"]),
            "player_name": sample["player_name"],
            "stat": sample["stat"],
            "line": float(sample["line"]),
            "sportsbook_count": len(books),
            "sportsbooks": books,
            "capture_spread_seconds": round((max(captures) - min(captures)).total_seconds(), 3),
            "consensus_ready_two_plus_books": len(books) >= 2,
        })

    families = []
    eligible_by_family: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        eligible_by_family[_family_key(row)].append(row)
    expected_by_fold = {book.casefold(): book for book in expected_books}
    for key in sorted(eligible_by_family, key=str):
        rows = eligible_by_family[key]
        sample = rows[0]
        books = sorted({str(row["sportsbook"]) for row in rows}, key=str.casefold)
        book_folds = {book.casefold() for book in books}
        missing_expected = [expected_by_fold[fold] for fold in expected_by_fold if fold not in book_folds]
        families.append({
            "game_id": sample["game_id"],
            "player_id": int(sample["player_id"]),
            "player_name": sample["player_name"],
            "stat": sample["stat"],
            "available_lines": sorted({float(row["line"]) for row in rows}),
            "sportsbook_count": len(books),
            "sportsbooks": books,
            "missing_expected_sportsbooks": sorted(missing_expected, key=str.casefold),
            "has_any_two_book_exact_line": any(
                group["game_id"] == sample["game_id"]
                and group["player_id"] == int(sample["player_id"])
                and group["stat"] == sample["stat"]
                and group["consensus_ready_two_plus_books"]
                for group in market_groups
            ),
        })

    movement = _movement_metadata(eligible, previous_snapshot)
    all_books = sorted({str(row["sportsbook"]) for row in eligible}, key=str.casefold)
    adapter_lineage = sorted(
        adapter_lineage,
        key=lambda row: (str(row["provider"]).casefold(), row["adapter_content_sha256"]),
    )

    records_out = []
    for row in eligible:
        identity = _quote_identity(row)
        records_out.append({
            **_strip_step10a_record(row),
            "quote_id": row["quote_id"],
            "market_age_seconds_at_evaluation": round(ages[identity], 3),
            "source_providers": row["source_providers"],
            "source_adapter_content_sha256_all": row["source_adapter_content_sha256_all"],
            "superseded_update_count": int(row["superseded_update_count"]),
            "earliest_seen_capture_utc": row["earliest_seen_capture_utc"],
        })

    result = {
        "data_type": "wnba_reconciled_live_market_snapshot",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluated_at_utc": evaluated.isoformat(),
        "snapshot": {
            "input_adapter_snapshot_count": len(adapter_snapshots),
            "input_record_count": len(flattened),
            "reconciled_identity_count": len(reconciled),
            "eligible_record_count": len(records_out),
            "excluded_record_count": len(excluded),
            "stale_record_count": len(stale_ids),
            "market_out_of_sync_record_count": len(out_of_sync_ids - stale_ids),
            "unique_sportsbook_count": len(all_books),
            "unique_sportsbooks": all_books,
            "market_group_count": len(market_groups),
            "market_family_count": len(families),
            "board_earliest_capture_utc": board_earliest.isoformat(),
            "board_latest_capture_utc": board_latest.isoformat(),
            "board_capture_spread_seconds": round(board_spread, 3),
            "board_synchronized": board_synchronized,
        },
        "freshness_policy": {
            "max_quote_age_seconds": quote_age_limit,
            "max_market_sync_seconds": market_sync_limit,
            "max_board_sync_seconds": board_sync_limit,
            "require_board_synchronized": require_board_synchronized,
            "future_clock_tolerance_seconds": step10a.MARKET_FUTURE_TOLERANCE_SECONDS,
        },
        "records": records_out,
        "excluded_records": excluded,
        "market_groups": market_groups,
        "market_families": families,
        "movement": movement,
        "reconciled_step10a_snapshot": reconciled_step10a,
        "lineage": {
            "step10b_release_id": step10b.RELEASE_ID,
            "step10b_model_version": step10b.MODEL_VERSION,
            "step10b_schema_version": step10b.SCHEMA_VERSION,
            "step10b_frozen_head_sha": STEP10B_FROZEN_HEAD_SHA,
            "adapter_snapshots": adapter_lineage,
            "reconciled_step10a_snapshot_content_sha256": reconciled_step10a["snapshot_content_sha256"],
        },
        "contract": {
            "latest_update_wins_for_same_book_game_player_stat_exact_line": True,
            "equal_timestamp_conflicts_fail_closed": True,
            "stale_quotes_excluded": True,
            "market_level_synchronization_enforced": True,
            "board_level_synchronization_checked": True,
            "alternative_lines_preserved": True,
            "line_change_reported_only_when_one_line_per_book_family_is_unambiguous": True,
            "missing_expected_sportsbooks_reported_when_supplied": True,
            "step9_consumes_only_reconciled_eligible_quotes_in_later_integration": True,
        },
        "guardrails": {
            "raw_provider_payload_consumed": False,
            "sportsbook_adapter_output_consumed": True,
            "sportsbook_adapter_applied": False,
            "sportsbook_network_fetch_performed": False,
            "market_snapshot_reconciled": True,
            "freshness_evaluated": True,
            "line_movement_calculated": previous_snapshot is not None,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9_called": False,
            "vig_removed": False,
            "edge_calculated": False,
            "expected_value_calculated": False,
            "cross_sportsbook_consensus_calculated": False,
            "cross_prop_ranking_calculated": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    result["snapshot_content_sha256"] = _canonical_hash(_previous_hash_surface(result))
    _assert_safe_environment(env)
    return result
