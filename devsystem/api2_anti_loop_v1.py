"""API2 anti-loop failure ledger, polling guard, and retry authorization."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

VERSION = "API2_ANTI_LOOP_V2"


class AntiLoopError(RuntimeError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def action_fingerprint(action: Mapping[str, Any]) -> str:
    return _digest(dict(action))


def evidence_fingerprint(evidence: Sequence[Any]) -> str:
    return _digest(list(evidence))


def hypothesis_fingerprint(hypothesis: str) -> str:
    return _digest(str(hypothesis or ""))


def record_failure(
    state: Mapping[str, Any],
    *,
    action: Mapping[str, Any],
    evidence: Sequence[Any],
    hypothesis: str,
    classification: str | None = None,
) -> dict[str, Any]:
    out = deepcopy(dict(state))
    failures = deepcopy(dict(out.get("failures") or {}))
    fp = action_fingerprint(action)
    prior = failures.get(fp)
    hard = bool(str(classification or "").strip())
    if prior is not None and (hard or prior.get("permanent_exclusion") is True):
        raise AntiLoopError("API2_FAILURE_ALREADY_RECORDED")
    failures[fp] = {
        "action": deepcopy(dict(action)),
        "evidence_digest": evidence_fingerprint(evidence),
        "hypothesis_digest": hypothesis_fingerprint(hypothesis),
        "hypothesis": str(hypothesis or ""),
        "classification": str(classification or "UNCLASSIFIED"),
        "permanent_exclusion": hard,
    }
    out["failures"] = failures
    out["blocked_action_fingerprint"] = fp
    return out


def authorize_retry(
    state: Mapping[str, Any],
    *,
    action: Mapping[str, Any],
    evidence: Sequence[Any],
    hypothesis: str,
) -> dict[str, Any]:
    fp = action_fingerprint(action)
    prior = (state.get("failures") or {}).get(fp)
    if prior is None:
        return {
            "allowed": True,
            "decision": "NEW_ACTION",
            "action_fingerprint": fp,
            "next_phase": "STEP_2B",
        }
    if prior.get("permanent_exclusion") is True:
        return {
            "allowed": False,
            "decision": "FAILED_ACTION_PERMANENTLY_EXCLUDED",
            "action_fingerprint": fp,
            "classification": prior.get("classification"),
            "next_phase": "STEP_2C",
        }
    new_evidence = evidence_fingerprint(evidence)
    new_hypothesis = hypothesis_fingerprint(hypothesis)
    evidence_changed = new_evidence != prior.get("evidence_digest")
    hypothesis_changed = new_hypothesis != prior.get("hypothesis_digest")
    allowed = evidence_changed and hypothesis_changed
    return {
        "allowed": allowed,
        "decision": "EVIDENCE_BACKED_RETRY" if allowed else "BLIND_REPEAT_BLOCKED",
        "action_fingerprint": fp,
        "evidence_changed": evidence_changed,
        "hypothesis_changed": hypothesis_changed,
        "next_phase": "STEP_2B" if allowed else "STEP_2C",
    }


def authorize_poll(
    state: Mapping[str, Any],
    *,
    operation_id: str,
    observed_state: str,
    observed_revision: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not operation_id:
        raise AntiLoopError("API2_POLL_OPERATION_ID_MISSING")
    out = deepcopy(dict(state))
    polls = deepcopy(dict(out.get("poll_observations") or {}))
    observation = {
        "observed_state": str(observed_state),
        "observed_revision": str(observed_revision),
    }
    prior = polls.get(operation_id)
    if prior == observation:
        return out, {
            "allowed": False,
            "decision": "SAME_STATE_POLL_BLOCKED",
            "operation_id": operation_id,
            **observation,
        }
    polls[operation_id] = observation
    out["poll_observations"] = polls
    return out, {
        "allowed": True,
        "decision": "FIRST_OBSERVATION" if prior is None else "OBSERVATION_CHANGED",
        "operation_id": operation_id,
        **observation,
    }


def _state_digest(state: Mapping[str, Any]) -> str:
    data = deepcopy(dict(state))
    data.pop("state_digest", None)
    return "sha256:" + _digest(data)


def state_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(state))
    out["state_digest"] = _state_digest(out)
    return out


def restore_state(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(snapshot))
    stored = str(out.get("state_digest") or "")
    if not stored or stored != _state_digest(out):
        raise AntiLoopError("API2_ANTI_LOOP_SNAPSHOT_DIGEST_MISMATCH")
    return out
