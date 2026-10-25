"""API2 anti-loop failure ledger and retry authorization."""
from __future__ import annotations
import hashlib, json
from copy import deepcopy
from typing import Any, Mapping, Sequence
VERSION = "API2_ANTI_LOOP_V1"

def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()

def action_fingerprint(action: Mapping[str, Any]) -> str:
    return _digest(dict(action))
def evidence_fingerprint(evidence: Sequence[Any]) -> str:
    return _digest(list(evidence))
def hypothesis_fingerprint(hypothesis: str) -> str:
    return _digest(str(hypothesis or ""))

def record_failure(state: Mapping[str, Any], *, action: Mapping[str, Any], evidence: Sequence[Any], hypothesis: str) -> dict[str, Any]:
    out = deepcopy(dict(state)); failures = deepcopy(dict(out.get("failures") or {})); fp = action_fingerprint(action)
    failures[fp] = {"action": deepcopy(dict(action)), "evidence_digest": evidence_fingerprint(evidence), "hypothesis_digest": hypothesis_fingerprint(hypothesis), "hypothesis": str(hypothesis or "")}
    out["failures"] = failures; out["blocked_action_fingerprint"] = fp
    return out

def authorize_retry(state: Mapping[str, Any], *, action: Mapping[str, Any], evidence: Sequence[Any], hypothesis: str) -> dict[str, Any]:
    fp = action_fingerprint(action); prior = (state.get("failures") or {}).get(fp)
    if prior is None:
        return {"allowed": True, "decision": "NEW_ACTION", "action_fingerprint": fp, "next_phase": "STEP_2B"}
    new_evidence = evidence_fingerprint(evidence); new_hypothesis = hypothesis_fingerprint(hypothesis)
    evidence_changed = new_evidence != prior.get("evidence_digest"); hypothesis_changed = new_hypothesis != prior.get("hypothesis_digest")
    allowed = evidence_changed and hypothesis_changed
    return {"allowed": allowed, "decision": "EVIDENCE_BACKED_RETRY" if allowed else "BLIND_REPEAT_BLOCKED", "action_fingerprint": fp, "evidence_changed": evidence_changed, "hypothesis_changed": hypothesis_changed, "next_phase": "STEP_2B" if allowed else "STEP_2C"}
