"""API 2 Finalization Authority V1 Step 2 — canonical ledger auto-heal planner.

Canonical completion is established only by Step 1's frozen-registry + Runless
resolver. This module is deliberately pure: it may plan an idempotent metadata
repair for a stale task ledger, but it never writes the ledger itself and it
cannot manufacture terminal completion from ledger state.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from devsystem.canonical_completion_resolver_v1 import resolve_completion

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0


def _result(decision: str, *, canonical: Mapping[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "decision": decision,
        "write_required": False,
        "healed_ledger": None,
        "canonical_completion": dict(canonical or {}),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        **extra,
    }


def resolve_and_plan_ledger_autoheal(
    *,
    task_id: str,
    freeze_token: str,
    ledger: Mapping[str, Any],
    registry: Mapping[str, Any],
    receipt: Mapping[str, Any],
    gate: Mapping[str, Any],
    merge_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Plan one ledger repair only after canonical terminal truth is proven.

    The input ledger is never mutated. A mismatched ledger identity fails closed.
    An already-aligned ledger is a no-op. A stale ledger receives only terminal
    metadata copied from the canonical completion result.
    """

    if not isinstance(ledger, Mapping) or str(ledger.get("task_id") or "") != str(task_id):
        return _result("LEDGER_AUTOHEAL_IDENTITY_MISMATCH")

    freeze_exit = ledger.get("freeze_exit")
    ledger_token = (
        str(freeze_exit.get("frozen_token") or "")
        if isinstance(freeze_exit, Mapping)
        else ""
    )
    if ledger_token and ledger_token != str(freeze_token):
        return _result("LEDGER_AUTOHEAL_IDENTITY_MISMATCH")

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
        return _result("LEDGER_AUTOHEAL_BLOCKED", canonical=canonical)

    claimed = ledger.get("green_plus_frozen_claimed") is True
    exit_claimed = isinstance(freeze_exit, Mapping) and freeze_exit.get("claimed") is True
    if str(ledger.get("status") or "") == "DONE" and claimed and exit_claimed and ledger_token == str(freeze_token):
        result = _result("LEDGER_ALREADY_ALIGNED", canonical=canonical)
        result["healed_ledger"] = deepcopy(dict(ledger))
        return result

    healed = deepcopy(dict(ledger))
    healed["status"] = "DONE"
    healed["green_plus_frozen_claimed"] = True

    healed_exit = deepcopy(dict(freeze_exit)) if isinstance(freeze_exit, Mapping) else {}
    healed_exit["frozen_token"] = str(freeze_token)
    healed_exit["claimed"] = True
    healed["freeze_exit"] = healed_exit

    healed["canonical_completion"] = {
        "authority": str(canonical.get("authority") or ""),
        "freeze_token": str(freeze_token),
        "merged_main_sha": str(canonical.get("merged_main_sha") or ""),
        "receipt_digest": str(canonical.get("receipt_digest") or ""),
        "registry_revision": canonical.get("registry_revision"),
        "registry_state_hash": str(canonical.get("registry_state_hash") or ""),
    }

    result = _result("LEDGER_AUTOHEAL_PLANNED", canonical=canonical)
    result["write_required"] = True
    result["healed_ledger"] = healed
    return result
