from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .models import ProofState


class FinalizationConvergenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class FinalizationTarget:
    proof_id: str
    workstream: str
    candidate_sha: str
    freeze_token: str
    proof_digest: str


def _field(value: Mapping[str, Any] | Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _state_name(value: Any) -> str:
    raw = _field(value, "state", "")
    return str(getattr(raw, "value", raw) or "")


def _authority_superseded(value: Any) -> bool:
    detail = str(_field(value, "detail", "") or "")
    prefix = "AUTHORITY_SUPERSEDED:"
    if not detail.startswith(prefix):
        return False
    parts = detail.split(":", 2)
    return len(parts) == 3 and len(parts[1]) == 40 and bool(parts[2])


def _require_merge_authority(status: Any, target: FinalizationTarget) -> None:
    if _authority_superseded(status):
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_AUTHORITY_SUPERSEDED")
    if _state_name(status) != ProofState.MERGE_AUTHORIZED.value:
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_MERGE_NOT_AUTHORIZED")
    if str(_field(status, "proof_id", "")) != target.proof_id:
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_PROOF_ID_MISMATCH")
    if str(_field(status, "candidate_sha", "")) != target.candidate_sha:
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_CANDIDATE_MISMATCH")
    if str(_field(status, "workstream", "")) != target.workstream:
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_WORKSTREAM_MISMATCH")
    if str(_field(status, "receipt_digest", "")) != target.proof_digest.removeprefix("sha256:"):
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_PROOF_DIGEST_MISMATCH")


def converge_green_frozen(
    target: FinalizationTarget,
    *,
    state_store: Any,
    github: Any,
    merge_exact_candidate: Callable[[str], Mapping[str, Any]],
    finalize_certified_candidate: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    """Connect one exact-head Runless gate to the existing merge/freeze authorities.

    This is orchestration only. Proof publication, merge transport, ledger/frozen
    registry mutation, canonical read-back, and durable lease release remain owned
    by their existing authorities. The callbacks must be idempotent for the same
    exact candidate/freeze token; this function never creates a parallel lane.
    """
    before = state_store.status(target.proof_id)
    if _state_name(before) == ProofState.GREEN_FROZEN.value:
        return {
            "status": "GREEN_FROZEN",
            "decision": "STEP5_ALREADY_GREEN_FROZEN",
            "proof_id": target.proof_id,
            "candidate_sha": target.candidate_sha,
            "merged_main_sha": str(_field(before, "merged_main_sha", "")),
            "freeze_token": str(_field(before, "freeze_token", target.freeze_token)),
            "reused": True,
        }

    _require_merge_authority(before, target)

    merge = dict(merge_exact_candidate(target.candidate_sha))
    if merge.get("candidate_sha") != target.candidate_sha:
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_MERGE_CANDIDATE_MISMATCH")
    merged_main_sha = str(merge.get("merged_main_sha") or "")
    if len(merged_main_sha) != 40:
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_MERGED_MAIN_INVALID")
    if github.main_sha() != merged_main_sha:
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_MERGED_MAIN_READBACK_MISMATCH")

    packet = {
        "proof_id": target.proof_id,
        "workstream": target.workstream,
        "candidate_sha": target.candidate_sha,
        "merged_main_sha": merged_main_sha,
        "freeze_token": target.freeze_token,
        "proof_digest": target.proof_digest,
    }
    finalized = dict(finalize_certified_candidate(packet))
    if finalized.get("status") != "GREEN_FROZEN":
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_FREEZE_NOT_TERMINAL")

    durable = state_store.closeout_green_frozen(
        target.proof_id,
        candidate_sha=target.candidate_sha,
        merged_main_sha=merged_main_sha,
        freeze_token=target.freeze_token,
        proof_digest=target.proof_digest,
        manifest_state_hash=str(finalized.get("manifest_state_hash") or ""),
    )
    readback = state_store.status(target.proof_id)
    if _state_name(durable) != ProofState.GREEN_FROZEN.value or _state_name(readback) != ProofState.GREEN_FROZEN.value:
        raise FinalizationConvergenceError("RUNLESS_V2_STEP5_CANONICAL_READBACK_FAILED")

    return {
        "status": "GREEN_FROZEN",
        "decision": "STEP5_CONVERGENCE_GREEN_FROZEN",
        "proof_id": target.proof_id,
        "candidate_sha": target.candidate_sha,
        "merged_main_sha": merged_main_sha,
        "freeze_token": target.freeze_token,
        "reused": False,
    }
