"""API2 Control-Plane Efficiency V1 Step 3 — WAIT != FAIL State Machine.

Recognizes evidence-backed temporary deployment/upstream states and converts
those states into event-driven WAIT decisions. WAIT never grants a repository,
product, deployment, or retry mutation. Rechecks require meaningful state-token
movement rather than time-based or anxiety-based polling.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

VERSION = "API2_CONTROL_PLANE_EFFICIENCY_V1_STEP3_WAIT_NOT_FAIL_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
BLIND_RETRY_ALLOWED = False

_DEPLOYMENT_IN_FLIGHT = (
    r"deployment[^\n]*(queued|building|activating|in[- ]flight|still progressing)",
    r"deploy[_ -]?phase\s*[:=]\s*(queued|building|activating)",
    r"waiting for deployment event",
)
_DEPLOYMENT_IDENTITY_PENDING = (
    r"deployment identity[^\n]*(not ready|unavailable|pending)",
    r"production sha[^\n]*(not ready|unavailable|missing|pending)",
    r"waiting for deployment identity",
)
_STALE_DEPLOYMENT = (
    r"stale deployment",
    r"still serves? (an )?older sha",
    r"not yet deployed",
    r"expected\s*[:=][^\s]+[^\n]*(actual|observed)\s*[:=][^\s]+",
    r"expected sha[^\n]*(actual|observed|production) sha",
)

_SHA = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)


class WaitStateFailure(RuntimeError):
    pass


def _normalize(text: str) -> str:
    value = (text or "").lower().strip()
    value = re.sub(r"\s+", " ", value)
    return value[:2000]


def _phase(text: str) -> str:
    for phase in ("queued", "building", "activating", "live", "failed"):
        if re.search(rf"\b{phase}\b", text):
            return phase.upper()
    return ""


def _meaningful_identity(text: str) -> str:
    shas = _SHA.findall(text)
    if not shas:
        return ""
    # Preserve the latest observed identity without making timestamps/log noise
    # alter the state token.
    return shas[-1].lower()


def _token(*, state: str, owner: str, text: str, evidence_signal: str) -> str:
    basis = {
        "state": state,
        "owner": owner,
        "phase": _phase(text),
        "observed_identity": _meaningful_identity(text),
        "evidence_signal": str(evidence_signal or ""),
    }
    raw = json.dumps(basis, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "WAIT-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24].upper()


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def classify_wait(
    *,
    job_name: str,
    layer: str,
    evidence_signal: str,
    evidence_text: str,
) -> dict[str, Any] | None:
    job = str(job_name or "").strip().lower()
    layer_name = str(layer or "").strip().lower()
    signal = str(evidence_signal or "").strip().lower()
    text = _normalize(evidence_text)

    deployment_surface = (
        layer_name in {"production", "deployment", "hosting"}
        or "production-verification" in job
        or job.startswith("deploy")
        or "deployment" in text
    )

    state = ""
    owner = ""
    wake_condition = ""

    if deployment_surface and _matches(_DEPLOYMENT_IN_FLIGHT, text):
        state = "WAITING_FOR_DEPLOYMENT_EVENT"
        owner = "DEPLOYMENT"
        wake_condition = "deployment phase changes or a terminal deployment event arrives"
    elif deployment_surface and _matches(_DEPLOYMENT_IDENTITY_PENDING, text):
        state = "WAITING_FOR_DEPLOYMENT_IDENTITY"
        owner = "DEPLOYMENT"
        wake_condition = "production identity becomes available or deployment phase changes"
    elif deployment_surface and _matches(_STALE_DEPLOYMENT, text):
        state = "WAITING_FOR_EXACT_DEPLOYMENT"
        owner = "DEPLOYMENT"
        wake_condition = "observed production SHA changes or deployment emits a terminal event"
    elif signal == "network-upstream":
        state = "WAITING_FOR_UPSTREAM_RECOVERY"
        owner = "EXTERNAL"
        wake_condition = "upstream health/rate-limit state changes"

    if not state:
        return None

    result = {
        "version": VERSION,
        "disposition": "WAIT",
        "state": state,
        "owner": owner,
        "state_token": _token(
            state=state,
            owner=owner,
            text=text,
            evidence_signal=signal,
        ),
        "wake_condition": wake_condition,
        "recheck_policy": "EVENT_DRIVEN_STATE_CHANGE_ONLY",
        "blind_retry_allowed": BLIND_RETRY_ALLOWED,
        "retry_allowed_now": False,
        "next_legal_action": "WAIT_FOR_STATE_CHANGE",
        "protections": {
            "wait_is_not_failure": True,
            "wait_removed_from_repair_queue": True,
            "unchanged_state_blocks_recheck": True,
            "product_patch_forbidden": True,
            "deployment_mutation_not_granted": True,
            "network_calls": NETWORK_CALLS,
            "auto_mutate": AUTO_MUTATE,
            "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }
    return validate_wait_decision(result)


def state_change_allows_recheck(previous_state_token: str, current_state_token: str) -> bool:
    before = str(previous_state_token or "").strip()
    after = str(current_state_token or "").strip()
    if not before or not after:
        return False
    return before != after


def validate_wait_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("version") != VERSION:
        raise WaitStateFailure("WAIT state version drift")
    if payload.get("disposition") != "WAIT":
        raise WaitStateFailure("WAIT state disposition drift")
    if payload.get("owner") not in {"DEPLOYMENT", "EXTERNAL"}:
        raise WaitStateFailure("WAIT state owner drift")
    if payload.get("blind_retry_allowed") is not False:
        raise WaitStateFailure("WAIT state may not allow blind retry")
    if payload.get("retry_allowed_now") is not False:
        raise WaitStateFailure("WAIT state may not authorize immediate retry")
    if payload.get("next_legal_action") != "WAIT_FOR_STATE_CHANGE":
        raise WaitStateFailure("WAIT next action drift")
    token = str(payload.get("state_token") or "")
    if not re.fullmatch(r"WAIT-[0-9A-F]{24}", token):
        raise WaitStateFailure("WAIT state token invalid")
    protections = payload.get("protections") or {}
    required = (
        "wait_is_not_failure",
        "wait_removed_from_repair_queue",
        "unchanged_state_blocks_recheck",
        "product_patch_forbidden",
        "deployment_mutation_not_granted",
    )
    if not all(protections.get(key) is True for key in required):
        raise WaitStateFailure("WAIT protections drift")
    if protections.get("network_calls") or protections.get("auto_mutate") or protections.get("may_modify_product_runtime"):
        raise WaitStateFailure("WAIT read-only invariant failed")
    return dict(payload)


def self_test() -> dict[str, Any]:
    old = "b" * 40
    new = "a" * 40
    inflight = classify_wait(
        job_name="production-verification",
        layer="production",
        evidence_signal="unclassified-evidence",
        evidence_text="deployment phase=ACTIVATING; still progressing",
    )
    stale = classify_wait(
        job_name="production-verification",
        layer="production",
        evidence_signal="unclassified-evidence",
        evidence_text=f"stale deployment expected={new} actual={old}",
    )
    upstream = classify_wait(
        job_name="data-provider-check",
        layer="unknown",
        evidence_signal="network-upstream",
        evidence_text="503 Service Unavailable from upstream API",
    )
    deterministic = classify_wait(
        job_name="cfb-critical",
        layer="cfb",
        evidence_signal="test-assertion",
        evidence_text="AssertionError expected official event ID",
    )
    stale_same = classify_wait(
        job_name="production-verification",
        layer="production",
        evidence_signal="unclassified-evidence",
        evidence_text=f"stale deployment expected={new} actual={old}",
    )
    stale_changed = classify_wait(
        job_name="production-verification",
        layer="production",
        evidence_signal="unclassified-evidence",
        evidence_text=f"stale deployment expected={new} actual={new}",
    )
    result = {
        "status": "GREEN",
        "version": VERSION,
        "inflight_waits": inflight is not None and inflight["state"] == "WAITING_FOR_DEPLOYMENT_EVENT",
        "stale_waits_for_exact_identity": stale is not None and stale["state"] == "WAITING_FOR_EXACT_DEPLOYMENT",
        "upstream_waits": upstream is not None and upstream["state"] == "WAITING_FOR_UPSTREAM_RECOVERY",
        "deterministic_assertion_not_wait": deterministic is None,
        "unchanged_state_blocks_recheck": not state_change_allows_recheck(
            stale["state_token"], stale_same["state_token"]
        ),
        "changed_state_allows_recheck": state_change_allows_recheck(
            stale["state_token"], stale_changed["state_token"]
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "inflight_waits",
        "stale_waits_for_exact_identity",
        "upstream_waits",
        "deterministic_assertion_not_wait",
        "unchanged_state_blocks_recheck",
        "changed_state_allows_recheck",
    )
    if not all(result[key] is True for key in required):
        raise WaitStateFailure("WAIT state self-test failed")
    print("API2_CONTROL_PLANE_EFFICIENCY_V1_STEP3_WAIT_NOT_FAIL_GREEN")
    return result


if __name__ == "__main__":
    print(json.dumps(self_test(), indent=2, sort_keys=True))
