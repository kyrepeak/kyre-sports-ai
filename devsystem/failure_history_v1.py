"""Bounded, evidence-only recurrence history for DevSystem failure fingerprints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


MAX_PRIOR_RUN_IDS = 5
HISTORY_TIMESTAMP_FIELD = "_history_source_created_at"


def _parse_utc_datetime(value: Any) -> datetime | None:
    """Return an aware UTC datetime only when the supplied value is trustworthy."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _normalize_utc_timestamp(value: Any) -> str:
    """Return a canonical UTC timestamp only when the supplied value is trustworthy."""
    parsed = _parse_utc_datetime(value)
    if parsed is None:
        return ""
    return parsed.isoformat().replace("+00:00", "Z")


def _format_age(total_seconds: int) -> str:
    """Format a non-negative elapsed duration without implying recurrence cadence."""
    seconds = max(0, int(total_seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


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
    current_run_created_at: str = "",
) -> dict[str, Any]:
    """Attach bounded recurrence chronology/age evidence without flakiness claims."""
    history_available = history_packets is not None
    packets = history_packets or []
    index = _history_index(packets)
    current_created_at = _normalize_utc_timestamp(current_run_created_at)
    current_dt = _parse_utc_datetime(current_created_at)

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

        age_seconds: int | None = None
        age_display = ""
        if not history_available:
            age_confidence = "unavailable"
        elif not prior_count:
            age_confidence = "not-applicable"
        elif timing_confidence != "confirmed" or current_dt is None:
            age_confidence = "unavailable"
        else:
            prior_last_dt = _parse_utc_datetime(prior_times[-1])
            if prior_last_dt is None or prior_last_dt > current_dt:
                age_confidence = "unavailable"
            else:
                age_seconds = int((current_dt - prior_last_dt).total_seconds())
                age_display = _format_age(age_seconds)
                age_confidence = "confirmed"

        failure["recurrence_status"] = status
        failure["recurrence_confidence"] = confidence
        failure["recurrence_timing_confidence"] = timing_confidence
        failure["recurrence_age_confidence"] = age_confidence
        failure["prior_occurrence_count"] = prior_count
        failure["known_occurrence_count"] = prior_count + 1
        failure["prior_run_ids"] = [
            item["run_id"] for item in prior if item.get("run_id")
        ][:MAX_PRIOR_RUN_IDS]
        failure["prior_first_seen_at"] = prior_times[0] if prior_times else ""
        failure["prior_last_seen_at"] = prior_times[-1] if prior_times else ""
        failure["prior_last_seen_age_seconds"] = age_seconds
        failure["prior_last_seen_age"] = age_display

    primary = report.get("primary")
    if primary:
        primary_fingerprint = str(primary.get("failure_fingerprint") or "")
        for failure in failures:
            if str(failure.get("failure_fingerprint") or "") == primary_fingerprint:
                for key in (
                    "recurrence_status",
                    "recurrence_confidence",
                    "recurrence_timing_confidence",
                    "recurrence_age_confidence",
                    "prior_occurrence_count",
                    "known_occurrence_count",
                    "prior_run_ids",
                    "prior_first_seen_at",
                    "prior_last_seen_at",
                    "prior_last_seen_age_seconds",
                    "prior_last_seen_age",
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
        "current_run_created_at": current_created_at,
        "claims_flakiness": False,
        "claims_cadence": False,
    }
