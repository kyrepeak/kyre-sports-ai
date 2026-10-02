"""MONSTER V8 Step 5 — Adaptive Stuck Thresholds V1.

This layer learns normal terminal durations for an exact workflow/job identity
and converts that history into a deterministic wait deadline.

It never polls GitHub, never starts/restarts work, and never grants mutation
authority.  Long-running authoritative work remains protected by the frozen
V7 Progress Truth + Stuck-State Detector and V5 heartbeat/dead-man layer.

Cold start is fail-safe: when there is not enough clean history, the caller's
existing fixed timeout is preserved exactly.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from statistics import median
from typing import Any, Mapping, Sequence

from devsystem.progress_truth_stuck_state_detector_v1 import (
    VERSION as PROGRESS_TRUTH_VERSION,
    evaluate_progress,
)

VERSION = "MONSTER_V8_ADAPTIVE_STUCK_THRESHOLDS_V1"
REQUIRED_PROGRESS_TRUTH_VERSION = (
    "MONSTER_V7_PROGRESS_TRUTH_STUCK_STATE_DETECTOR_V1"
)

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

MIN_HISTORY_SAMPLES = 5
MAX_HISTORY_SAMPLES = 50
MIN_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 7200
GRACE_SECONDS = 30
_HISTORY_SUCCESS = {"SUCCESS"}
_LIVE_RUN_STATES = {"QUEUED", "PENDING", "WAITING", "IN_PROGRESS", "RUNNING"}
_TERMINAL_RUN_STATES = {
    "SUCCESS",
    "FAILURE",
    "CANCELLED",
    "SKIPPED",
    "TIMED_OUT",
    "COMPLETED",
}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class AdaptiveThresholdFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise AdaptiveThresholdFailure(f"{field} is required")
    return out


def _positive_int(value: Any, field: str) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise AdaptiveThresholdFailure(f"{field} must be an integer") from exc
    if out <= 0:
        raise AdaptiveThresholdFailure(f"{field} must be positive")
    return out


def _duration(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise AdaptiveThresholdFailure("duration_seconds must be numeric") from exc
    if not math.isfinite(out) or out <= 0 or out > MAX_TIMEOUT_SECONDS * 4:
        raise AdaptiveThresholdFailure("duration_seconds outside safe bounds")
    return round(out, 3)


def _normalize_sample(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise AdaptiveThresholdFailure("history sample must be an object")
    workflow_key = _text(raw.get("workflow_key"), "workflow_key")
    job_key = _text(raw.get("job_key"), "job_key")
    run_id = _positive_int(raw.get("run_id"), "run_id")
    head_sha = str(raw.get("head_sha") or "").strip().lower()
    if not _SHA40.fullmatch(head_sha):
        raise AdaptiveThresholdFailure("head_sha must be a lowercase 40-char SHA")
    conclusion = _text(raw.get("conclusion"), "conclusion").upper()
    if conclusion not in (_HISTORY_SUCCESS | _TERMINAL_RUN_STATES):
        raise AdaptiveThresholdFailure(f"unsupported conclusion: {conclusion}")
    duration_seconds = _duration(raw.get("duration_seconds"))
    identity = {
        "workflow_key": workflow_key,
        "job_key": job_key,
        "run_id": run_id,
        "head_sha": head_sha,
    }
    return {
        **identity,
        "duration_seconds": duration_seconds,
        "conclusion": conclusion,
        "sample_id": _digest({**identity, "conclusion": conclusion, "duration_seconds": duration_seconds}),
    }


def _nearest_rank(values: Sequence[float], percentile: int) -> float:
    if not values:
        raise AdaptiveThresholdFailure("percentile requires values")
    if percentile <= 0 or percentile > 100:
        raise AdaptiveThresholdFailure("percentile outside 1..100")
    ordered = sorted(float(v) for v in values)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return ordered[rank - 1]


def _dedupe_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    workflow_key: str,
    job_key: str,
) -> list[dict[str, Any]]:
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)):
        raise AdaptiveThresholdFailure("samples must be a sequence")
    exact: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for raw in samples:
        row = _normalize_sample(raw)
        if row["workflow_key"] != workflow_key or row["job_key"] != job_key:
            continue
        key = (
            row["workflow_key"],
            row["job_key"],
            row["run_id"],
            row["head_sha"],
        )
        previous = exact.get(key)
        if previous is not None and (
            previous["duration_seconds"] != row["duration_seconds"]
            or previous["conclusion"] != row["conclusion"]
        ):
            raise AdaptiveThresholdFailure(
                "conflicting history for one exact workflow/job/run/head identity"
            )
        exact[key] = row
    ordered = sorted(exact.values(), key=lambda row: row["run_id"])
    return ordered[-MAX_HISTORY_SAMPLES:]


def derive_threshold(
    samples: Sequence[Mapping[str, Any]],
    *,
    workflow_key: str,
    job_key: str,
    fallback_seconds: int,
) -> dict[str, Any]:
    """Build a deterministic deadline from clean successful terminal history."""
    workflow = _text(workflow_key, "workflow_key")
    job = _text(job_key, "job_key")
    fallback = _positive_int(fallback_seconds, "fallback_seconds")
    if fallback < MIN_TIMEOUT_SECONDS or fallback > MAX_TIMEOUT_SECONDS:
        raise AdaptiveThresholdFailure("fallback_seconds outside safe bounds")

    exact = _dedupe_samples(samples, workflow_key=workflow, job_key=job)
    successful = [row for row in exact if row["conclusion"] in _HISTORY_SUCCESS]
    successful = successful[-MAX_HISTORY_SAMPLES:]

    base = {
        "version": VERSION,
        "workflow_key": workflow,
        "job_key": job,
        "fallback_seconds": fallback,
        "sample_count": len(successful),
        "minimum_samples": MIN_HISTORY_SAMPLES,
        "history_run_ids": [row["run_id"] for row in successful],
        "history_head_shas": [row["head_sha"] for row in successful],
        "mutation_authority": False,
    }

    if len(successful) < MIN_HISTORY_SAMPLES:
        policy = {
            **base,
            "mode": "COLD_START_FALLBACK",
            "threshold_seconds": fallback,
            "p50_seconds": None,
            "p90_seconds": None,
            "mad_seconds": None,
            "winsor_cap_seconds": None,
            "reason": "INSUFFICIENT_SUCCESS_HISTORY_PRESERVE_EXISTING_TIMEOUT",
        }
        policy["baseline_digest"] = _digest(policy)
        return policy

    durations = [float(row["duration_seconds"]) for row in successful]
    p50 = float(median(durations))
    deviations = [abs(value - p50) for value in durations]
    mad = float(median(deviations))
    guard = max(5.0, mad)

    # A single pathological success must not teach the detector that a very
    # long stall is normal.  Winsorization is deterministic and history-only.
    winsor_cap = max(p50 * 2.0, p50 + (8.0 * guard))
    robust = [min(value, winsor_cap) for value in durations]
    p90 = _nearest_rank(robust, 90)

    learned = math.ceil(max(p90 * 1.5, p50 + (6.0 * guard))) + GRACE_SECONDS
    lower = max(MIN_TIMEOUT_SECONDS, math.ceil(fallback * 0.5))
    upper = min(
        MAX_TIMEOUT_SECONDS,
        max(fallback * 4, fallback + 300),
    )
    threshold = max(lower, min(int(learned), upper))

    policy = {
        **base,
        "mode": "ADAPTIVE",
        "threshold_seconds": threshold,
        "p50_seconds": round(p50, 3),
        "p90_seconds": round(p90, 3),
        "mad_seconds": round(mad, 3),
        "winsor_cap_seconds": round(winsor_cap, 3),
        "lower_bound_seconds": lower,
        "upper_bound_seconds": upper,
        "reason": "EXACT_WORKFLOW_JOB_SUCCESS_HISTORY",
    }
    policy["baseline_digest"] = _digest(policy)
    return policy


def classify_wait(
    policy: Mapping[str, Any],
    *,
    elapsed_seconds: int,
    observed_run_state: str,
    heartbeat_live: bool | None = None,
) -> dict[str, Any]:
    """Classify a wait without starting, rerunning, cancelling, or mutating."""
    if not isinstance(policy, Mapping) or policy.get("version") != VERSION:
        raise AdaptiveThresholdFailure("adaptive policy version mismatch")
    elapsed = int(elapsed_seconds)
    if elapsed < 0:
        raise AdaptiveThresholdFailure("elapsed_seconds cannot be negative")
    threshold = _positive_int(policy.get("threshold_seconds"), "threshold_seconds")
    state = _text(observed_run_state, "observed_run_state").upper()

    base = {
        "version": VERSION,
        "elapsed_seconds": elapsed,
        "threshold_seconds": threshold,
        "overdue_seconds": max(0, elapsed - threshold),
        "observed_run_state": state,
        "mutation_authority": False,
        "duplicate_run_allowed": False,
    }

    if elapsed <= threshold:
        return {
            **base,
            "stuck": False,
            "classification": "EXPECTED_WAIT",
            "next_legal_action": "WAIT_FOR_MATERIAL_EVENT",
        }

    if state in _TERMINAL_RUN_STATES:
        return {
            **base,
            "stuck": False,
            "classification": "TERMINAL_EVENT_AVAILABLE",
            "next_legal_action": "CONSUME_TERMINAL_EVENT",
        }

    if state in _LIVE_RUN_STATES:
        return {
            **base,
            "stuck": False,
            "classification": "SLOW_BUT_AUTHORITATIVE_RUN_ACTIVE",
            "next_legal_action": "WAIT_FOR_TERMINAL_EVENT",
        }

    if heartbeat_live is True:
        return {
            **base,
            "stuck": False,
            "classification": "SLOW_BUT_HEARTBEAT_LIVE",
            "next_legal_action": "WAIT_FOR_MATERIAL_EVENT",
        }

    return {
        **base,
        "stuck": True,
        "classification": "ABNORMAL_STALL_LIVENESS_UNPROVEN",
        "next_legal_action": "RUN_FROZEN_STUCK_STATE_DETECTOR",
    }


def adapt_waiting_checkpoints(
    checkpoints: Sequence[Mapping[str, Any]],
    *,
    histories: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Return copied checkpoints with adaptive deadlines for configured waits."""
    if not isinstance(histories, Mapping):
        raise AdaptiveThresholdFailure("histories must be an object")
    adapted = deepcopy(list(checkpoints))
    policies: dict[str, dict[str, Any]] = {}

    for row in adapted:
        if not isinstance(row, dict):
            raise AdaptiveThresholdFailure("checkpoint must be an object")
        if str(row.get("status") or "").upper() != "WAITING":
            continue
        checkpoint_id = _text(row.get("checkpoint_id"), "checkpoint_id")
        cfg = histories.get(checkpoint_id)
        if cfg is None:
            continue
        if not isinstance(cfg, Mapping):
            raise AdaptiveThresholdFailure("checkpoint history config must be an object")
        fallback = _positive_int(
            row.get("wait_timeout_seconds"),
            "wait_timeout_seconds",
        )
        policy = derive_threshold(
            cfg.get("samples") or [],
            workflow_key=_text(cfg.get("workflow_key"), "workflow_key"),
            job_key=_text(cfg.get("job_key"), "job_key"),
            fallback_seconds=fallback,
        )
        row["wait_timeout_seconds"] = policy["threshold_seconds"]
        policies[checkpoint_id] = policy

    return {
        "checkpoints": adapted,
        "policies": policies,
        "version": VERSION,
        "mutation_authority": False,
    }


def evaluate_progress_adaptively(
    detector_state: Mapping[str, Any],
    *,
    checkpoints: Sequence[Mapping[str, Any]],
    now_utc: str,
    histories: Mapping[str, Mapping[str, Any]],
    heartbeat_contexts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply adaptive deadlines, then delegate truth/stuck handling to frozen V7."""
    if PROGRESS_TRUTH_VERSION != REQUIRED_PROGRESS_TRUTH_VERSION:
        raise AdaptiveThresholdFailure("frozen progress-truth dependency mismatch")
    adapted = adapt_waiting_checkpoints(checkpoints, histories=histories)
    report = evaluate_progress(
        detector_state,
        checkpoints=adapted["checkpoints"],
        now_utc=now_utc,
        heartbeat_contexts=heartbeat_contexts or {},
    )
    out = deepcopy(report)
    out["result"]["adaptive_stuck_thresholds_version"] = VERSION
    out["result"]["adaptive_threshold_policies"] = adapted["policies"]
    out["result"]["adaptive_threshold_mutation_authority"] = False
    return out


def _sample(
    run_id: int,
    duration: float,
    *,
    workflow: str = "DevSystem targeted CI",
    job: str = "devsystem-final-gate",
    conclusion: str = "SUCCESS",
) -> dict[str, Any]:
    return {
        "workflow_key": workflow,
        "job_key": job,
        "run_id": run_id,
        "head_sha": f"{run_id % 16:x}" * 40,
        "duration_seconds": duration,
        "conclusion": conclusion,
    }


def contract_self_test() -> dict[str, Any]:
    history = [
        _sample(101, 95),
        _sample(102, 102),
        _sample(103, 108),
        _sample(104, 111),
        _sample(105, 119),
        _sample(106, 125),
        _sample(107, 2500),  # winsorized; one slow success cannot poison the baseline
    ]
    policy = derive_threshold(
        history,
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    cold = derive_threshold(
        history[:3],
        workflow_key="DevSystem targeted CI",
        job_key="devsystem-final-gate",
        fallback_seconds=900,
    )
    expected = classify_wait(
        policy,
        elapsed_seconds=max(1, policy["threshold_seconds"] - 1),
        observed_run_state="IN_PROGRESS",
    )
    live = classify_wait(
        policy,
        elapsed_seconds=policy["threshold_seconds"] + 120,
        observed_run_state="IN_PROGRESS",
    )
    stalled = classify_wait(
        policy,
        elapsed_seconds=policy["threshold_seconds"] + 120,
        observed_run_state="UNKNOWN",
        heartbeat_live=False,
    )

    if policy["mode"] != "ADAPTIVE":
        raise AdaptiveThresholdFailure("adaptive history did not activate")
    if cold["threshold_seconds"] != 900 or cold["mode"] != "COLD_START_FALLBACK":
        raise AdaptiveThresholdFailure("cold start failed to preserve existing timeout")
    if policy["threshold_seconds"] >= policy["upper_bound_seconds"]:
        raise AdaptiveThresholdFailure("single outlier poisoned threshold ceiling")
    if expected["classification"] != "EXPECTED_WAIT" or expected["stuck"]:
        raise AdaptiveThresholdFailure("expected wait misclassified")
    if live["classification"] != "SLOW_BUT_AUTHORITATIVE_RUN_ACTIVE" or live["stuck"]:
        raise AdaptiveThresholdFailure("live authoritative run misclassified")
    if not stalled["stuck"] or stalled["classification"] != "ABNORMAL_STALL_LIVENESS_UNPROVEN":
        raise AdaptiveThresholdFailure("abnormal stall was not detected")

    return {
        "status": "GREEN",
        "version": VERSION,
        "adaptive_history": True,
        "cold_start_preserves_existing_timeout": True,
        "outlier_poisoning_bounded": True,
        "expected_wait_distinguished": True,
        "live_authoritative_run_protected": True,
        "abnormal_stall_detected": True,
        "frozen_progress_truth_reused": PROGRESS_TRUTH_VERSION == REQUIRED_PROGRESS_TRUTH_VERSION,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V8_STEP5_ADAPTIVE_STUCK_THRESHOLDS_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
