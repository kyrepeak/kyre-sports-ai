"""CFB Over/Under Step 7A validation and backtesting.

Additive, offline analytics only. This module measures live-shadow model behavior
without modifying projections, market attachment, routing, or wager selection.
Official ESPN event IDs are the only accepted game identity.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping

MODEL_VERSION = "CFB O/U VALIDATION V1 • STEP 7A"
ALLOWED_MARKETS = {"game_total", "over", "under"}


class ValidationError(ValueError):
    """Raised when a validation row violates the Step 7 safety contract."""


def _finite(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"unsafe_non_numeric:{field}") from exc
    if not math.isfinite(number):
        raise ValidationError(f"unsafe_nonfinite:{field}")
    return number


def _probability(value: Any, field: str) -> float:
    number = _finite(value, field)
    if not 0.0 <= number <= 1.0:
        raise ValidationError(f"unsafe_probability:{field}")
    return number


def _validate_row(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    event_id = str(row.get("game_id") or "").strip()
    if not event_id.isdigit():
        raise ValidationError(f"unsafe_non_official_event_id:{index}")
    if row.get("identity_verified") is not True:
        raise ValidationError(f"unsafe_unverified_event_identity:{event_id}")
    if str(row.get("source_mode") or "").strip().casefold() != "live_shadow":
        raise ValidationError(f"unsafe_non_shadow_row:{event_id}")

    market_type = str(row.get("market_type") or "").strip().casefold()
    if market_type not in ALLOWED_MARKETS:
        raise ValidationError(f"unsafe_market_type:{event_id}:{market_type or 'missing'}")

    probability = _probability(row.get("model_probability"), f"model_probability:{event_id}")
    outcome = row.get("outcome")
    if outcome not in (0, 1, False, True):
        raise ValidationError(f"unsafe_outcome:{event_id}")

    signal_edge = _finite(row.get("model_edge_at_signal"), f"model_edge_at_signal:{event_id}")
    closing_edge = _finite(row.get("model_edge_at_close"), f"model_edge_at_close:{event_id}")
    signal_line = _finite(row.get("market_total_at_signal"), f"market_total_at_signal:{event_id}")
    closing_line = _finite(row.get("market_total_at_close"), f"market_total_at_close:{event_id}")

    conference = str(row.get("conference") or "UNKNOWN").strip() or "UNKNOWN"
    return {
        "game_id": event_id,
        "conference": conference,
        "market_type": market_type,
        "model_probability": probability,
        "outcome": int(bool(outcome)),
        "model_edge_at_signal": signal_edge,
        "model_edge_at_close": closing_edge,
        "market_total_at_signal": signal_line,
        "market_total_at_close": closing_line,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"sample_size": 0}
    brier = sum((r["model_probability"] - r["outcome"]) ** 2 for r in rows) / n
    mean_pred = sum(r["model_probability"] for r in rows) / n
    actual_rate = sum(r["outcome"] for r in rows) / n
    mean_clv_points = sum(
        r["market_total_at_close"] - r["market_total_at_signal"] for r in rows
    ) / n
    mean_signal_edge = sum(r["model_edge_at_signal"] for r in rows) / n
    mean_close_edge = sum(r["model_edge_at_close"] for r in rows) / n
    edge_decay = mean_signal_edge - mean_close_edge
    return {
        "sample_size": n,
        "brier_score": brier,
        "mean_predicted_probability": mean_pred,
        "actual_rate": actual_rate,
        "calibration_gap": mean_pred - actual_rate,
        "mean_clv_points": mean_clv_points,
        "mean_signal_edge": mean_signal_edge,
        "mean_closing_edge": mean_close_edge,
        "mean_edge_decay": edge_decay,
    }


def _calibration_bins(rows: list[dict[str, Any]], bin_width: float = 0.1) -> list[dict[str, Any]]:
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        idx = min(int(row["model_probability"] / bin_width), int(1.0 / bin_width) - 1)
        buckets[idx].append(row)
    result = []
    for idx in sorted(buckets):
        group = buckets[idx]
        lo = idx * bin_width
        hi = min(1.0, lo + bin_width)
        result.append({
            "bin_low": lo,
            "bin_high": hi,
            "sample_size": len(group),
            "mean_predicted_probability": sum(r["model_probability"] for r in group) / len(group),
            "actual_rate": sum(r["outcome"] for r in group) / len(group),
        })
    return result


def build_validation_report(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return CLV, calibration, and edge-decay diagnostics from live-shadow rows."""
    rows = [_validate_row(row, i) for i, row in enumerate(records)]
    if not rows:
        raise ValidationError("unsafe_empty_validation_sample")

    by_conference: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_market: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_conference[row["conference"]].append(row)
        by_market[row["market_type"]].append(row)

    return {
        "version": MODEL_VERSION,
        "overall": _summary(rows),
        "calibration_curve": _calibration_bins(rows),
        "by_conference": {key: _summary(value) for key, value in sorted(by_conference.items())},
        "by_market_type": {key: _summary(value) for key, value in sorted(by_market.items())},
        "diagnostics": {
            "live_shadow_only": True,
            "official_event_id_only": True,
            "projection_weight": 0.0,
            "may_modify_projection": False,
            "feature_expansion": False,
            "core_model_frozen": True,
        },
    }


__all__ = ["ALLOWED_MARKETS", "MODEL_VERSION", "ValidationError", "build_validation_report"]
