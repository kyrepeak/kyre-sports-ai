"""Bounded, evidence-only recurrence history for DevSystem failure fingerprints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


MAX_PRIOR_RUN_IDS = 5
HISTORY_TIMESTAMP_FIELD = "_history_source_created_at"


def _normalize_utc_timestamp(value: Any) -> str:
    """Return a canonical UTC timestamp only when the supplied value is trustworthy."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        return ""
    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _history_index(history_packets: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    """Index prior packet failures by stable fingerprint, once per source run."""
    index: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[str, str]] = set()

    for packet in history_packets:
        if not isinstance(packet, dict):
            continue
        run_id = str(packet.get("run_id") or "")
        sha = str(packet.get("sha") or "")
        ref = str(packet.get("ref") or "")
        occurred_at = _normalize_utc_timestamp(packet.get(HISTORY_TIMESTAMP_FIELD))
        failures = ((packet.get("triage") or {}).get("failures") or [])
        for failure in failures:
            if not isinstance(failure, dict):
                continue
            fingerprint = str(failure.get("failure_fingerprint") or "")
            if not fingerprint.startswith("KYRE-CI-"):
                continue
            occurrence_key = run_id or sha or ref
            if not occurrence_key:
                continue
            dedupe_key = (fingerprint, occurrence_key)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            index.setdefault(fingerprint, []).append(
                {
                    "run_id": run_id,
                    "sha": sha,
                    "ref": ref,
                    "occurred_at": occurred_at,
                }
            )

    return index


def attach_recurrence(
    report: dict[str, Any],
    history_packets: list[dict[str, Any]] | None,
    *,
    current_run_id: str = "",
) -> dict[str, Any]:
    """Attach bounded recurrence and chronology evidence without claiming flakiness."""
    history_available = history_packets is not None
    packets = history_packets or []
    index = _history_index(packets)

    failures = report.get("failures") or []
    for failure in failures:
        fingerprint = str(failure.get("failure_fingerprint") or "")
        prior = [
            item
            for item in index.get(fingerprint, [])
            if not current_run_id or item.get("run_id") != current_run_id
        ]
        prior_count = len(prior)
        prior_times = sorted(
            item["occurred_at"] for item in prior if item.get("occurred_at")
        )
        if not history_available:
            status = "history-unavailable"
            confidence = "unavailable"
            timing_confidence = "unavailable"
        elif prior_count:
            status = "recurring"
            confidence = "confirmed"
            if len(prior_times) == prior_count:
                timing_confidence = "confirmed"
            elif prior_times:
                timing_confidence = "partial"
            else:
                timing_confidence = "unavailable"
        else:
            status = "not-seen-in-history"
            confidence = "bounded"
            timing_confidence = "not-applicable"

        failure["recurrence_status"] = status
        failure["recurrence_confidence"] = confidence
        failure["recurrence_timing_confidence"] = timing_confidence
        failure["prior_occurrence_count"] = prior_count
        failure["known_occurrence_count"] = prior_count + 1
        failure["prior_run_ids"] = [
            item["run_id"] for item in prior if item.get("run_id")
        ][:MAX_PRIOR_RUN_IDS]
        failure["prior_first_seen_at"] = prior_times[0] if prior_times else ""
        failure["prior_last_seen_at"] = prior_times[-1] if prior_times else ""

    primary = report.get("primary")
    if primary:
        primary_fingerprint = str(primary.get("failure_fingerprint") or "")
        for failure in failures:
            if str(failure.get("failure_fingerprint") or "") == primary_fingerprint:
                for key in (
                    "recurrence_status",
                    "recurrence_confidence",
                    "recurrence_timing_confidence",
                    "prior_occurrence_count",
                    "known_occurrence_count",
                    "prior_run_ids",
                    "prior_first_seen_at",
                    "prior_last_seen_at",
                ):
                    primary[key] = failure.get(key)
                break

    return {
        "source": "bounded-failure-packet-artifacts",
        "history_available": history_available,
        "packets_scanned": len(packets),
        "fingerprints_seen": len(index),
        "timestamped_packets": sum(
            1 for packet in packets if _normalize_utc_timestamp(packet.get(HISTORY_TIMESTAMP_FIELD))
        ),
        "current_run_id": current_run_id,
        "claims_flakiness": False,
        "claims_cadence": False,
    }
