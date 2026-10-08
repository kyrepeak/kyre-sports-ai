"""API 2 Finalization Authority V1 Step 6 — 100% Finalizer.

Pure terminal convergence layer. It consumes the already-proven Step 1–5
terminal checkpoints plus the Step-5 Authority Garbage Collector result and
emits one deterministic finalization-ready packet. It performs no I/O and
grants no mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0

EXPECTED_FREEZE_TOKENS = {
    1: "API2_FINALIZATION_AUTHORITY_V1_STEP1_FROZEN",
    2: "API2_FINALIZATION_AUTHORITY_V1_STEP2_FROZEN",
    3: "API2_FINALIZATION_AUTHORITY_V1_STEP3_FROZEN",
    4: "API2_FINALIZATION_AUTHORITY_V1_STEP4_FROZEN",
    5: "API2_FINALIZATION_AUTHORITY_V1_STEP5_FROZEN",
}
_REQUIRED_STEPS = frozenset(EXPECTED_FREEZE_TOKENS)
_TERMINAL_GC_DECISIONS = {"AUTHORITY_GC_COLLECTED", "AUTHORITY_GC_ALREADY_CLEAN"}
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class Finalization100PercentFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _result(decision: str, *, finalized: bool, **extra: Any) -> dict[str, Any]:
    return {
        "decision": decision,
        "finalized": bool(finalized),
        "program_progress_percent": 100.0 if finalized else 83.3,
        "completed_prior_steps": 5 if finalized else 0,
        "total_steps": 6,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        **extra,
    }


def _checkpoint_map(checkpoints: Sequence[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for index, raw in enumerate(checkpoints):
        if not isinstance(raw, Mapping):
            raise Finalization100PercentFailure(f"checkpoint[{index}] must be an object")
        try:
            step = int(raw.get("step"))
        except (TypeError, ValueError) as exc:
            raise Finalization100PercentFailure("checkpoint step invalid") from exc
        if step in out:
            raise Finalization100PercentFailure(f"duplicate step: {step}")
        if step not in _REQUIRED_STEPS:
            raise Finalization100PercentFailure(f"unsupported step: {step}")
        item = dict(raw)
        terminal_digest = str(item.get("terminal_digest") or "").lower()
        if not _HASH64.fullmatch(terminal_digest):
            raise Finalization100PercentFailure(f"step {step} terminal_digest invalid")
        merged_main_sha = str(item.get("merged_main_sha") or "").lower()
        if not _SHA40.fullmatch(merged_main_sha):
            raise Finalization100PercentFailure(f"step {step} merged_main_sha invalid")
        if not str(item.get("task_id") or "").strip():
            raise Finalization100PercentFailure(f"step {step} task_id required")
        item["terminal_digest"] = terminal_digest
        item["merged_main_sha"] = merged_main_sha
        out[step] = item
    return out


def finalize_to_100_percent(
    *,
    checkpoints: Sequence[Mapping[str, Any]],
    authority_gc: Mapping[str, Any],
    active_thaws: Iterable[str] = (),
) -> dict[str, Any]:
    """Return the deterministic finalization-ready packet or one fail-closed state."""
    checkpoint_by_step = _checkpoint_map(checkpoints)
    missing = sorted(_REQUIRED_STEPS - set(checkpoint_by_step))
    if missing:
        return {
            "result": _result(
                "FINALIZER_WAIT_CHECKPOINTS",
                finalized=False,
                missing_steps=missing,
                next_legal_action="WAIT_FOR_CANONICAL_CHECKPOINTS",
            ),
            "receipt": None,
        }

    mismatched = [
        step
        for step, item in sorted(checkpoint_by_step.items())
        if str(item.get("freeze_token") or "") != EXPECTED_FREEZE_TOKENS[step]
    ]
    if mismatched:
        return {
            "result": _result(
                "FINALIZER_FREEZE_TOKEN_MISMATCH",
                finalized=False,
                mismatched_steps=mismatched,
                next_legal_action="RECONCILE_CANONICAL_FREEZE_TOKENS",
            ),
            "receipt": None,
        }

    blocked = [
        step
        for step, item in sorted(checkpoint_by_step.items())
        if item.get("complete") is not True or str(item.get("status") or "") != "GREEN_FROZEN"
    ]
    if blocked:
        return {
            "result": _result(
                "FINALIZER_CHECKPOINT_NOT_TERMINAL",
                finalized=False,
                blocked_steps=blocked,
                next_legal_action="WAIT_FOR_CANONICAL_CHECKPOINTS",
            ),
            "receipt": None,
        }

    if not isinstance(authority_gc, Mapping):
        raise Finalization100PercentFailure("authority_gc must be an object")
    gc_decision = str(authority_gc.get("decision") or "")
    if gc_decision not in _TERMINAL_GC_DECISIONS:
        return {
            "result": _result(
                "FINALIZER_AUTHORITY_GC_NOT_TERMINAL",
                finalized=False,
                next_legal_action="COMPLETE_AUTHORITY_GARBAGE_COLLECTION",
            ),
            "receipt": None,
        }

    try:
        remaining = int(authority_gc.get("remaining_target_mutation_authority"))
    except (TypeError, ValueError) as exc:
        raise Finalization100PercentFailure(
            "remaining_target_mutation_authority invalid"
        ) from exc
    if remaining != 0:
        return {
            "result": _result(
                "FINALIZER_AUTHORITY_REMAINS",
                finalized=False,
                remaining_target_mutation_authority=remaining,
                next_legal_action="RECONCILE_AUTHORITY_REMAINDER",
            ),
            "receipt": None,
        }

    if str(authority_gc.get("next_legal_action") or "") != "RUN_100_PERCENT_FINALIZER":
        return {
            "result": _result(
                "FINALIZER_AUTHORITY_GC_NOT_TERMINAL",
                finalized=False,
                next_legal_action="COMPLETE_AUTHORITY_GARBAGE_COLLECTION",
            ),
            "receipt": None,
        }

    gc_digest = str(authority_gc.get("receipt_digest") or "").lower()
    if not _HASH64.fullmatch(gc_digest):
        raise Finalization100PercentFailure("authority_gc receipt_digest invalid")

    thaws = sorted({str(value or "").strip() for value in active_thaws if str(value or "").strip()})
    checkpoint_terminal_digests = {
        str(step): checkpoint_by_step[step]["terminal_digest"] for step in sorted(_REQUIRED_STEPS)
    }
    checkpoint_main_shas = {
        str(step): checkpoint_by_step[step]["merged_main_sha"] for step in sorted(_REQUIRED_STEPS)
    }
    freeze_tokens = {
        str(step): EXPECTED_FREEZE_TOKENS[step] for step in sorted(_REQUIRED_STEPS)
    }
    receipt_body = {
        "version": "API2_FINALIZATION_AUTHORITY_V1_100_PERCENT_FINALIZER",
        "checkpoint_terminal_digests": checkpoint_terminal_digests,
        "checkpoint_main_shas": checkpoint_main_shas,
        "freeze_tokens": freeze_tokens,
        "authority_gc_receipt_digest": gc_digest,
        "active_thaws_preserved": thaws,
        "completed_prior_steps": 5,
        "total_steps": 6,
        "program_progress_percent": 100.0,
    }
    receipt = {**receipt_body, "receipt_digest": _digest(receipt_body)}
    return {
        "result": _result(
            "FINALIZATION_100_PERCENT_READY",
            finalized=True,
            receipt_digest=receipt["receipt_digest"],
            next_legal_action="RUNLESS_PROVE_MERGE_FREEZE_STEP6",
        ),
        "receipt": receipt,
    }
