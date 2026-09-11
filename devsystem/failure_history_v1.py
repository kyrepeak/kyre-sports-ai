"""Bounded, evidence-only recurrence history for DevSystem failure fingerprints."""
from __future__ import annotations

from typing import Any


MAX_PRIOR_RUN_IDS = 5


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
                {"run_id": run_id, "sha": sha, "ref": ref}
            )

    return index


def attach_recurrence(
    report: dict[str, Any],
    history_packets: list[dict[str, Any]] | None,
    *,
    current_run_id: str = "",
) -> dict[str, Any]:
    """Attach recurrence evidence without claiming flakiness or unlimited history."""
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
        if not history_available:
            status = "history-unavailable"
            confidence = "unavailable"
        elif prior_count:
            status = "recurring"
            confidence = "confirmed"
        else:
            status = "not-seen-in-history"
            confidence = "bounded"

        failure["recurrence_status"] = status
        failure["recurrence_confidence"] = confidence
        failure["prior_occurrence_count"] = prior_count
        failure["known_occurrence_count"] = prior_count + 1
        failure["prior_run_ids"] = [
            item["run_id"] for item in prior if item.get("run_id")
        ][:MAX_PRIOR_RUN_IDS]

    primary = report.get("primary")
    if primary:
        primary_fingerprint = str(primary.get("failure_fingerprint") or "")
        for failure in failures:
            if str(failure.get("failure_fingerprint") or "") == primary_fingerprint:
                for key in (
                    "recurrence_status",
                    "recurrence_confidence",
                    "prior_occurrence_count",
                    "known_occurrence_count",
                    "prior_run_ids",
                ):
                    primary[key] = failure.get(key)
                break

    return {
        "source": "bounded-failure-packet-artifacts",
        "history_available": history_available,
        "packets_scanned": len(packets),
        "fingerprints_seen": len(index),
        "current_run_id": current_run_id,
        "claims_flakiness": False,
    }
