"""MONSTER V4 Step 6 — Regression-Debt-Zero Gate V1.

A resolved real failure may not reach a freeze checkpoint unless the repair
leaves a permanent regression test or contract behind. STALE and EXTERNAL
observations never create repair debt because they do not authorize a repository
patch in the Failure Ownership Engine.

Dependency-light, fail-closed, no network calls, no product/runtime mutation.
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

VERSION = "MONSTER_V4_REGRESSION_DEBT_ZERO_GATE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

REAL_FAILURE_OWNERS = frozenset({"PRODUCT", "VERIFIER", "CI", "DEPLOYMENT"})
NON_REPAIR_OWNERS = frozenset({"STALE", "EXTERNAL"})
ALLOWED_GUARD_KINDS = frozenset({"TEST", "CONTRACT"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")


class RegressionDebtFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RegressionDebtFailure(f"{field} is required")
    return text


def _sha(value: Any, field: str) -> str:
    sha = str(value or "").strip().lower()
    if not _SHA40.fullmatch(sha):
        raise RegressionDebtFailure(f"{field} must be a full 40-character SHA")
    return sha


def _normalize_guard(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise RegressionDebtFailure("regression guard must be an object")
    kind = str(raw.get("kind") or "").strip().upper()
    if kind not in ALLOWED_GUARD_KINDS:
        raise RegressionDebtFailure("regression guard kind must be TEST or CONTRACT")
    path = _nonempty(raw.get("path"), "regression guard path").replace("\\", "/")
    permanent = raw.get("permanent")
    if permanent is not True:
        raise RegressionDebtFailure("regression guard must be permanent")

    if kind == "TEST":
        if not path.startswith("tests/") or not path.endswith(".py"):
            raise RegressionDebtFailure("TEST guard must be a tests/*.py path")
    else:
        if not (
            path.startswith("devsystem/")
            or path.startswith(".github/")
            or path.startswith("tests/")
        ):
            raise RegressionDebtFailure(
                "CONTRACT guard must live under devsystem/, .github/, or tests/"
            )

    return {"kind": kind, "path": path, "permanent": True}


def _normalize_guards(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        raise RegressionDebtFailure("at least one permanent regression guard is required")
    guards = [_normalize_guard(value) for value in values]
    keys = [(item["kind"], item["path"]) for item in guards]
    if len(set(keys)) != len(keys):
        raise RegressionDebtFailure("duplicate regression guard")
    return sorted(guards, key=lambda item: (item["kind"], item["path"]))


def build_debt(
    *,
    failure_id: str,
    owner: str,
    root_cause: str,
    repair_sha: str,
    regression_guards: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_owner = str(owner or "").strip().upper()
    if normalized_owner in NON_REPAIR_OWNERS:
        return {
            "version": VERSION,
            "failure_id": _nonempty(failure_id, "failure_id"),
            "owner": normalized_owner,
            "debt_required": False,
            "state": "EXEMPT",
            "reason": "NON_REPAIR_OWNER",
        }
    if normalized_owner not in REAL_FAILURE_OWNERS:
        raise RegressionDebtFailure(f"unsupported failure owner: {normalized_owner!r}")

    body: dict[str, Any] = {
        "version": VERSION,
        "failure_id": _nonempty(failure_id, "failure_id"),
        "owner": normalized_owner,
        "root_cause": _nonempty(root_cause, "root_cause"),
        "repair_sha": _sha(repair_sha, "repair_sha"),
        "debt_required": True,
        "state": "CLEARED" if regression_guards else "OPEN",
        "regression_guards": (
            _normalize_guards(regression_guards or [])
            if regression_guards
            else []
        ),
    }
    body["debt_hash"] = _hash(body)
    return validate_debt(body)


def validate_debt(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise RegressionDebtFailure("regression debt must be an object")
    value = deepcopy(dict(payload))
    owner = str(value.get("owner") or "").strip().upper()

    if owner in NON_REPAIR_OWNERS:
        if value.get("debt_required") is not False or value.get("state") != "EXEMPT":
            raise RegressionDebtFailure("non-repair owner debt must be EXEMPT")
        return value

    if owner not in REAL_FAILURE_OWNERS:
        raise RegressionDebtFailure("regression debt has invalid owner")
    _nonempty(value.get("failure_id"), "failure_id")
    _nonempty(value.get("root_cause"), "root_cause")
    _sha(value.get("repair_sha"), "repair_sha")

    if value.get("debt_required") is not True:
        raise RegressionDebtFailure("real failure must create regression debt")

    state = str(value.get("state") or "").upper()
    if state not in {"OPEN", "CLEARED"}:
        raise RegressionDebtFailure("real failure debt state must be OPEN or CLEARED")

    guards_raw = value.get("regression_guards")
    if not isinstance(guards_raw, list):
        raise RegressionDebtFailure("regression_guards must be a list")
    guards = _normalize_guards(guards_raw) if guards_raw else []

    if state == "CLEARED" and not guards:
        raise RegressionDebtFailure("CLEARED debt requires a permanent regression guard")
    if state == "OPEN" and guards:
        raise RegressionDebtFailure("OPEN debt cannot already carry regression guards")

    supplied = str(value.get("debt_hash") or "").lower()
    if not _HASH64.fullmatch(supplied):
        raise RegressionDebtFailure("debt_hash must be sha256")
    unsigned = deepcopy(value)
    unsigned.pop("debt_hash", None)
    expected = _hash(unsigned)
    if supplied != expected:
        raise RegressionDebtFailure("regression debt hash mismatch")

    value["owner"] = owner
    value["state"] = state
    value["regression_guards"] = guards
    value["debt_hash"] = supplied
    return value


def evaluate_freeze(debts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if isinstance(debts, (str, bytes)) or not isinstance(debts, Sequence):
        raise RegressionDebtFailure("debts must be a sequence")

    open_ids: list[str] = []
    cleared_ids: list[str] = []
    exempt_ids: list[str] = []
    seen: set[str] = set()

    for raw in debts:
        debt = validate_debt(raw)
        failure_id = _nonempty(debt.get("failure_id"), "failure_id")
        if failure_id in seen:
            raise RegressionDebtFailure(f"duplicate failure debt: {failure_id}")
        seen.add(failure_id)

        if debt.get("state") == "OPEN":
            open_ids.append(failure_id)
        elif debt.get("state") == "CLEARED":
            cleared_ids.append(failure_id)
        else:
            exempt_ids.append(failure_id)

    if open_ids:
        raise RegressionDebtFailure(
            "REGRESSION_DEBT_BLOCKS_FREEZE: " + ", ".join(sorted(open_ids))
        )

    return {
        "status": "GREEN",
        "decision": "REGRESSION_DEBT_ZERO",
        "freeze_allowed": True,
        "total_failures": len(seen),
        "cleared_debt_count": len(cleared_ids),
        "exempt_count": len(exempt_ids),
        "open_debt_count": 0,
        "cleared_failure_ids": sorted(cleared_ids),
        "exempt_failure_ids": sorted(exempt_ids),
    }


def contract_self_test() -> dict[str, Any]:
    sha = "a" * 40

    open_debt = build_debt(
        failure_id="failure-product-1",
        owner="PRODUCT",
        root_cause="exact parser branch lost the provider alias",
        repair_sha=sha,
    )
    open_debt_blocks = False
    try:
        evaluate_freeze([open_debt])
    except RegressionDebtFailure as exc:
        open_debt_blocks = "REGRESSION_DEBT_BLOCKS_FREEZE" in str(exc)

    guarded = build_debt(
        failure_id="failure-product-1",
        owner="PRODUCT",
        root_cause="exact parser branch lost the provider alias",
        repair_sha=sha,
        regression_guards=[
            {"kind": "TEST", "path": "tests/test_provider_alias_regression.py", "permanent": True}
        ],
    )
    contract_guarded = build_debt(
        failure_id="failure-ci-1",
        owner="CI",
        root_cause="workflow omitted a required terminal lane",
        repair_sha=sha,
        regression_guards=[
            {"kind": "CONTRACT", "path": "devsystem/permanent_gate_v1.py", "permanent": True}
        ],
    )
    cleared = evaluate_freeze([guarded, contract_guarded])

    stale = build_debt(
        failure_id="failure-stale-1",
        owner="STALE",
        root_cause="ignored",
        repair_sha=sha,
    )
    external = build_debt(
        failure_id="failure-external-1",
        owner="EXTERNAL",
        root_cause="ignored",
        repair_sha=sha,
    )
    exempt = evaluate_freeze([stale, external])

    failed_guard_rejected = False
    try:
        build_debt(
            failure_id="failure-verifier-1",
            owner="VERIFIER",
            root_cause="selector race",
            repair_sha=sha,
            regression_guards=[
                {"kind": "TEST", "path": "docs/not-a-test.md", "permanent": True}
            ],
        )
    except RegressionDebtFailure:
        failed_guard_rejected = True

    nonpermanent_guard_rejected = False
    try:
        build_debt(
            failure_id="failure-deploy-1",
            owner="DEPLOYMENT",
            root_cause="deployment identity drift",
            repair_sha=sha,
            regression_guards=[
                {"kind": "CONTRACT", "path": "devsystem/deploy_guard.py", "permanent": False}
            ],
        )
    except RegressionDebtFailure:
        nonpermanent_guard_rejected = True

    tampered = deepcopy(guarded)
    tampered["root_cause"] = "tampered"
    tamper_rejected = False
    try:
        validate_debt(tampered)
    except RegressionDebtFailure:
        tamper_rejected = True

    mixed_open_blocks = False
    try:
        evaluate_freeze([guarded, open_debt])
    except RegressionDebtFailure:
        mixed_open_blocks = True

    empty_green = evaluate_freeze([])

    result = {
        "status": "GREEN",
        "version": VERSION,
        "real_failure_creates_debt": open_debt["debt_required"] is True,
        "open_debt_blocks_freeze": open_debt_blocks,
        "permanent_test_clears_debt": cleared["cleared_debt_count"] == 2,
        "permanent_contract_clears_debt": contract_guarded["state"] == "CLEARED",
        "stale_failure_exempt": stale["state"] == "EXEMPT",
        "external_failure_exempt": external["state"] == "EXEMPT",
        "invalid_test_guard_rejected": failed_guard_rejected,
        "nonpermanent_guard_rejected": nonpermanent_guard_rejected,
        "tamper_rejected": tamper_rejected,
        "mixed_open_debt_blocks": mixed_open_blocks,
        "zero_debt_green": empty_green["freeze_allowed"] is True,
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
        raise RegressionDebtFailure("regression-debt-zero self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["product_runtime_mutation"]:
        raise RegressionDebtFailure("regression-debt-zero safety invariant failed")
    return result


def main() -> int:
    print("MONSTER_V4_REGRESSION_DEBT_ZERO_GATE_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RegressionDebtFailure as exc:
        print(f"MONSTER_V4_REGRESSION_DEBT_ZERO_GATE_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1)
