"""MONSTER V4 Step 5 — Terminal Proof Receipt V1.

A terminal receipt collapses the final proof chain into one tamper-evident
object bound to the exact candidate SHA, authoritative workflow run, test
count, required lane results, scope diff, and freeze tokens.

The receipt is proof material only. It never mutates product runtime and it
never replaces the distributed lease, frozen-artifact registry, cross-chat
truth handshake, or GitHub's devsystem-final-gate.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

VERSION = "MONSTER_V4_TERMINAL_PROOF_RECEIPT_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_LANE_RESULTS = {"success", "skipped"}


class TerminalProofReceiptFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    sha = str(value or "").strip().lower()
    if not _SHA40.fullmatch(sha):
        raise TerminalProofReceiptFailure(f"{field} must be a full 40-character SHA")
    return sha


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise TerminalProofReceiptFailure(f"{field} is required")
    return text


def _normalize_lanes(lanes: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(lanes, Mapping) or not lanes:
        raise TerminalProofReceiptFailure("required_lanes must be a non-empty object")
    normalized: dict[str, str] = {}
    for raw_name, raw_result in lanes.items():
        name = _nonempty(raw_name, "lane name")
        result = str(raw_result or "").strip().lower()
        if result not in _ALLOWED_LANE_RESULTS:
            raise TerminalProofReceiptFailure(
                f"{name}: terminal lane must be success or skipped, got {result!r}"
            )
        normalized[name] = result
    return dict(sorted(normalized.items()))


def _normalize_unique(values: Sequence[Any], field: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        raise TerminalProofReceiptFailure(f"{field} must be a non-empty sequence")
    normalized = [_nonempty(item, field) for item in values]
    if len(set(normalized)) != len(normalized):
        raise TerminalProofReceiptFailure(f"{field} contains duplicates")
    return sorted(normalized)


def build_receipt(
    *,
    repository: str,
    checkpoint_id: str,
    head_sha: str,
    authoritative_run: int,
    authoritative_workflow: str,
    test_count: int,
    required_lanes: Mapping[str, Any],
    scope_diff: Sequence[str],
    freeze_tokens: Sequence[str],
) -> dict[str, Any]:
    repo = _nonempty(repository, "repository").lower()
    if "/" not in repo:
        raise TerminalProofReceiptFailure("repository must be owner/name")
    run = int(authoritative_run)
    tests = int(test_count)
    if run <= 0:
        raise TerminalProofReceiptFailure("authoritative_run must be positive")
    if tests < 0:
        raise TerminalProofReceiptFailure("test_count cannot be negative")

    body = {
        "schema_version": 1,
        "version": VERSION,
        "repository": repo,
        "checkpoint_id": _nonempty(checkpoint_id, "checkpoint_id"),
        "head_sha": _sha(head_sha, "head_sha"),
        "authoritative_run": run,
        "authoritative_workflow": _nonempty(
            authoritative_workflow, "authoritative_workflow"
        ),
        "test_count": tests,
        "required_lanes": _normalize_lanes(required_lanes),
        "scope_diff": _normalize_unique(scope_diff, "scope_diff"),
        "freeze_tokens": _normalize_unique(freeze_tokens, "freeze_tokens"),
    }
    body["receipt_hash"] = _hash(body)
    return validate_receipt(body)


def validate_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TerminalProofReceiptFailure("receipt must be an object")
    receipt = deepcopy(dict(payload))
    required = {
        "schema_version",
        "version",
        "repository",
        "checkpoint_id",
        "head_sha",
        "authoritative_run",
        "authoritative_workflow",
        "test_count",
        "required_lanes",
        "scope_diff",
        "freeze_tokens",
        "receipt_hash",
    }
    missing = sorted(required - set(receipt))
    if missing:
        raise TerminalProofReceiptFailure(
            "receipt missing fields: " + ", ".join(missing)
        )
    if int(receipt["schema_version"]) != 1:
        raise TerminalProofReceiptFailure("receipt schema mismatch")
    if receipt["version"] != VERSION:
        raise TerminalProofReceiptFailure("receipt version mismatch")
    if "/" not in _nonempty(receipt["repository"], "repository"):
        raise TerminalProofReceiptFailure("repository must be owner/name")
    _nonempty(receipt["checkpoint_id"], "checkpoint_id")
    _sha(receipt["head_sha"], "head_sha")
    if int(receipt["authoritative_run"]) <= 0:
        raise TerminalProofReceiptFailure("authoritative_run must be positive")
    _nonempty(receipt["authoritative_workflow"], "authoritative_workflow")
    if int(receipt["test_count"]) < 0:
        raise TerminalProofReceiptFailure("test_count cannot be negative")

    lanes = _normalize_lanes(receipt["required_lanes"])
    scope = _normalize_unique(receipt["scope_diff"], "scope_diff")
    tokens = _normalize_unique(receipt["freeze_tokens"], "freeze_tokens")
    if receipt["required_lanes"] != lanes:
        raise TerminalProofReceiptFailure("required_lanes must be canonical")
    if receipt["scope_diff"] != scope:
        raise TerminalProofReceiptFailure("scope_diff must be canonical")
    if receipt["freeze_tokens"] != tokens:
        raise TerminalProofReceiptFailure("freeze_tokens must be canonical")

    digest = str(receipt["receipt_hash"] or "").strip().lower()
    if not _HASH64.fullmatch(digest):
        raise TerminalProofReceiptFailure("receipt_hash must be sha256")
    unsigned = deepcopy(receipt)
    unsigned.pop("receipt_hash", None)
    expected = _hash(unsigned)
    if digest != expected:
        raise TerminalProofReceiptFailure("terminal receipt hash mismatch")

    return {
        "status": "GREEN",
        "version": VERSION,
        "receipt_hash": expected,
        "head_sha": receipt["head_sha"],
        "authoritative_run": int(receipt["authoritative_run"]),
        "test_count": int(receipt["test_count"]),
        "required_lane_count": len(lanes),
        "scope_file_count": len(scope),
        "freeze_token_count": len(tokens),
    }


def verify_terminal_receipt(
    receipt: Mapping[str, Any],
    *,
    expected_head_sha: str,
    expected_authoritative_run: int,
    expected_required_lanes: Mapping[str, Any],
    expected_scope_diff: Sequence[str],
    expected_freeze_tokens: Sequence[str],
) -> dict[str, Any]:
    validated = validate_receipt(receipt)
    expected_sha = _sha(expected_head_sha, "expected_head_sha")
    expected_run = int(expected_authoritative_run)
    expected_lanes = _normalize_lanes(expected_required_lanes)
    expected_scope = _normalize_unique(expected_scope_diff, "expected_scope_diff")
    expected_tokens = _normalize_unique(expected_freeze_tokens, "expected_freeze_tokens")

    mismatches: list[str] = []
    if receipt["head_sha"] != expected_sha:
        mismatches.append("head_sha")
    if int(receipt["authoritative_run"]) != expected_run:
        mismatches.append("authoritative_run")
    if receipt["required_lanes"] != expected_lanes:
        mismatches.append("required_lanes")
    if receipt["scope_diff"] != expected_scope:
        mismatches.append("scope_diff")
    if receipt["freeze_tokens"] != expected_tokens:
        mismatches.append("freeze_tokens")
    if mismatches:
        raise TerminalProofReceiptFailure(
            "terminal receipt does not match expected proof: " + ", ".join(mismatches)
        )

    return {
        **validated,
        "decision": "TERMINAL_PROOF_RECEIPT_VERIFIED",
        "exact_sha_bound": True,
        "authoritative_run_bound": True,
        "required_lanes_bound": True,
        "scope_diff_bound": True,
        "freeze_tokens_bound": True,
    }


def contract_self_test() -> dict[str, Any]:
    sha = "1" * 40
    lanes = {
        "permanent-contract": "success",
        "devsystem-final-gate": "success",
        "browser-qa": "skipped",
    }
    scope = [
        "devsystem/terminal_proof_receipt_v1.py",
        "tests/test_devsystem_terminal_proof_receipt_v1.py",
    ]
    tokens = [
        "MONSTER_V4_STEP5_GREEN",
        "MONSTER_V4_STEP5_FROZEN",
    ]
    receipt = build_receipt(
        repository="owner/repo",
        checkpoint_id="MONSTER_V4_STEP5",
        head_sha=sha,
        authoritative_run=5005,
        authoritative_workflow="DevSystem targeted CI",
        test_count=125,
        required_lanes=lanes,
        scope_diff=scope,
        freeze_tokens=tokens,
    )
    verified = verify_terminal_receipt(
        receipt,
        expected_head_sha=sha,
        expected_authoritative_run=5005,
        expected_required_lanes=lanes,
        expected_scope_diff=scope,
        expected_freeze_tokens=tokens,
    )

    tampered = deepcopy(receipt)
    tampered["test_count"] = 126
    hash_tamper_rejected = False
    try:
        validate_receipt(tampered)
    except TerminalProofReceiptFailure:
        hash_tamper_rejected = True

    stale_sha_receipt = build_receipt(
        repository="owner/repo",
        checkpoint_id="MONSTER_V4_STEP5",
        head_sha="2" * 40,
        authoritative_run=5005,
        authoritative_workflow="DevSystem targeted CI",
        test_count=125,
        required_lanes=lanes,
        scope_diff=scope,
        freeze_tokens=tokens,
    )
    stale_sha_rejected = False
    try:
        verify_terminal_receipt(
            stale_sha_receipt,
            expected_head_sha=sha,
            expected_authoritative_run=5005,
            expected_required_lanes=lanes,
            expected_scope_diff=scope,
            expected_freeze_tokens=tokens,
        )
    except TerminalProofReceiptFailure:
        stale_sha_rejected = True

    stale_run_receipt = build_receipt(
        repository="owner/repo",
        checkpoint_id="MONSTER_V4_STEP5",
        head_sha=sha,
        authoritative_run=5004,
        authoritative_workflow="DevSystem targeted CI",
        test_count=125,
        required_lanes=lanes,
        scope_diff=scope,
        freeze_tokens=tokens,
    )
    stale_run_rejected = False
    try:
        verify_terminal_receipt(
            stale_run_receipt,
            expected_head_sha=sha,
            expected_authoritative_run=5005,
            expected_required_lanes=lanes,
            expected_scope_diff=scope,
            expected_freeze_tokens=tokens,
        )
    except TerminalProofReceiptFailure:
        stale_run_rejected = True

    failed_lane_rejected = False
    try:
        build_receipt(
            repository="owner/repo",
            checkpoint_id="MONSTER_V4_STEP5",
            head_sha=sha,
            authoritative_run=5005,
            authoritative_workflow="DevSystem targeted CI",
            test_count=125,
            required_lanes={"devsystem-final-gate": "failure"},
            scope_diff=scope,
            freeze_tokens=tokens,
        )
    except TerminalProofReceiptFailure:
        failed_lane_rejected = True

    scope_drift_receipt = build_receipt(
        repository="owner/repo",
        checkpoint_id="MONSTER_V4_STEP5",
        head_sha=sha,
        authoritative_run=5005,
        authoritative_workflow="DevSystem targeted CI",
        test_count=125,
        required_lanes=lanes,
        scope_diff=scope + ["unexpected.py"],
        freeze_tokens=tokens,
    )
    scope_drift_rejected = False
    try:
        verify_terminal_receipt(
            scope_drift_receipt,
            expected_head_sha=sha,
            expected_authoritative_run=5005,
            expected_required_lanes=lanes,
            expected_scope_diff=scope,
            expected_freeze_tokens=tokens,
        )
    except TerminalProofReceiptFailure:
        scope_drift_rejected = True

    token_drift_receipt = build_receipt(
        repository="owner/repo",
        checkpoint_id="MONSTER_V4_STEP5",
        head_sha=sha,
        authoritative_run=5005,
        authoritative_workflow="DevSystem targeted CI",
        test_count=125,
        required_lanes=lanes,
        scope_diff=scope,
        freeze_tokens=["MONSTER_V4_STEP5_GREEN"],
    )
    token_drift_rejected = False
    try:
        verify_terminal_receipt(
            token_drift_receipt,
            expected_head_sha=sha,
            expected_authoritative_run=5005,
            expected_required_lanes=lanes,
            expected_scope_diff=scope,
            expected_freeze_tokens=tokens,
        )
    except TerminalProofReceiptFailure:
        token_drift_rejected = True

    result = {
        "status": "GREEN",
        "version": VERSION,
        "single_terminal_object": True,
        "exact_sha_bound": verified["exact_sha_bound"],
        "authoritative_run_bound": verified["authoritative_run_bound"],
        "test_count_bound": receipt["test_count"] == 125,
        "required_lanes_bound": verified["required_lanes_bound"],
        "scope_diff_bound": verified["scope_diff_bound"],
        "freeze_tokens_bound": verified["freeze_tokens_bound"],
        "receipt_hash_tamper_rejected": hash_tamper_rejected,
        "stale_sha_rejected": stale_sha_rejected,
        "stale_run_rejected": stale_run_rejected,
        "failed_lane_rejected": failed_lane_rejected,
        "scope_drift_rejected": scope_drift_rejected,
        "freeze_token_drift_rejected": token_drift_rejected,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = [
        key for key, value in result.items()
        if isinstance(value, bool)
        and key not in {"network_calls", "auto_mutate", "product_runtime_mutation"}
    ]
    if not all(result[key] is True for key in required):
        raise TerminalProofReceiptFailure("terminal proof receipt self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["product_runtime_mutation"]:
        raise TerminalProofReceiptFailure("terminal proof receipt safety invariant failed")
    return result


def main() -> int:
    print("MONSTER_V4_TERMINAL_PROOF_RECEIPT_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TerminalProofReceiptFailure as exc:
        print(f"MONSTER_V4_TERMINAL_PROOF_RECEIPT_V1_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1)
