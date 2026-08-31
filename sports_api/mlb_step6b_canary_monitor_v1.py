"""Read-only Step 6B monitoring contracts for the active MLB Step 6A canary.

Step 6B does not change rollout behavior. It evaluates repeated live observations
of the already-certified Step 6A 10% production canary and fails closed when core
safety invariants drift: exact official-game identity, deterministic cohort
assignment, gate partitioning, rollback behavior, feed freshness, or protected
impact flags.

The monitor is intentionally side-effect free: no model writes, no database
persistence, no wagering, and no WNBA behavior changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import math
from typing import Any, Iterable, Mapping, Sequence

DATA_TYPE = "mlb_step6b_canary_monitor_window_v1"
SCHEMA_VERSION = 1
TARGET_CANARY_PERCENT = 10.0
MAX_CANARY_PERCENT = 10.0
MIN_MONITOR_CYCLES = 4
MAX_FEED_AGE_SECONDS = 300.0


class MLBStep6BCanaryMonitorError(ValueError):
    pass


def _positive_ids(values: Iterable[object], *, label: str) -> tuple[int, ...]:
    try:
        items = list(values)
    except Exception as exc:
        raise MLBStep6BCanaryMonitorError(f"{label} must be iterable") from exc
    out: list[int] = []
    for raw in items:
        if isinstance(raw, bool):
            raise MLBStep6BCanaryMonitorError(f"{label} contains boolean id")
        try:
            value = int(raw)
        except Exception as exc:
            raise MLBStep6BCanaryMonitorError(f"{label} contains invalid id") from exc
        if value <= 0:
            raise MLBStep6BCanaryMonitorError(f"{label} contains non-positive id")
        out.append(value)
    return tuple(sorted(set(out)))


def _nonnegative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise MLBStep6BCanaryMonitorError(f"{label} must be an integer")
    try:
        parsed = int(value)
    except Exception as exc:
        raise MLBStep6BCanaryMonitorError(f"{label} must be an integer") from exc
    if parsed < 0:
        raise MLBStep6BCanaryMonitorError(f"{label} must be non-negative")
    return parsed


def _utc(value: object, *, label: str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            raise MLBStep6BCanaryMonitorError(f"{label} is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except Exception as exc:
            raise MLBStep6BCanaryMonitorError(f"{label} must be ISO-8601") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_canary_cycle_observation(
    *,
    cycle_index: int,
    observed_at_utc: object,
    collected_at_utc: object,
    http_status: int,
    source: str,
    official_game_ids: Iterable[object],
    selected_game_ids: Iterable[object],
    attached_count: int,
    derived_context_count: int,
    fallback_matching_used: bool,
    total_checks: int,
    enrolled_checks: int,
    allow_count: int,
    block_count: int,
    nonenrolled_passthrough: int,
    rollback_passthrough: int,
    line_bearing_checks: int,
    rollout_enabled: bool,
    rollout_percent: float,
    protected_impacts_clear: bool = True,
) -> dict[str, Any]:
    """Build one normalized monitor-cycle observation with hard invariants."""
    idx = _nonnegative_int(cycle_index, label="cycle_index")
    observed = _utc(observed_at_utc, label="observed_at_utc")
    collected = _utc(collected_at_utc, label="collected_at_utc")
    games = _positive_ids(official_game_ids, label="official_game_ids")
    selected = _positive_ids(selected_game_ids, label="selected_game_ids")
    selected_set = set(selected)
    game_set = set(games)
    if not selected_set.issubset(game_set):
        raise MLBStep6BCanaryMonitorError("selected_game_ids must be a subset of official_game_ids")

    counts = {
        "attached_count": _nonnegative_int(attached_count, label="attached_count"),
        "derived_context_count": _nonnegative_int(derived_context_count, label="derived_context_count"),
        "total_checks": _nonnegative_int(total_checks, label="total_checks"),
        "enrolled_checks": _nonnegative_int(enrolled_checks, label="enrolled_checks"),
        "allow_count": _nonnegative_int(allow_count, label="allow_count"),
        "block_count": _nonnegative_int(block_count, label="block_count"),
        "nonenrolled_passthrough": _nonnegative_int(nonenrolled_passthrough, label="nonenrolled_passthrough"),
        "rollback_passthrough": _nonnegative_int(rollback_passthrough, label="rollback_passthrough"),
        "line_bearing_checks": _nonnegative_int(line_bearing_checks, label="line_bearing_checks"),
    }

    if not isinstance(fallback_matching_used, bool):
        raise MLBStep6BCanaryMonitorError("fallback_matching_used must be boolean")
    if not isinstance(rollout_enabled, bool):
        raise MLBStep6BCanaryMonitorError("rollout_enabled must be boolean")
    if not isinstance(protected_impacts_clear, bool):
        raise MLBStep6BCanaryMonitorError("protected_impacts_clear must be boolean")

    try:
        percent = float(rollout_percent)
    except Exception as exc:
        raise MLBStep6BCanaryMonitorError("rollout_percent must be numeric") from exc
    if not math.isfinite(percent) or percent < 0:
        raise MLBStep6BCanaryMonitorError("rollout_percent must be finite and non-negative")

    game_count = len(games)
    selected_count = len(selected)
    realized_percent = (selected_count / game_count * 100.0) if game_count else 0.0
    expected_selected_count = int(math.floor(game_count * TARGET_CANARY_PERCENT / 100.0))
    expected_checks = game_count * 6
    expected_line_bearing = game_count * 4
    feed_age_seconds = max(0.0, (observed - collected).total_seconds())

    violations: list[str] = []
    warnings: list[str] = []
    if int(http_status) != 200:
        violations.append("PRODUCTION_HTTP_NOT_200")
    if str(source) != "FanDuel":
        violations.append("PRODUCTION_SOURCE_NOT_FANDUEL")
    if game_count <= 0:
        violations.append("EMPTY_CURRENT_SLATE")
    if counts["attached_count"] != game_count:
        violations.append("EXACT_ID_ATTACH_COUNT_MISMATCH")
    if counts["derived_context_count"] != game_count:
        violations.append("PROBABILITY_CONTEXT_COUNT_MISMATCH")
    if fallback_matching_used:
        violations.append("FALLBACK_MATCHING_USED")
    if rollout_enabled is not True:
        violations.append("STEP6A_CANARY_NOT_ENABLED")
    if abs(percent - TARGET_CANARY_PERCENT) > 1e-12:
        violations.append("STEP6A_PERCENT_NOT_10")
    if selected_count != expected_selected_count:
        violations.append("CANARY_COHORT_SIZE_MISMATCH")
    if realized_percent > MAX_CANARY_PERCENT + 1e-12:
        violations.append("CANARY_REALIZED_PERCENT_EXCEEDS_CAP")
    if counts["total_checks"] != expected_checks:
        violations.append("LIVE_CHECK_COVERAGE_MISMATCH")
    if counts["enrolled_checks"] != selected_count * 6:
        violations.append("ENROLLED_CHECK_COVERAGE_MISMATCH")
    if counts["allow_count"] + counts["block_count"] != counts["enrolled_checks"]:
        violations.append("ENROLLED_GATE_PARTITION_MISMATCH")
    if counts["nonenrolled_passthrough"] + counts["enrolled_checks"] != counts["total_checks"]:
        violations.append("CANARY_PARTITION_MISMATCH")
    if counts["rollback_passthrough"] != counts["total_checks"]:
        violations.append("ROLLBACK_PASSTHROUGH_MISMATCH")
    if counts["line_bearing_checks"] != expected_line_bearing:
        violations.append("LINE_BEARING_COVERAGE_MISMATCH")
    if feed_age_seconds > MAX_FEED_AGE_SECONDS:
        violations.append("FEED_STALE")
    elif feed_age_seconds > MAX_FEED_AGE_SECONDS * 0.75:
        warnings.append("FEED_AGE_APPROACHING_LIMIT")
    if protected_impacts_clear is not True:
        violations.append("PROTECTED_IMPACT_DRIFT")

    snapshot_key = sha256(
        (collected.isoformat() + "|" + ",".join(map(str, games))).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "data_type": "mlb_step6b_canary_monitor_cycle_v1",
        "schema_version": SCHEMA_VERSION,
        "cycle_index": idx,
        "observed_at_utc": observed.isoformat(),
        "collected_at_utc": collected.isoformat(),
        "snapshot_key": snapshot_key,
        "http_status": int(http_status),
        "source": str(source),
        "official_game_ids": list(games),
        "game_count": game_count,
        "selected_game_ids": list(selected),
        "selected_game_count": selected_count,
        "expected_selected_game_count": expected_selected_count,
        "realized_percent": realized_percent,
        "rollout_enabled": rollout_enabled,
        "rollout_percent": percent,
        "feed_age_seconds": feed_age_seconds,
        **counts,
        "fallback_matching_used": fallback_matching_used,
        "protected_impacts_clear": protected_impacts_clear,
        "violations": violations,
        "warnings": warnings,
        "cycle_green": not violations,
        "read_only_monitor": True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
    }


def evaluate_canary_monitor_window(
    cycles: Sequence[Mapping[str, Any]],
    *,
    min_cycles: int = MIN_MONITOR_CYCLES,
) -> dict[str, Any]:
    """Evaluate repeated cycles and enforce deterministic same-slate cohorts."""
    if isinstance(cycles, (str, bytes)):
        raise MLBStep6BCanaryMonitorError("cycles must be a sequence of mappings")
    rows = [dict(row) for row in cycles]
    minimum = _nonnegative_int(min_cycles, label="min_cycles")
    if minimum <= 0:
        raise MLBStep6BCanaryMonitorError("min_cycles must be positive")

    violations: list[str] = []
    warnings: list[str] = []
    if len(rows) < minimum:
        violations.append("INSUFFICIENT_MONITOR_CYCLES")

    same_slate_cohorts: dict[tuple[int, ...], tuple[int, ...]] = {}
    distinct_snapshots: set[str] = set()
    max_feed_age = 0.0
    total_allow = total_block = total_enrolled = total_rollback = 0
    stale_cycle_count = 0

    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            violations.append(f"CYCLE_{index}_NOT_MAPPING")
            continue
        for item in row.get("violations") or []:
            violations.append(f"CYCLE_{index}:{item}")
        for item in row.get("warnings") or []:
            warnings.append(f"CYCLE_{index}:{item}")

        games = tuple(int(v) for v in (row.get("official_game_ids") or []))
        selected = tuple(int(v) for v in (row.get("selected_game_ids") or []))
        if games in same_slate_cohorts and same_slate_cohorts[games] != selected:
            violations.append(f"CYCLE_{index}:SAME_SLATE_COHORT_CHANGED")
        else:
            same_slate_cohorts[games] = selected

        snapshot = str(row.get("snapshot_key") or "")
        if snapshot:
            distinct_snapshots.add(snapshot)
        age = float(row.get("feed_age_seconds") or 0.0)
        max_feed_age = max(max_feed_age, age)
        if age > MAX_FEED_AGE_SECONDS:
            stale_cycle_count += 1
        total_allow += int(row.get("allow_count") or 0)
        total_block += int(row.get("block_count") or 0)
        total_enrolled += int(row.get("enrolled_checks") or 0)
        total_rollback += int(row.get("rollback_passthrough") or 0)

    if rows and len(distinct_snapshots) < 2:
        warnings.append("NO_SNAPSHOT_ADVANCE_OBSERVED_IN_WINDOW")

    # Deduplicate while preserving first-seen order for readable CI evidence.
    violations = list(dict.fromkeys(violations))
    warnings = list(dict.fromkeys(warnings))

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "monitor_result": "GREEN" if not violations else "RED",
        "cycle_count": len(rows),
        "minimum_cycle_count": minimum,
        "distinct_snapshot_count": len(distinct_snapshots),
        "distinct_slate_count": len(same_slate_cohorts),
        "max_feed_age_seconds": max_feed_age,
        "stale_cycle_count": stale_cycle_count,
        "total_enrolled_checks": total_enrolled,
        "total_allow_count": total_allow,
        "total_block_count": total_block,
        "total_rollback_passthrough": total_rollback,
        "same_slate_cohort_deterministic": not any("SAME_SLATE_COHORT_CHANGED" in v for v in violations),
        "violations": violations,
        "warnings": warnings,
        "read_only_monitor": True,
        "scheduled_monitor_safe": True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "TARGET_CANARY_PERCENT",
    "MAX_CANARY_PERCENT",
    "MIN_MONITOR_CYCLES",
    "MAX_FEED_AGE_SECONDS",
    "MLBStep6BCanaryMonitorError",
    "build_canary_cycle_observation",
    "evaluate_canary_monitor_window",
]
