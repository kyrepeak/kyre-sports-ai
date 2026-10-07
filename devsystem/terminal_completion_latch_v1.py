"""API 2 Finalization Authority V1 Step 3 — terminal completion latch.

Canonical completion comes only from Step 1's resolver. Once an exact terminal
completion tuple exists, duplicate finalization work is short-circuited before
proof, merge, freeze, deploy, or ledger re-check can reopen the task.

This module is deliberately pure and non-mutating.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from devsystem.canonical_completion_resolver_v1 import resolve_completion

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0

_READ_ONLY_ACTIONS = {"READ_CANONICAL_STATE"}


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _terminal_digest(canonical: Mapping[str, Any]) -> str:
    payload = {
        "task_id": str(canonical.get("task_id") or ""),
        "freeze_token": str(canonical.get("frozen_token") or ""),
        "candidate_sha": str(canonical.get("candidate_sha") or ""),
        "receipt_digest": str(canonical.get("receipt_digest") or ""),
        "merged_main_sha": str(canonical.get("merged_main_sha") or ""),
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _result(
    decision: str,
    *,
    allowed: bool,
    short_circuit: bool,
    canonical_completion: Mapping[str, Any],
    terminal_digest: str | None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "decision": decision,
        "allowed": bool(allowed),
        "short_circuit": bool(short_circuit),
        "canonical_completion": dict(canonical_completion),
        "terminal_digest": terminal_digest,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        **extra,
    }


def evaluate_terminal_latch(
    *,
    task_id: str,
    freeze_token: str,
    ledger: Mapping[str, Any],
    registry: Mapping[str, Any],
    receipt: Mapping[str, Any],
    gate: Mapping[str, Any],
    merge_evidence: Mapping[str, Any],
    requested_action: str,
    reopen_authorization: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the one legal decision for work aimed at a terminal task.

    Terminal truth is derived from Step 1 only. A stale ledger never reopens the
    task. Reopening requires both an explicit thaw identity and a distinct new
    task id; the old terminal tuple remains immutable and is carried forward by
    digest for provenance.
    """
    action = str(requested_action or "").strip().upper()
    canonical = resolve_completion(
        task_id=task_id,
        freeze_token=freeze_token,
        ledger=ledger,
        registry=registry,
        receipt=receipt,
        gate=gate,
        merge_evidence=merge_evidence,
    )

    if canonical.get("complete") is not True:
        return _result(
            "TERMINAL_LATCH_OPEN",
            allowed=True,
            short_circuit=False,
            canonical_completion=canonical,
            terminal_digest=None,
            duplicate_work_blocked=False,
            next_legal_action="CONTINUE_CURRENT_TASK",
        )

    digest = _terminal_digest(canonical)

    if action in _READ_ONLY_ACTIONS:
        return _result(
            "TERMINAL_LATCH_READ_ONLY",
            allowed=True,
            short_circuit=True,
            canonical_completion=canonical,
            terminal_digest=digest,
            duplicate_work_blocked=True,
            next_legal_action="RETURN_CANONICAL_TERMINAL_STATE",
        )

    reopen = dict(reopen_authorization or {})
    if reopen:
        mode = str(reopen.get("mode") or "").strip().upper()
        thaw_id = str(reopen.get("thaw_id") or "").strip()
        new_task_id = str(reopen.get("new_task_id") or "").strip()
        if (
            mode == "EXPLICIT_THAW"
            and thaw_id
            and new_task_id
            and new_task_id != str(task_id)
        ):
            return _result(
                "TERMINAL_LATCH_REOPEN_AUTHORIZED",
                allowed=True,
                short_circuit=False,
                canonical_completion=canonical,
                terminal_digest=digest,
                duplicate_work_blocked=False,
                reopen_from_terminal_digest=digest,
                thaw_id=thaw_id,
                new_task_id=new_task_id,
                next_legal_action="START_NEW_TASK_UNDER_EXPLICIT_THAW",
            )
        return _result(
            "TERMINAL_LATCH_REOPEN_BLOCKED",
            allowed=False,
            short_circuit=True,
            canonical_completion=canonical,
            terminal_digest=digest,
            duplicate_work_blocked=True,
            next_legal_action="MOVE_TO_NEXT_STEP",
        )

    return _result(
        "TERMINAL_LATCH_ALREADY_COMPLETE",
        allowed=False,
        short_circuit=True,
        canonical_completion=canonical,
        terminal_digest=digest,
        duplicate_work_blocked=True,
        next_legal_action="MOVE_TO_NEXT_STEP",
    )
