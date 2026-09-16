"""Authoritative forward-motion controller for Monster Anti-Loop V2."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from devsystem.action_ledger_v2 import build_receipt
from devsystem.checkpoint_ledger_v2 import CheckpointLedgerV2Failure, validate_checkpoint_ledger

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "devsystem" / "forward_motion_policy_v2.json"

_VOLATILE_KEYS = {
    "run_id",
    "workflow_run_id",
    "timestamp",
    "created_at",
    "updated_at",
    "retry_counter",
    "display_branch",
}


class ForwardMotionV2Failure(RuntimeError):
    pass


def _hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    text = (value or "").lower().strip()
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"\b[0-9a-f]{7,64}\b", "<hex>", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}t\S+z\b", "<timestamp>", text)
    text = re.sub(r"\brun\s+\d+\b", "run <n>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _stable_payload(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _stable_payload(item)
            for key, item in sorted(value.items())
            if str(key) not in _VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_stable_payload(item) for item in value]
    if isinstance(value, str):
        return _normalize_text(value)
    return value


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForwardMotionV2Failure(f"unable to load V2 policy: {exc}") from exc
    if int(payload.get("version", 0)) != 2:
        raise ForwardMotionV2Failure("forward-motion V2 policy version must be 2")
    if payload.get("mode") != "strict_auto_continue_v2":
        raise ForwardMotionV2Failure("forward-motion V2 policy mode drift")
    return payload


def fingerprint_action(action: dict[str, Any]) -> str:
    required = ("task_id", "checkpoint_id", "action_type", "target")
    missing = [name for name in required if not str(action.get(name) or "").strip()]
    if missing:
        raise ForwardMotionV2Failure("action missing required fields: " + ", ".join(missing))
    payload = {
        "task_id": str(action["task_id"]),
        "checkpoint_id": str(action["checkpoint_id"]),
        "action_type": str(action["action_type"]),
        "target": str(action["target"]),
        "inputs": _stable_payload(action.get("inputs") or {}),
        "evidence": _stable_payload(action.get("evidence") or {}),
        "failure": _stable_payload(action.get("failure") or {}),
        "retry": bool(action.get("retry")),
        "failure_class": str(action.get("failure_class") or ""),
        "new_hypothesis": bool(action.get("new_hypothesis")),
        "command": action.get("command") or [],
    }
    return _hash(payload)


def fingerprint_root_cause(action: dict[str, Any]) -> str:
    hint = str(action.get("root_cause_hint") or "").strip()
    if hint:
        return _hash({"root_cause_hint": _normalize_text(hint)})
    failure = action.get("failure") or {}
    if not isinstance(failure, dict):
        failure = {"message": str(failure)}
    semantic = {
        "job": _normalize_text(str(failure.get("job") or "unknown")),
        "layer": _normalize_text(str(failure.get("layer") or "unknown")),
        "evidence_signal": _normalize_text(str(failure.get("evidence_signal") or "none")),
        "error_family": _normalize_text(str(failure.get("error_family") or "unknown")),
        "message": _normalize_text(str(failure.get("message") or failure.get("diagnosis") or "")),
        "target": _normalize_text(str(action.get("target") or "")),
    }
    return _hash(semantic)


def fingerprint_evidence(action: dict[str, Any]) -> str:
    payload = {
        "evidence": _stable_payload(action.get("evidence") or {}),
        "contradictory_evidence": _stable_payload(action.get("contradictory_evidence") or {}),
    }
    return _hash(payload)


def fingerprint_relevant_inputs(action: dict[str, Any]) -> str:
    return _hash(_stable_payload(action.get("inputs") or {}))


def _checkpoint(task_ledger: dict[str, Any], checkpoint_id: str) -> dict[str, Any]:
    for checkpoint in task_ledger.get("checkpoints") or []:
        if str(checkpoint.get("id")) == str(checkpoint_id):
            return checkpoint
    raise ForwardMotionV2Failure(f"unknown checkpoint: {checkpoint_id}")


def _decision(decision: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload = {"decision": decision, "reason": reason}
    payload.update(extra)
    return payload


def _denial_payload(action: dict[str, Any], decision: str, reason: str, **extra: Any) -> dict[str, Any]:
    action_fp = fingerprint_action(action)
    denial_fp = _hash({
        "decision": decision,
        "reason": reason,
        "task_id": str(action.get("task_id") or ""),
        "checkpoint_id": str(action.get("checkpoint_id") or ""),
        "action_fingerprint": action_fp,
    })
    payload = {
        "decision": decision,
        "reason": reason,
        "action_fingerprint": action_fp,
        "denial_fingerprint": denial_fp,
    }
    payload.update(extra)
    return payload


def _validate_override_event(
    task_ledger: dict[str, Any],
    action: dict[str, Any],
    denial: dict[str, Any],
    override_event: dict[str, Any],
) -> str | None:
    if not isinstance(override_event, dict):
        return "override event must be an object"
    event_id = str(override_event.get("event_id") or "").strip()
    if not event_id:
        return "override event requires event_id"
    recorded = [
        item for item in (task_ledger.get("override_events") or [])
        if isinstance(item, dict) and str(item.get("event_id") or "") == event_id
    ]
    if len(recorded) != 1 or recorded[0] != override_event:
        return "override event must be explicitly recorded exactly once in the task ledger"
    if override_event.get("source") != "user_explicit":
        return "override source must be user_explicit"
    if bool(override_event.get("consumed")):
        return "override event is already consumed"
    if str(override_event.get("task_id") or "") != str(task_ledger.get("task_id") or ""):
        return "override task mismatch"
    if str(override_event.get("checkpoint_id") or "") != str(action.get("checkpoint_id") or ""):
        return "override checkpoint mismatch"
    if str(override_event.get("blocked_action_fingerprint") or "") != str(denial.get("action_fingerprint") or ""):
        return "override action fingerprint mismatch"
    if not str(override_event.get("denial_fingerprint") or "").strip():
        return "override requires denial fingerprint"
    if str(override_event.get("denial_fingerprint") or "") != str(denial.get("denial_fingerprint") or ""):
        return "override denial fingerprint mismatch"
    if not str(override_event.get("reason") or "").strip():
        return "override requires a reason"
    return None


def _authorize(
    task_ledger: dict[str, Any],
    action: dict[str, Any],
    history: list[dict[str, Any]],
    decision: str,
    reason: str,
    *,
    override_event_id: str | None = None,
    retry_budget_remaining: int | None = None,
) -> dict[str, Any]:
    action_fp = fingerprint_action(action)
    root_fp = fingerprint_root_cause(action)
    evidence_fp = fingerprint_evidence(action)
    input_fp = fingerprint_relevant_inputs(action)
    head = str((task_ledger.get("action_log") or {}).get("head_chain_hash") or "")
    nonce_material = f"{action_fp}|{root_fp}|{evidence_fp}|{input_fp}|{len(history)}|{decision}|{head}"
    event_nonce = hashlib.sha256(nonce_material.encode("utf-8")).hexdigest()[:24]
    receipt = build_receipt({
        "policy_version": 2,
        "task_id": str(action["task_id"]),
        "checkpoint_id": str(action["checkpoint_id"]),
        "action_fingerprint": action_fp,
        "root_cause_fingerprint": root_fp,
        "evidence_fingerprint": evidence_fp,
        "relevant_input_fingerprint": input_fp,
        "decision": decision,
        "previous_chain_hash": head,
        "event_nonce": event_nonce,
        "override_event_id": override_event_id,
    })
    result = {
        "decision": decision,
        "reason": reason,
        "action_fingerprint": action_fp,
        "root_cause_fingerprint": root_fp,
        "evidence_fingerprint": evidence_fp,
        "relevant_input_fingerprint": input_fp,
        "receipt": receipt,
    }
    if retry_budget_remaining is not None:
        result["retry_budget_remaining"] = retry_budget_remaining
    return result


def decide(
    task_ledger: dict[str, Any],
    action: dict[str, Any],
    history: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
    override_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_policy = policy or load_policy()
    if str(action.get("task_id") or "") != str(task_ledger.get("task_id") or ""):
        raise ForwardMotionV2Failure("action task_id does not match ledger task_id")

    try:
        state = validate_checkpoint_ledger(task_ledger)
    except CheckpointLedgerV2Failure as exc:
        raise ForwardMotionV2Failure(f"invalid checkpoint ledger: {exc}") from exc

    if state["task_status"] == "DONE":
        return _decision("TASK_COMPLETE", "declared finish line is already satisfied")

    def deny(decision: str, reason: str, *, retry_budget_remaining: int | None = None) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if retry_budget_remaining is not None:
            extra["retry_budget_remaining"] = retry_budget_remaining
        denial = _denial_payload(action, decision, reason, **extra)
        if override_event is None:
            return denial
        error = _validate_override_event(task_ledger, action, denial, override_event)
        if error is not None:
            return _denial_payload(
                action,
                "DENIED_UNAUTHORIZED_OVERRIDE",
                error,
                original_denial_fingerprint=denial["denial_fingerprint"],
            )
        return _authorize(
            task_ledger,
            action,
            history,
            "AUTHORIZED_USER_OVERRIDE",
            "explicit user override authorizes this exact denied action once",
            override_event_id=str(override_event["event_id"]),
            retry_budget_remaining=retry_budget_remaining,
        )

    checkpoint_id = str(action.get("checkpoint_id") or "")
    checkpoint = _checkpoint(task_ledger, checkpoint_id)
    current = str(task_ledger.get("current_checkpoint") or "")
    if checkpoint_id != current:
        if checkpoint.get("state") == "DONE" and not action.get("contradictory_evidence"):
            return deny("DENIED_CLOSED_CHECKPOINT", "closed checkpoint cannot reopen without contradictory evidence")
        if not action.get("contradictory_evidence"):
            return deny("DENIED_BACKTRACK", "action does not target the active checkpoint")

    if str(action.get("scope_relation") or "in_scope") == "unrelated":
        return _decision("DEFER_SIDE_QUEST", "finding is unrelated to the active finish line")

    active_blocker = state.get("active_blocker")
    if active_blocker and str(action.get("action_type") or "") == "open_blocker":
        requested = str((action.get("inputs") or {}).get("blocker_id") or "")
        current_blocker = str(active_blocker.get("blocker_id") or "")
        if requested and requested != current_blocker:
            return _decision("DEFER_SIDE_QUEST", "one active blocker already owns the task")

    if bool(action.get("requires_user")) and not bool(action.get("resolvable_with_available_tools", True)):
        user_action = str(action.get("user_action") or "").strip()
        if not user_action:
            raise ForwardMotionV2Failure("external blocker requires one concrete user_action")
        return _decision("STOP_EXTERNAL_BLOCKER", "blocker cannot be resolved with available tools", user_action=user_action)

    action_fp = fingerprint_action(action)
    root_fp = fingerprint_root_cause(action)
    evidence_fp = fingerprint_evidence(action)
    input_fp = fingerprint_relevant_inputs(action)
    root_matches = [item for item in history if str(item.get("root_cause_fingerprint") or "") == root_fp]
    exact_matches = [item for item in history if str(item.get("action_fingerprint") or "") == action_fp]
    unchanged_root = [
        item for item in root_matches
        if str(item.get("evidence_fingerprint") or "") == evidence_fp
        and str(item.get("relevant_input_fingerprint") or "") == input_fp
    ]

    for resolved in task_ledger.get("resolved_root_causes") or []:
        if not isinstance(resolved, dict):
            continue
        if str(resolved.get("root_cause_fingerprint") or "") != root_fp:
            continue
        closing_fp = str(resolved.get("closing_evidence_fingerprint") or "")
        if bool(action.get("contradictory_evidence")) and evidence_fp and evidence_fp != closing_fp:
            return _authorize(
                task_ledger,
                action,
                history,
                "AUTHORIZED_NEW_HYPOTHESIS",
                "new contradictory evidence invalidates the resolved root cause closing proof",
            )
        return deny("DENIED_STALE_FAILURE", "resolved root cause stays closed without new contradictory evidence")

    retry = bool(action.get("retry"))
    failure_class = str(action.get("failure_class") or "")
    budgets = active_policy.get("retry_budgets") or {}

    if retry and failure_class == "deterministic-regression":
        return deny(
            "DENIED_STALE_FAILURE",
            "deterministic failures receive zero unchanged retries",
            retry_budget_remaining=0,
        )

    if retry and failure_class == "transient-capable":
        if not bool(action.get("evidence_inspected")):
            return deny(
                "DENIED_STALE_FAILURE",
                "transient retry requires evidence inspection first",
                retry_budget_remaining=int(budgets.get("transient-capable", 1)),
            )
        allowed = int(budgets.get("transient-capable", 1))
        used = sum(bool(item.get("controlled_retry")) for item in root_matches)
        if used < allowed:
            if override_event is not None:
                return _denial_payload(action, "DENIED_UNAUTHORIZED_OVERRIDE", "override is unnecessary for an authorized controlled retry")
            return _authorize(
                task_ledger,
                action,
                history,
                "AUTHORIZED_CONTROLLED_RETRY",
                "one inspected transient-capable retry is allowed",
                retry_budget_remaining=allowed - used - 1,
            )
        return deny(
            "DENIED_STALE_FAILURE",
            "controlled transient retry budget exhausted",
            retry_budget_remaining=0,
        )

    if retry and failure_class in {"unknown", ""} and str(action.get("action_type") or "") == "gather_evidence":
        allowed = int(budgets.get("unknown_evidence_actions", 1))
        used = sum(bool(item.get("evidence_action")) for item in root_matches)
        if used >= allowed:
            return deny(
                "DENIED_STALE_FAILURE",
                "unknown failure evidence-gathering budget exhausted",
                retry_budget_remaining=0,
            )
        if override_event is not None:
            return _denial_payload(action, "DENIED_UNAUTHORIZED_OVERRIDE", "override is unnecessary for an authorized evidence action")
        return _authorize(
            task_ledger,
            action,
            history,
            "AUTHORIZED",
            "one evidence-gathering action is allowed for an unknown failure",
            retry_budget_remaining=allowed - used - 1,
        )

    if exact_matches:
        return deny("DENIED_LOOP", "exact action fingerprint already produced evidence")

    threshold = int((active_policy.get("stagnation") or {}).get("max_no_progress_actions", 3))
    same_path = [
        item for item in root_matches
        if str(item.get("relevant_input_fingerprint") or "") == input_fp
    ]
    consecutive_no_progress = 0
    for item in reversed(same_path):
        if str(item.get("progress_class") or "") != "no_progress":
            break
        consecutive_no_progress += 1
    if consecutive_no_progress >= threshold:
        return deny("DENIED_STAGNATION", f"{threshold} no-progress actions locked this root-cause path")

    if unchanged_root and not bool(action.get("new_hypothesis")):
        return deny("DENIED_STALE_FAILURE", "same root cause has no new evidence or relevant input")

    if bool(action.get("new_hypothesis")):
        if override_event is not None:
            return _denial_payload(action, "DENIED_UNAUTHORIZED_OVERRIDE", "override is unnecessary for a new hypothesis")
        return _authorize(
            task_ledger,
            action,
            history,
            "AUTHORIZED_NEW_HYPOTHESIS",
            "action tests a genuinely new discriminating hypothesis",
        )

    if override_event is not None:
        return _denial_payload(action, "DENIED_UNAUTHORIZED_OVERRIDE", "override is unnecessary for an otherwise authorized action")
    return _authorize(
        task_ledger,
        action,
        history,
        "AUTHORIZED",
        "action advances the active checkpoint with a new proof basis",
    )
