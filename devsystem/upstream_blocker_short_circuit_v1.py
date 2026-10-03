"""API2 Proof Architecture V1 Step 4 — Upstream Blocker Short Circuit.

No expensive downstream proof may begin until its registered upstream owner is
explicitly certified GREEN + FROZEN. Source-complete or status=DONE is not
sufficient when the upstream ledger still withholds its freeze claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

VERSION = "API2_UPSTREAM_BLOCKER_SHORT_CIRCUIT_V1"
REGISTRY_VERSION = "API2_UPSTREAM_CERTIFICATION_REGISTRY_V1"
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "devsystem/upstream_certification_registry_v1.json"


class UpstreamGateFailure(RuntimeError):
    pass


def _registry(path: Path = REGISTRY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != REGISTRY_VERSION:
        raise UpstreamGateFailure("upstream registry version drift")
    deps = payload.get("dependencies")
    if not isinstance(deps, Mapping) or not deps:
        raise UpstreamGateFailure("upstream registry requires dependencies")
    return payload


def _spec(dependency_id: str, *, registry: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    payload = dict(registry or _registry())
    spec = payload["dependencies"].get(dependency_id)
    if not isinstance(spec, Mapping):
        raise UpstreamGateFailure(f"unknown upstream dependency: {dependency_id}")
    for key in ("upstream_owner", "downstream_owner", "evidence", "blocked_decision", "allowed_decision"):
        if not spec.get(key):
            raise UpstreamGateFailure(f"{dependency_id}: missing {key}")
    evidence = spec["evidence"]
    if not isinstance(evidence, Mapping) or evidence.get("type") != "TASK_LEDGER_GREEN_FROZEN":
        raise UpstreamGateFailure(f"{dependency_id}: unsupported evidence contract")
    for key in ("path", "required_status", "required_boolean"):
        if not evidence.get(key):
            raise UpstreamGateFailure(f"{dependency_id}: missing evidence.{key}")
    return spec


def evaluate_ledger_payload(
    dependency_id: str,
    spec: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = spec["evidence"]
    required_status = str(evidence["required_status"])
    required_boolean = str(evidence["required_boolean"])
    observed_status = str(ledger.get("status") or "")
    freeze_claim = ledger.get(required_boolean)
    status_ok = observed_status == required_status
    freeze_ok = freeze_claim is True
    allowed = status_ok and freeze_ok

    if not status_ok:
        reason = f"UPSTREAM_STATUS_{observed_status or 'MISSING'}"
    elif not freeze_ok:
        reason = "GREEN_PLUS_FROZEN_NOT_CLAIMED"
    else:
        reason = "UPSTREAM_GREEN_FROZEN"

    return {
        "version": VERSION,
        "dependency_id": dependency_id,
        "status": "GREEN" if allowed else "UPSTREAM_BLOCKED",
        "decision": spec["allowed_decision"] if allowed else spec["blocked_decision"],
        "downstream_proof_allowed": allowed,
        "upstream_owner": str(spec["upstream_owner"]),
        "downstream_owner": str(spec["downstream_owner"]),
        "evidence_type": str(evidence["type"]),
        "ledger_task_id": str(ledger.get("task_id") or ""),
        "ledger_status": observed_status,
        "green_plus_frozen_claimed": freeze_ok,
        "reason": reason,
        "product_patch_allowed": False,
        "expensive_proof_allowed": allowed,
    }


def evaluate_upstream_dependency(
    dependency_id: str,
    *,
    root: Path = ROOT,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = _spec(dependency_id, registry=registry)
    ledger_path = root / str(spec["evidence"]["path"])
    if not ledger_path.exists():
        return {
            "version": VERSION,
            "dependency_id": dependency_id,
            "status": "UPSTREAM_BLOCKED",
            "decision": str(spec["blocked_decision"]),
            "downstream_proof_allowed": False,
            "upstream_owner": str(spec["upstream_owner"]),
            "downstream_owner": str(spec["downstream_owner"]),
            "evidence_type": str(spec["evidence"]["type"]),
            "ledger_task_id": "",
            "ledger_status": "MISSING",
            "green_plus_frozen_claimed": False,
            "reason": "UPSTREAM_LEDGER_MISSING",
            "product_patch_allowed": False,
            "expensive_proof_allowed": False,
        }
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise UpstreamGateFailure("upstream ledger must be an object")
    return evaluate_ledger_payload(dependency_id, spec, payload)


def contract_self_test() -> dict[str, Any]:
    payload = _registry()
    real = evaluate_upstream_dependency("wnba-pra-repair-v1-step3-public")
    spec = _spec("wnba-pra-repair-v1-step3-public", registry=payload)
    blocked_ledger = {
        "task_id": "synthetic-blocked-upstream",
        "status": spec["evidence"]["required_status"],
        spec["evidence"]["required_boolean"]: False,
    }
    blocked = evaluate_ledger_payload(
        "wnba-pra-repair-v1-step3-public", spec, blocked_ledger
    )
    green_ledger = {
        "task_id": "synthetic-green-upstream",
        "status": spec["evidence"]["required_status"],
        spec["evidence"]["required_boolean"]: True,
    }
    allowed = evaluate_ledger_payload(
        "wnba-pra-repair-v1-step3-public", spec, green_ledger
    )
    if real["status"] not in {"UPSTREAM_BLOCKED", "GREEN"}:
        raise UpstreamGateFailure("real WNBA proof case returned an invalid state")
    if real["status"] == "GREEN":
        if real["decision"] != "PROCEED_DOWNSTREAM_PROOF" or real["downstream_proof_allowed"] is not True:
            raise UpstreamGateFailure("GREEN + FROZEN real upstream did not open downstream proof")
    elif real["decision"] != "UPSTREAM_BLOCKED" or real["downstream_proof_allowed"] is not False:
        raise UpstreamGateFailure("blocked real upstream did not fail closed")
    if blocked["status"] != "UPSTREAM_BLOCKED" or blocked["downstream_proof_allowed"] is not False:
        raise UpstreamGateFailure("synthetic unfrozen upstream did not block downstream proof")
    if allowed["decision"] != "PROCEED_DOWNSTREAM_PROOF" or allowed["downstream_proof_allowed"] is not True:
        raise UpstreamGateFailure("GREEN + FROZEN upstream did not open downstream proof")
    return {
        "status": "GREEN",
        "version": VERSION,
        "registered_dependency_count": len(payload["dependencies"]),
        "real_wnba_case": real["status"],
        "real_wnba_reason": real["reason"],
        "real_wnba_proof_allowed": real["downstream_proof_allowed"],
        "blocked_proof_allowed": blocked["downstream_proof_allowed"],
        "green_frozen_proof_allowed": allowed["downstream_proof_allowed"],
        "product_patch_allowed_when_blocked": blocked["product_patch_allowed"],
        "network_calls": False,
        "product_runtime_mutation": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("self-test")
    check = sub.add_parser("check")
    check.add_argument("--dependency-id", required=True)
    check.add_argument("--json-out")
    args = parser.parse_args(argv)

    if args.command in {None, "self-test"}:
        result = contract_self_test()
        print("API2_UPSTREAM_BLOCKER_SHORT_CIRCUIT_V1_GREEN")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    result = evaluate_upstream_dependency(args.dependency_id)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(f"API2_UPSTREAM_DECISION={result['decision']}")
    print(f"API2_UPSTREAM_OWNER={result['upstream_owner']}")
    print(f"API2_UPSTREAM_REASON={result['reason']}")
    print(f"API2_DOWNSTREAM_PROOF_ALLOWED={str(result['downstream_proof_allowed']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
