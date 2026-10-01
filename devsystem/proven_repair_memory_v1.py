"""MONSTER V6 Step 4 — Proven Repair Memory V1.

Repository-backed, tamper-evident memory of repairs that were actually proven.

A memory hit is advisory only. It may reuse a diagnosis/repair pattern, but it
never grants repository mutation authority. Every new failure still requires
fresh failure ownership, Step 2A, a scope-aware lease, preflight, and exact-head
proof.

Matching is exact on stable signature fields:
owner + failure_code + surface + evidence_signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.failure_ownership_engine_v1 import classify_failure

VERSION = "MONSTER_V6_PROVEN_REPAIR_MEMORY_V1"
CATALOG_VERSION = "MONSTER_V6_PROVEN_REPAIR_MEMORY_CATALOG_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_OWNERS = {"PRODUCT", "VERIFIER", "CI", "DEPLOYMENT", "EXTERNAL", "STALE"}


class RepairMemoryFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash24(value: Any, prefix: str) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:24].upper()


def _signature(value: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise RepairMemoryFailure("failure signature must be an object")
    owner = str(value.get("owner") or "").strip().upper()
    code = str(value.get("failure_code") or "").strip().upper()
    surface = str(value.get("surface") or "").strip().lower()
    signal = str(value.get("evidence_signal") or "").strip().lower()
    if owner not in _OWNERS:
        raise RepairMemoryFailure("failure signature owner is invalid")
    if not code or not surface or not signal:
        raise RepairMemoryFailure("failure signature requires failure_code, surface, and evidence_signal")
    return {
        "owner": owner,
        "failure_code": code,
        "surface": surface,
        "evidence_signal": signal,
    }


def _proof(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RepairMemoryFailure("proof must be an object")
    out = deepcopy(dict(value))
    out["checkpoint_id"] = str(out.get("checkpoint_id") or "").strip()
    out["proven_sha"] = str(out.get("proven_sha") or "").strip().lower()
    out["terminal_receipt_digest"] = str(out.get("terminal_receipt_digest") or "").strip().lower()
    out["conclusion"] = str(out.get("conclusion") or "").strip().upper()
    try:
        out["workflow_run_id"] = int(out.get("workflow_run_id") or 0)
    except (TypeError, ValueError) as exc:
        raise RepairMemoryFailure("proof workflow_run_id must be an integer") from exc
    if not out["checkpoint_id"]:
        raise RepairMemoryFailure("proof checkpoint_id is required")
    if not _SHA40.fullmatch(out["proven_sha"]):
        raise RepairMemoryFailure("proof proven_sha must be a full SHA")
    if out["workflow_run_id"] <= 0:
        raise RepairMemoryFailure("proof workflow_run_id must be positive")
    if not _DIGEST.fullmatch(out["terminal_receipt_digest"]):
        raise RepairMemoryFailure("proof terminal_receipt_digest is invalid")
    if out["conclusion"] != "SUCCESS":
        raise RepairMemoryFailure("only successful proof may enter repair memory")
    return out


def _required_protections(value: Mapping[str, Any]) -> dict[str, bool]:
    if not isinstance(value, Mapping):
        raise RepairMemoryFailure("repair protections must be an object")
    required_true = [
        "advisory_only",
        "fresh_ownership_required",
        "step_2a_required",
        "scope_lease_required",
        "preflight_required",
    ]
    out = {name: bool(value.get(name)) for name in required_true}
    out["mutation_authority"] = bool(value.get("mutation_authority"))
    if not all(out[name] for name in required_true):
        raise RepairMemoryFailure("repair protections are incomplete")
    if out["mutation_authority"]:
        raise RepairMemoryFailure("repair memory may not grant mutation authority")
    return out


def validate_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise RepairMemoryFailure("repair record must be an object")
    out = deepcopy(dict(record))
    supplied = str(out.pop("record_id", "") or "").strip().upper()
    if out.get("version") != VERSION or int(out.get("schema_version", 0)) != 1:
        raise RepairMemoryFailure("repair record version/schema mismatch")
    out["signature"] = _signature(out.get("signature") or {})
    out["root_cause"] = str(out.get("root_cause") or "").strip()
    if not out["root_cause"]:
        raise RepairMemoryFailure("root_cause is required")
    repair = out.get("repair_pattern")
    if not isinstance(repair, Mapping):
        raise RepairMemoryFailure("repair_pattern must be an object")
    if not str(repair.get("summary") or "").strip():
        raise RepairMemoryFailure("repair_pattern summary is required")
    if not isinstance(repair.get("steps"), list) or not repair.get("steps"):
        raise RepairMemoryFailure("repair_pattern steps are required")
    mutation_owner = str(repair.get("mutation_owner") or "").strip().upper()
    if mutation_owner != out["signature"]["owner"]:
        raise RepairMemoryFailure("repair mutation_owner must match failure owner")
    out["proof"] = _proof(out.get("proof") or {})
    failed = out.get("failed_evidence")
    if not isinstance(failed, Mapping):
        raise RepairMemoryFailure("failed_evidence must be an object")
    try:
        failed_run = int(failed.get("workflow_run_id") or 0)
    except (TypeError, ValueError) as exc:
        raise RepairMemoryFailure("failed_evidence workflow_run_id must be an integer") from exc
    if failed_run <= 0 or str(failed.get("conclusion") or "").upper() not in {"FAILURE", "CANCELLED"}:
        raise RepairMemoryFailure("failed_evidence must identify a terminal failed/cancelled run")
    out["protections"] = _required_protections(out.get("protections") or {})
    expected = _hash24(out, "REPAIR-")
    if supplied != expected:
        raise RepairMemoryFailure("repair record fingerprint mismatch")
    out["record_id"] = supplied
    return out


def validate_catalog(catalog: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(catalog, Mapping):
        raise RepairMemoryFailure("repair catalog must be an object")
    raw = deepcopy(dict(catalog))
    supplied = str(raw.pop("catalog_id", "") or "").strip().upper()
    if raw.get("version") != CATALOG_VERSION or int(raw.get("schema_version", 0)) != 1:
        raise RepairMemoryFailure("repair catalog version/schema mismatch")
    if not str(raw.get("repository") or "").strip():
        raise RepairMemoryFailure("repair catalog repository is required")
    try:
        revision = int(raw.get("revision") or 0)
    except (TypeError, ValueError) as exc:
        raise RepairMemoryFailure("repair catalog revision must be an integer") from exc
    if revision <= 0:
        raise RepairMemoryFailure("repair catalog revision must be positive")
    records = raw.get("records")
    if not isinstance(records, list) or not records:
        raise RepairMemoryFailure("repair catalog requires at least one record")
    verified = [validate_record(item) for item in records]
    ids = [item["record_id"] for item in verified]
    if len(ids) != len(set(ids)):
        raise RepairMemoryFailure("duplicate repair record IDs are forbidden")
    signatures = [_canonical(item["signature"]) for item in verified]
    if len(signatures) != len(set(signatures)):
        raise RepairMemoryFailure("duplicate failure signatures are forbidden")
    protections = raw.get("protections") or {}
    required_true = [
        "exact_signature_match_only",
        "successful_proof_required",
        "terminal_receipt_required",
        "duplicate_signature_forbidden",
        "advisory_only",
        "fresh_failure_ownership_required",
        "step_2a_required",
        "scope_lease_required",
        "preflight_required",
    ]
    if not all(protections.get(name) is True for name in required_true):
        raise RepairMemoryFailure("catalog protections drift")
    if protections.get("mutation_authority") is not False:
        raise RepairMemoryFailure("catalog may not grant mutation authority")
    raw["records"] = sorted(verified, key=lambda item: item["record_id"])
    expected = _hash24(raw, "CATALOG-")
    if supplied != expected:
        raise RepairMemoryFailure("repair catalog fingerprint mismatch")
    raw["catalog_id"] = supplied
    return raw


def load_catalog(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepairMemoryFailure(f"unable to read repair catalog: {target}") from exc
    return validate_catalog(data)


def lookup_exact(catalog: Mapping[str, Any], signature: Mapping[str, Any]) -> dict[str, Any]:
    verified = validate_catalog(catalog)
    wanted = _signature(signature)
    matches = [item for item in verified["records"] if item["signature"] == wanted]
    if not matches:
        return {
            "version": VERSION,
            "status": "MISS",
            "signature": wanted,
            "repair": None,
            "next_legal_action": "DIAGNOSE_FRESH_FAILURE",
            "mutation_authority": False,
        }
    if len(matches) != 1:
        raise RepairMemoryFailure("ambiguous repair memory match")
    record = matches[0]
    return {
        "version": VERSION,
        "status": "HIT",
        "signature": wanted,
        "repair": record,
        "next_legal_action": "REUSE_DIAGNOSIS_PATTERN_THEN_REVALIDATE",
        "requirements_before_mutation": [
            "FRESH_FAILURE_OWNERSHIP",
            "STEP_2A",
            "SCOPE_AWARE_LEASE",
            "PREFLIGHT_GATE",
            "EXACT_HEAD_PROOF",
        ],
        "mutation_authority": False,
    }


def lookup_for_failure(
    catalog: Mapping[str, Any],
    *,
    failure_code: str,
    failure: Mapping[str, Any],
    evidence_freshness: str = "CURRENT",
) -> dict[str, Any]:
    ownership = classify_failure(failure, evidence_freshness=evidence_freshness)
    signature = {
        "owner": ownership["owner"],
        "failure_code": failure_code,
        "surface": str(failure.get("layer") or "").strip().lower(),
        "evidence_signal": str(failure.get("evidence_signal") or "").strip().lower(),
    }
    result = lookup_exact(catalog, signature)
    result["fresh_ownership"] = {
        "owner": ownership["owner"],
        "decision_id": ownership["decision_id"],
        "patch_allowed": ownership["patch_allowed"],
        "product_mutation_allowed": ownership["product_mutation_allowed"],
    }
    if ownership["owner"] in {"STALE", "EXTERNAL"}:
        result["status"] = "BLOCKED"
        result["repair"] = None
        result["next_legal_action"] = ownership["next_legal_action"]
    return result


def contract_self_test() -> dict[str, Any]:
    base = {
        "schema_version": 1,
        "version": VERSION,
        "signature": {
            "owner": "CI",
            "failure_code": "PACKAGE_BOOTSTRAP",
            "surface": "workflow-control",
            "evidence_signal": "module-import",
        },
        "root_cause": "repository root absent from sys.path",
        "repair_pattern": {
            "summary": "bootstrap repository root",
            "steps": ["insert root before package import"],
            "mutation_owner": "CI",
            "touched_paths": ["devsystem/example.py"],
        },
        "failed_evidence": {"workflow_run_id": 100, "conclusion": "FAILURE"},
        "proof": {
            "checkpoint_id": "TEST",
            "proven_sha": "a" * 40,
            "workflow_run_id": 101,
            "terminal_receipt_digest": "sha256:" + "b" * 64,
            "conclusion": "SUCCESS",
        },
        "protections": {
            "advisory_only": True,
            "fresh_ownership_required": True,
            "step_2a_required": True,
            "scope_lease_required": True,
            "preflight_required": True,
            "mutation_authority": False,
        },
    }
    base["record_id"] = _hash24(base, "REPAIR-")
    catalog_body = {
        "schema_version": 1,
        "version": CATALOG_VERSION,
        "repository": "owner/repo",
        "revision": 1,
        "records": [base],
        "protections": {
            "exact_signature_match_only": True,
            "successful_proof_required": True,
            "terminal_receipt_required": True,
            "duplicate_signature_forbidden": True,
            "advisory_only": True,
            "fresh_failure_ownership_required": True,
            "step_2a_required": True,
            "scope_lease_required": True,
            "preflight_required": True,
            "mutation_authority": False,
        },
    }
    catalog = deepcopy(catalog_body)
    catalog["catalog_id"] = _hash24(catalog_body, "CATALOG-")
    hit = lookup_exact(catalog, base["signature"])
    miss = lookup_exact(catalog, {**base["signature"], "failure_code": "OTHER_FAILURE"})
    fresh = lookup_for_failure(
        catalog,
        failure_code="PACKAGE_BOOTSTRAP",
        failure={
            "job": "preflight",
            "layer": "workflow-control",
            "evidence_signal": "module-import",
            "diagnosis": "package import failed",
        },
    )
    tampered = deepcopy(catalog)
    tampered["records"][0]["root_cause"] = "tampered"
    tamper_blocked = False
    try:
        validate_catalog(tampered)
    except RepairMemoryFailure:
        tamper_blocked = True

    bad_proof = deepcopy(base)
    bad_proof["proof"]["conclusion"] = "FAILURE"
    bad_proof["record_id"] = _hash24({k: v for k, v in bad_proof.items() if k != "record_id"}, "REPAIR-")
    failed_proof_blocked = False
    try:
        validate_record(bad_proof)
    except RepairMemoryFailure:
        failed_proof_blocked = True

    result = {
        "status": "GREEN",
        "version": VERSION,
        "exact_hit_reuses_pattern": hit["status"] == "HIT",
        "nonexact_match_misses": miss["status"] == "MISS",
        "fresh_ownership_checked": fresh.get("fresh_ownership", {}).get("owner") == "CI",
        "hit_never_grants_mutation": hit["mutation_authority"] is False,
        "tamper_fails_closed": tamper_blocked,
        "unproven_repair_rejected": failed_proof_blocked,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = [
        "exact_hit_reuses_pattern",
        "nonexact_match_misses",
        "fresh_ownership_checked",
        "hit_never_grants_mutation",
        "tamper_fails_closed",
        "unproven_repair_rejected",
    ]
    if not all(result[name] is True for name in required):
        raise RepairMemoryFailure("repair memory self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["may_modify_product_runtime"] or result["mutation_authority_granted"]:
        raise RepairMemoryFailure("repair memory read-only invariant failed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="MONSTER V6 proven repair memory")
    parser.add_argument("--catalog", default="")
    args = parser.parse_args()
    result = contract_self_test()
    if args.catalog:
        verified = load_catalog(args.catalog)
        print(f"MONSTER_V6_PROVEN_REPAIR_CATALOG_GREEN revision={verified['revision']} records={len(verified['records'])}")
    print("MONSTER_V6_PROVEN_REPAIR_MEMORY_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RepairMemoryFailure as exc:
        print(f"MONSTER_V6_PROVEN_REPAIR_MEMORY_BLOCKED: {exc}")
        raise SystemExit(1)
