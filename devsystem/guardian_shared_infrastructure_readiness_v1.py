from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "GUARDIAN_SHARED_INFRASTRUCTURE_READINESS_CONTRACT_V1"
BASELINE_FILE = "devsystem/guardian_shared_infrastructure_readiness_v1.json"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_AUTHORIZE_CONSUMER_EXECUTION = False
_ALLOWED_CONSUMERS = frozenset({"API2", "MONSTER"})
_FORBIDDEN_KEYS = frozenset({
    "branch",
    "pr",
    "lease",
    "lock",
    "checkpoint",
    "receipt",
    "proof_artifact",
    "execution_state",
    "failure_state",
    "recovery_state",
    "green_frozen",
    "percentage",
    "frozen_registry",
})


class ReadinessContractError(RuntimeError):
    pass


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _find_forbidden(value: Any, *, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in _FORBIDDEN_KEYS:
                hits.append(child_path)
            hits.extend(_find_forbidden(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_find_forbidden(child, path=f"{path}[{index}]"))
    return hits


def validate_baseline(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReadinessContractError("baseline must be an object")

    value = deepcopy(dict(payload))
    forbidden = _find_forbidden(value)
    if forbidden:
        raise ReadinessContractError(
            "forbidden cross-system execution-authority fields present: " + ", ".join(forbidden)
        )

    if value.get("contract") != CONTRACT:
        raise ReadinessContractError("readiness contract identity mismatch")
    if int(value.get("schema_version") or 0) != 1:
        raise ReadinessContractError("readiness schema version mismatch")
    if value.get("status") != "GREEN":
        raise ReadinessContractError("published readiness status must be GREEN")
    if value.get("publisher") != "KYRE_GUARDIAN":
        raise ReadinessContractError("readiness publisher must be KYRE_GUARDIAN")
    if value.get("consumer_systems") != ["API2", "MONSTER"]:
        raise ReadinessContractError("consumer systems must be exactly API2 and MONSTER")

    shared = value.get("shared_infrastructure")
    if not isinstance(shared, Mapping):
        raise ReadinessContractError("shared infrastructure block is missing")

    github = shared.get("github")
    vercel = shared.get("vercel")
    supabase = shared.get("supabase")
    source_of_truth = shared.get("source_of_truth")
    if not all(isinstance(item, Mapping) for item in (github, vercel, supabase, source_of_truth)):
        raise ReadinessContractError("shared infrastructure sections are incomplete")

    if github.get("repository") != "kyrepeak/kyre-sports-ai":
        raise ReadinessContractError("GitHub repository identity mismatch")
    if github.get("protected_main") is not True:
        raise ReadinessContractError("protected main must remain required")
    if github.get("required_final_gate") != "runless-final-gate":
        raise ReadinessContractError("Runless final gate identity mismatch")
    if int(github.get("required_final_gate_app_id") or 0) != 5204253:
        raise ReadinessContractError("Runless final gate App identity mismatch")

    projects = vercel.get("production_projects")
    if projects != ["kyre-sports-api", "kyre-runless-proof", "kyre-sports-finalizer"]:
        raise ReadinessContractError("production project set mismatch")
    if int(vercel.get("stale_preview_env_count") or 0) != 0:
        raise ReadinessContractError("stale preview configuration must be zero")

    if int(supabase.get("migration_count") or 0) <= 0:
        raise ReadinessContractError("Supabase migration count is invalid")
    if int(supabase.get("actionable_security_findings") or 0) != 0:
        raise ReadinessContractError("Supabase has actionable security findings")
    if supabase.get("anon_authenticated_schema_usage") is not False:
        raise ReadinessContractError("backend-only schemas must not be exposed to anon/authenticated")

    policy = value.get("consumer_policy")
    if not isinstance(policy, Mapping):
        raise ReadinessContractError("consumer policy is missing")
    if policy.get("authority_policy") != "CONTEXT_ONLY_NOT_EXECUTION_EVIDENCE":
        raise ReadinessContractError("consumer authority policy mismatch")
    if policy.get("may_authorize_consumer_execution") is not False:
        raise ReadinessContractError("Guardian readiness may not authorize consumer execution")
    if policy.get("consumer_execution_state_remains_independent") is not True:
        raise ReadinessContractError("consumer execution state must remain independent")

    forbidden_uses = policy.get("forbidden_uses")
    if not isinstance(forbidden_uses, list):
        raise ReadinessContractError("forbidden uses list is missing")
    for required in ("execution_authorization", "green_frozen_authority"):
        if required not in forbidden_uses:
            raise ReadinessContractError(f"forbidden use missing: {required}")

    freshness = value.get("freshness")
    if not isinstance(freshness, Mapping):
        raise ReadinessContractError("freshness policy is missing")
    if freshness.get("scope") != "SHARED_INFRASTRUCTURE_REVISION":
        raise ReadinessContractError("freshness scope mismatch")
    if freshness.get("page_only_merge_invalidates_baseline") is not False:
        raise ReadinessContractError("page-only merges must not invalidate shared readiness")

    return value


def load_readiness(consumer_system: str, repo_root: Path | None = None) -> dict[str, Any]:
    consumer = str(consumer_system or "").strip().upper()
    if consumer not in _ALLOWED_CONSUMERS:
        raise ReadinessContractError(f"consumer is not allowed: {consumer or 'missing'}")

    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    path = root / BASELINE_FILE
    if not path.is_file():
        raise ReadinessContractError(f"readiness baseline is missing: {BASELINE_FILE}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadinessContractError(f"readiness baseline is unreadable: {exc}") from exc

    baseline = validate_baseline(payload)
    policy = baseline["consumer_policy"]
    return {
        "contract": CONTRACT,
        "status": "GREEN",
        "consumer_system": consumer,
        "authority_policy": policy["authority_policy"],
        "may_authorize_consumer_execution": False,
        "baseline_digest": _digest(baseline),
        "shared_infrastructure": deepcopy(baseline["shared_infrastructure"]),
        "freshness": deepcopy(baseline["freshness"]),
        "source_manifest": baseline["shared_infrastructure"]["source_of_truth"]["manifest"],
    }
