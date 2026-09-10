"""CFB Over/Under Step 7B persistent shadow-history collector.

Additive analysis-only storage utilities for certified live-shadow validation rows.
This module never modifies projections, routing, market attachment, or wager logic.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

HISTORY_VERSION = "CFB O/U SHADOW HISTORY V1 • STEP 7B"


class ShadowHistoryError(ValueError):
    """Raised when a row violates the Step 7B history safety contract."""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _validate_row(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise ShadowHistoryError("unsafe_row_not_mapping")
    event_id = _clean(row.get("game_id"))
    if not event_id.isdigit():
        raise ShadowHistoryError("unsafe_non_official_event_id")
    if row.get("identity_verified") is not True:
        raise ShadowHistoryError(f"unsafe_unverified_event_identity:{event_id}")
    if _clean(row.get("source_mode")).casefold() != "live_shadow":
        raise ShadowHistoryError(f"unsafe_non_shadow_row:{event_id}")
    projection_weight = float(row.get("projection_weight", 0.0))
    if projection_weight != 0.0:
        raise ShadowHistoryError(f"unsafe_nonzero_projection_weight:{event_id}")
    if row.get("may_modify_projection") is True:
        raise ShadowHistoryError(f"unsafe_may_modify_projection:{event_id}")

    normalized = dict(row)
    normalized["game_id"] = event_id
    normalized["source_mode"] = "live_shadow"
    normalized["projection_weight"] = 0.0
    normalized["may_modify_projection"] = False
    normalized["identity_verified"] = True
    return normalized


def build_history_snapshot(records: Iterable[Mapping[str, Any]], *, captured_at_utc: str | None = None) -> dict[str, Any]:
    rows = [_validate_row(row) for row in records]
    if not rows:
        raise ShadowHistoryError("unsafe_empty_history_sample")
    stamp = captured_at_utc or datetime.now(timezone.utc).isoformat()
    return {
        "version": HISTORY_VERSION,
        "captured_at_utc": stamp,
        "record_count": len(rows),
        "records": rows,
        "diagnostics": {
            "live_shadow_only": True,
            "official_event_id_only": True,
            "fuzzy_matching": False,
            "synthetic_official_ids": False,
            "projection_weight": 0.0,
            "may_modify_projection": False,
            "core_model_frozen": True,
        },
    }


def append_history_file(path: str | Path, records: Iterable[Mapping[str, Any]], *, captured_at_utc: str | None = None) -> dict[str, Any]:
    """Append one immutable capture batch to a JSONL history file."""
    snapshot = build_history_snapshot(records, captured_at_utc=captured_at_utc)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True, separators=(",", ":")) + "\n")
    return snapshot


def load_history_records(path: str | Path) -> list[dict[str, Any]]:
    """Flatten all certified JSONL capture batches for Step 7A validation."""
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ShadowHistoryError(f"unsafe_invalid_jsonl:{line_number}") from exc
            batch = payload.get("records")
            if not isinstance(batch, list):
                raise ShadowHistoryError(f"unsafe_invalid_batch:{line_number}")
            rows.extend(_validate_row(row) for row in batch)
    return rows


__all__ = ["HISTORY_VERSION", "ShadowHistoryError", "append_history_file", "build_history_snapshot", "load_history_records"]
