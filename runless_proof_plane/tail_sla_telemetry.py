from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

TAIL_SLA_SECONDS = 120
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
POLLING_REQUIRED = False
GITHUB_ACTIONS_FALLBACK = 0


class TailSLATelemetryFailure(RuntimeError):
    pass


def _parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise TailSLATelemetryFailure("MISSING_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TailSLATelemetryFailure("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None:
        raise TailSLATelemetryFailure("TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc)


def _fmt_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _base_result(**extra: Any) -> dict[str, Any]:
    return {
        "network_calls": False,
        "auto_mutate": False,
        "mutation_authority_granted": False,
        "polling_required": False,
        "github_actions_fallback": 0,
        **extra,
    }


def _validated_timeline(timeline: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous: datetime | None = None
    for item in timeline:
        row = deepcopy(dict(item))
        state = str(row.get("state") or "").strip()
        if not state:
            raise TailSLATelemetryFailure("MISSING_STATE")
        at = _parse_utc(str(row.get("at_utc") or ""))
        if previous is not None and at < previous:
            raise TailSLATelemetryFailure("NON_MONOTONIC_TIMESTAMP")
        previous = at
        row["state"] = state
        row["at_utc"] = _fmt_utc(at)
        row["blocked_on"] = row.get("blocked_on")
        row["next_event"] = row.get("next_event")
        row["hosted_deployment_wait"] = bool(row.get("hosted_deployment_wait", False))
        row["identity"] = row.get("identity")
        rows.append(row)
    return rows


def record_tail_state(
    timeline: Sequence[Mapping[str, Any]],
    *,
    state: str,
    at_utc: str,
    blocked_on: str | None = None,
    next_event: str | None = None,
    hosted_deployment_wait: bool = False,
    identity: str | None = None,
) -> list[dict[str, Any]]:
    """Return a new timeline with one exact state transition appended.

    The input is never mutated. Timestamps must be timezone-aware and monotonic.
    """

    rows = _validated_timeline(timeline)
    state_text = str(state or "").strip()
    if not state_text:
        raise TailSLATelemetryFailure("MISSING_STATE")
    at = _parse_utc(at_utc)
    if rows and at < _parse_utc(rows[-1]["at_utc"]):
        raise TailSLATelemetryFailure("NON_MONOTONIC_TIMESTAMP")
    rows.append(
        {
            "state": state_text,
            "at_utc": _fmt_utc(at),
            "blocked_on": blocked_on,
            "next_event": next_event,
            "hosted_deployment_wait": bool(hosted_deployment_wait),
            "identity": identity,
        }
    )
    return rows


def evaluate_tail_sla(
    timeline: Sequence[Mapping[str, Any]],
    *,
    now_utc: str,
    meaningful_identity_change: bool = False,
) -> dict[str, Any]:
    """Evaluate final-mile latency without polling or granting mutation authority."""

    rows = _validated_timeline(timeline)
    now = _parse_utc(now_utc)
    current = rows[-1] if rows else {
        "state": None,
        "at_utc": None,
        "blocked_on": None,
        "next_event": None,
        "hosted_deployment_wait": False,
        "identity": None,
    }
    timestamps = [{"state": row["state"], "at_utc": row["at_utc"]} for row in rows]

    certified = next((row for row in rows if row["state"] == "CERTIFIED_PROOF"), None)
    if certified is None:
        return _base_result(
            decision="RUNLESS_TAIL_SLA_UNARMED",
            allowed=False,
            sla_seconds=TAIL_SLA_SECONDS,
            sla_applicable=False,
            sla_status="UNARMED",
            within_sla=None,
            first_certified_proof_at=None,
            current_state=current.get("state"),
            state_timestamps=timestamps,
            tail_age_seconds=None,
            blocked_on=current.get("blocked_on"),
            next_event=current.get("next_event"),
            event_driven_resume=False,
            resume_now=False,
        )

    start = _parse_utc(certified["at_utc"])
    if now < start:
        raise TailSLATelemetryFailure("NOW_PRECEDES_CERTIFIED_PROOF")

    completed = next((row for row in rows if row["state"] == "GREEN_FROZEN"), None)
    end = _parse_utc(completed["at_utc"]) if completed is not None else now
    if end < start:
        raise TailSLATelemetryFailure("COMPLETION_PRECEDES_CERTIFIED_PROOF")
    tail_age_seconds = int((end - start).total_seconds())

    hosted_wait = bool(current.get("hosted_deployment_wait")) and current.get("state") != "GREEN_FROZEN"
    if hosted_wait:
        wake = bool(meaningful_identity_change)
        return _base_result(
            decision="RUNLESS_TAIL_SLA_RESUME_NOW" if wake else "RUNLESS_TAIL_SLA_HOSTED_WAIT",
            allowed=True,
            sla_seconds=TAIL_SLA_SECONDS,
            sla_applicable=False,
            sla_status="HOSTED_WAIT_EVENT_DRIVEN",
            within_sla=None,
            first_certified_proof_at=certified["at_utc"],
            current_state=current.get("state"),
            state_timestamps=timestamps,
            tail_age_seconds=tail_age_seconds,
            blocked_on=current.get("blocked_on"),
            next_event=current.get("next_event") or "MEANINGFUL_IDENTITY_CHANGE",
            event_driven_resume=True,
            resume_now=wake,
            identity=current.get("identity"),
        )

    within_sla = tail_age_seconds <= TAIL_SLA_SECONDS
    if completed is not None and within_sla:
        decision = "RUNLESS_TAIL_SLA_GREEN"
    elif within_sla:
        decision = "RUNLESS_TAIL_SLA_TRACKING"
    else:
        decision = "RUNLESS_TAIL_SLA_BREACH"

    return _base_result(
        decision=decision,
        allowed=True,
        sla_seconds=TAIL_SLA_SECONDS,
        sla_applicable=True,
        sla_status="WITHIN_SLA" if within_sla else "BREACHED",
        within_sla=within_sla,
        first_certified_proof_at=certified["at_utc"],
        current_state=current.get("state"),
        state_timestamps=timestamps,
        tail_age_seconds=tail_age_seconds,
        blocked_on=current.get("blocked_on"),
        next_event=current.get("next_event"),
        event_driven_resume=False,
        resume_now=False,
    )
