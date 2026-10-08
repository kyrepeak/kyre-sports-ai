"""API 2 Finalization Authority V1 Step 5 — Authority Garbage Collector.

Retires mutation-capable authority for canonically completed workstreams while
preserving unrelated/current authority and immutable proof evidence.

This module is pure and side-effect free: it mutates only a copied in-memory
snapshot supplied by the caller. It performs no network calls and grants no
ambient mutation authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0

_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_HASH40 = re.compile(r"^[0-9a-f]{40}$")
_RETIRED = "RETIRED"


class AuthorityGarbageCollectorFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise AuthorityGarbageCollectorFailure(f"{field} is required")
    return text


def _completion_ready(record: Mapping[str, Any]) -> bool:
    digest = str(record.get("terminal_digest") or "").lower()
    main_sha = str(record.get("source_main_sha") or "").lower()
    return (
        record.get("complete") is True
        and bool(_HASH64.fullmatch(digest))
        and bool(_HASH40.fullmatch(main_sha))
    )


def _base_result(decision: str, **extra: Any) -> dict[str, Any]:
    return {
        "decision": decision,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        **extra,
    }


def _validate_authorities(authorities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(authorities):
        if not isinstance(raw, Mapping):
            raise AuthorityGarbageCollectorFailure(f"authority[{index}] must be an object")
        item = deepcopy(dict(raw))
        authority_id = _text(item.get("authority_id"), f"authority[{index}].authority_id")
        if authority_id in seen:
            raise AuthorityGarbageCollectorFailure(f"duplicate authority_id: {authority_id}")
        seen.add(authority_id)
        _text(item.get("workstream"), f"authority[{index}].workstream")
        _text(item.get("authority_type"), f"authority[{index}].authority_type")
        _text(item.get("state"), f"authority[{index}].state")
        if not isinstance(item.get("mutation_capable"), bool):
            raise AuthorityGarbageCollectorFailure(
                f"authority[{index}].mutation_capable must be bool"
            )
        if not isinstance(item.get("immutable_evidence"), bool):
            raise AuthorityGarbageCollectorFailure(
                f"authority[{index}].immutable_evidence must be bool"
            )
        copied.append(item)
    return copied


def _is_live_target_mutation(item: Mapping[str, Any], targets: set[str]) -> bool:
    return (
        str(item.get("workstream")) in targets
        and item.get("mutation_capable") is True
        and item.get("immutable_evidence") is not True
        and str(item.get("state") or "").upper() != _RETIRED
    )


def collect_authority_garbage(
    *,
    target_workstreams: Iterable[str],
    canonical_completion: Mapping[str, Mapping[str, Any]],
    authorities: Sequence[Mapping[str, Any]],
    protected_authority_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Retire stale mutation authority for canonically terminal workstreams.

    Collection is atomic from the caller's point of view: if canonical terminal
    truth is incomplete, duplicate authority identities exist, or a protected
    target authority remains live, no authority record is changed.
    """
    targets = sorted({_text(value, "target_workstream") for value in target_workstreams})
    if not targets:
        raise AuthorityGarbageCollectorFailure("target_workstreams is required")
    if not isinstance(canonical_completion, Mapping):
        raise AuthorityGarbageCollectorFailure("canonical_completion must be an object")

    snapshot = _validate_authorities(authorities)
    protected = {_text(value, "protected_authority_id") for value in protected_authority_ids}

    terminal_digests: dict[str, str] = {}
    source_main_shas: dict[str, str] = {}
    for workstream in targets:
        record = canonical_completion.get(workstream)
        if not isinstance(record, Mapping) or not _completion_ready(record):
            return {
                "result": _base_result(
                    "AUTHORITY_GC_WAIT_CANONICAL_COMPLETION",
                    mutation_count=0,
                    remaining_target_mutation_authority=sum(
                        1 for item in snapshot if _is_live_target_mutation(item, set(targets))
                    ),
                    unrelated_authority_preserved=True,
                    immutable_evidence_preserved=True,
                    next_legal_action="WAIT_FOR_CANONICAL_COMPLETION",
                ),
                "authorities": snapshot,
                "receipt": None,
            }
        terminal_digests[workstream] = str(record["terminal_digest"]).lower()
        source_main_shas[workstream] = str(record["source_main_sha"]).lower()

    target_set = set(targets)
    protected_live = sorted(
        str(item["authority_id"])
        for item in snapshot
        if str(item["authority_id"]) in protected and _is_live_target_mutation(item, target_set)
    )
    if protected_live:
        return {
            "result": _base_result(
                "AUTHORITY_GC_PROTECTED_AUTHORITY_REMAINS",
                mutation_count=0,
                remaining_target_mutation_authority=sum(
                    1 for item in snapshot if _is_live_target_mutation(item, target_set)
                ),
                protected_authority_ids=protected_live,
                unrelated_authority_preserved=True,
                immutable_evidence_preserved=True,
                next_legal_action="RECONCILE_PROTECTED_AUTHORITY",
            ),
            "authorities": snapshot,
            "receipt": None,
        }

    retired_ids: list[str] = []
    retained_ids: list[str] = []
    for item in snapshot:
        authority_id = str(item["authority_id"])
        if _is_live_target_mutation(item, target_set):
            workstream = str(item["workstream"])
            item["state"] = _RETIRED
            item["retired_reason"] = "CANONICAL_TERMINAL_COMPLETION"
            item["retired_by_terminal_digest"] = terminal_digests[workstream]
            item["retired_source_main_sha"] = source_main_shas[workstream]
            retired_ids.append(authority_id)
        else:
            retained_ids.append(authority_id)

    snapshot.sort(key=lambda item: str(item["authority_id"]))
    retired_ids.sort()
    retained_ids.sort()
    remaining = sum(1 for item in snapshot if _is_live_target_mutation(item, target_set))

    receipt_body = {
        "target_workstreams": targets,
        "terminal_digests": dict(sorted(terminal_digests.items())),
        "source_main_shas": dict(sorted(source_main_shas.items())),
        "retired_authority_ids": retired_ids,
        "retained_authority_ids": retained_ids,
        "remaining_target_mutation_authority": remaining,
    }
    receipt = {**receipt_body, "receipt_digest": _digest(receipt_body)}

    decision = "AUTHORITY_GC_COLLECTED" if retired_ids else "AUTHORITY_GC_ALREADY_CLEAN"
    return {
        "result": _base_result(
            decision,
            mutation_count=len(retired_ids),
            remaining_target_mutation_authority=remaining,
            unrelated_authority_preserved=True,
            immutable_evidence_preserved=True,
            next_legal_action=(
                "RUN_100_PERCENT_FINALIZER" if remaining == 0 else "RECONCILE_AUTHORITY_REMAINDER"
            ),
            receipt_digest=receipt["receipt_digest"],
        ),
        "authorities": snapshot,
        "receipt": receipt,
    }
