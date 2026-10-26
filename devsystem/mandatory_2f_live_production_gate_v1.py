"""MONSTER Step 2F — Live Production Consumption + Stable Alias Gate V1.

Pure fail-closed verifier. It does not deploy, promote, poll, or mutate. Callers
must supply MONSTER-owned evidence from the authoritative deployment/probe path.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping

from devsystem.monster_system_isolation_v1 import assert_monster_only

VERSION = "MONSTER_STEP2F_LIVE_PRODUCTION_CONSUMPTION_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class Mandatory2FLiveProductionFailure(RuntimeError):
    def __init__(self, failure_class: str, reason: str, evidence: Mapping[str, Any] | None = None):
        self.failure_class = failure_class
        self.reason = reason
        self.evidence = dict(evidence or {})
        super().__init__(f"{failure_class}: {reason}")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _sha(value: Any, field: str) -> str:
    value = _text(value).lower()
    if not _SHA.fullmatch(value):
        raise Mandatory2FLiveProductionFailure("PROOF_MISMATCH", f"invalid {field}")
    return value


def _fail(kind: str, reason: str, **evidence: Any) -> None:
    raise Mandatory2FLiveProductionFailure(kind, reason, evidence)


def verify_live_production(evidence: Mapping[str, Any]) -> dict[str, Any]:
    assert_monster_only(evidence)
    system = _text(evidence.get("system")).upper()
    if system != "MONSTER":
        _fail("SYSTEM_ISOLATION", "production evidence is not MONSTER-owned")

    head = _sha(evidence.get("certified_head_sha"), "certified_head_sha")
    deployment = dict(evidence.get("deployment") or {})
    alias = dict(evidence.get("stable_alias") or {})
    endpoint = dict(evidence.get("canonical_endpoint") or {})
    website = dict(evidence.get("website") or {})
    rollback = dict(evidence.get("rollback_anchor") or {})
    proof = dict(evidence.get("proof") or {})

    if _text(deployment.get("target")).lower() != "production":
        _fail("PREVIEW_NOT_PRODUCTION", "deployment target is not production", target=deployment.get("target"))
    if _text(deployment.get("state")).upper() != "READY":
        _fail("DEPLOYMENT_FAILURE", "production deployment is not READY", state=deployment.get("state"))
    deployment_sha = _sha(deployment.get("git_sha"), "deployment.git_sha")
    if deployment_sha != head:
        _fail("DEPLOYMENT_DRIFT", "production deployment SHA differs from certified head", expected=head, observed=deployment_sha)
    branch = _text(deployment.get("branch")).lower()
    if not branch.startswith("monster"):
        _fail("SYSTEM_ISOLATION", "production deployment branch is not MONSTER-owned", branch=branch)
    deployment_id = _text(deployment.get("id"))
    if not deployment_id or not _text(deployment.get("url")):
        _fail("DEPLOYMENT_IDENTITY_MISSING", "deployment identity is incomplete")

    if _text(alias.get("deployment_id")) != deployment_id:
        _fail("ALIAS_DRIFT", "stable alias points to a different deployment")
    if _sha(alias.get("git_sha"), "stable_alias.git_sha") != head:
        _fail("ALIAS_DRIFT", "stable alias SHA differs from certified head")
    if not _text(alias.get("url")):
        _fail("ALIAS_DRIFT", "stable alias URL is missing")

    code = int(endpoint.get("status_code") or 0)
    if code in {301, 302, 303, 307, 308} and "auth" in _text(endpoint.get("redirect_location")).lower():
        _fail("AUTHENTICATION_REQUIRED", "canonical production endpoint requires authentication")
    if not 200 <= code < 300:
        _fail("UNHEALTHY_PRODUCTION_RUNTIME", "canonical endpoint is not healthy", status_code=code)
    if _text(endpoint.get("router_owner")).upper() != "MONSTER" or _text(endpoint.get("schema_owner")).upper() != "MONSTER":
        _fail("ROUTER_SCHEMA_MISMATCH", "canonical endpoint owner/schema mismatch")
    if _sha(endpoint.get("git_sha"), "canonical_endpoint.git_sha") != head:
        _fail("PROOF_MISMATCH", "canonical endpoint SHA differs from certified head")

    website_code = int(website.get("status_code") or 0)
    if website_code in {301, 302, 303, 307, 308} and "auth" in _text(website.get("redirect_location")).lower():
        _fail("AUTHENTICATION_REQUIRED", "live website requires authentication")
    if not 200 <= website_code < 300:
        _fail("UNHEALTHY_PRODUCTION_RUNTIME", "live website smoke is not healthy", status_code=website_code)
    consumed_sha = _sha(website.get("consumed_sha"), "website.consumed_sha")
    if consumed_sha != head:
        _fail("LIVE_CONSUMPTION_DRIFT", "website is not consuming the certified head", expected=head, observed=consumed_sha)
    smokes = list(website.get("route_smokes") or [])
    if not smokes or any(_text(item.get("status")).upper() != "PASS" for item in smokes):
        _fail("PRODUCTION_SMOKE_FAILURE", "one or more production route smokes did not pass")

    rollback_id = _text(rollback.get("deployment_id"))
    rollback_sha = _sha(rollback.get("git_sha"), "rollback_anchor.git_sha")
    if not rollback_id or rollback_id == deployment_id or rollback_sha == head:
        _fail("ROLLBACK_ANCHOR_MISSING", "independent rollback anchor is missing")

    proof_id = _text(proof.get("proof_id"))
    receipt_digest = _text(proof.get("receipt_digest")).lower()
    if not proof_id.startswith("monster-") or not _DIGEST.fullmatch(receipt_digest):
        _fail("PROOF_MISMATCH", "MONSTER proof receipt is incomplete")

    canonical = json.dumps(deepcopy(dict(evidence)), sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "status": "GREEN",
        "version": VERSION,
        "monster_only": True,
        "certified_head_sha": head,
        "deployment_id": deployment_id,
        "stable_alias": alias["url"],
        "exact_head_deployment": True,
        "stable_alias_parity": True,
        "canonical_endpoint_healthy": True,
        "website_consumes_exact_head": True,
        "every_page_smoke_green": True,
        "rollback_anchor_present": True,
        "proof_receipt_bound": True,
        "evidence_digest": digest,
    }


def contract_self_test() -> dict[str, Any]:
    sha = "1" * 40
    evidence = {
        "system": "MONSTER",
        "certified_head_sha": sha,
        "deployment": {"id": "dpl_monster", "target": "production", "state": "READY", "git_sha": sha, "branch": "monster-main", "url": "https://monster.example"},
        "stable_alias": {"url": "https://monster-stable.example", "deployment_id": "dpl_monster", "git_sha": sha},
        "canonical_endpoint": {"url": "https://monster-stable.example/health", "status_code": 200, "router_owner": "MONSTER", "schema_owner": "MONSTER", "git_sha": sha},
        "website": {"url": "https://site.example", "status_code": 200, "consumed_sha": sha, "route_smokes": [{"route": "self-test", "status": "PASS"}]},
        "rollback_anchor": {"deployment_id": "dpl_previous", "git_sha": "2" * 40},
        "proof": {"proof_id": "monster-step2f-self-test", "receipt_digest": "3" * 64},
    }
    green = verify_live_production(evidence)
    bad = deepcopy(evidence)
    bad["stable_alias"]["deployment_id"] = "dpl_wrong"
    blocked = False
    try:
        verify_live_production(bad)
    except Mandatory2FLiveProductionFailure as exc:
        blocked = exc.failure_class == "ALIAS_DRIFT"
    if not blocked:
        raise AssertionError("Step 2F alias drift self-test did not fail closed")
    return {**green, "alias_drift_fail_closed": True}


if __name__ == "__main__":
    contract_self_test()
    print("MONSTER_STEP2F_LIVE_PRODUCTION_CONSUMPTION_V1_GREEN")
