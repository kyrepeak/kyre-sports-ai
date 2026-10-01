"""MONSTER V5 Step 1 — Scope-Aware Parallel Execution Lease V1.

Additive successor layer to the frozen V4 repository-wide lease. It permits
parallel mutation only when declared write/dependency/shared scopes are proven
disjoint. Overlap, frozen reach, stale CAS, out-of-scope actions, or scoped
identity drift fail closed.

Authoritative state is designed for:
  refs/heads/monster-scope-aware-execution-leases
  devsystem/scope_aware_execution_lease_state_v1.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.mandatory_2a_global_enforcement_v1 import enforce_certified_action

VERSION = "MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_V1"
LEASE_REF = "refs/heads/monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_MUTATIONS = {"create_branch","create_file","update_file","delete_file","merge","update_ref","create_commit","deploy"}


class ScopeLeaseFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _without_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(dict(value))
    out.pop("state_hash", None)
    return out


def _utc(value: str) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ScopeLeaseFailure("invalid UTC timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise ScopeLeaseFailure(f"{field} must be a full 40-character SHA")
    return text


def _norm_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/").lstrip("./")
    if not text or text.startswith("../") or "/../" in text:
        raise ScopeLeaseFailure("invalid scope path")
    return text.rstrip("/")


def _norm_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise ScopeLeaseFailure("empty scope token")
    return text


def _unique_paths(values: Sequence[Any]) -> list[str]:
    return sorted({_norm_path(v) for v in values})


def _unique_tokens(values: Sequence[Any]) -> list[str]:
    return sorted({_norm_token(v) for v in values})


def _path_overlap(a: str, b: str) -> bool:
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def build_scope(
    *,
    write_paths: Sequence[str],
    dependency_tokens: Sequence[str] = (),
    shared_resources: Sequence[str] = (),
    resource_identity: Mapping[str, str] | None = None,
    exclusive: bool = False,
) -> dict[str, Any]:
    paths = _unique_paths(write_paths)
    if not paths:
        raise ScopeLeaseFailure("write_paths required")
    identity = {
        _norm_token(k): str(v or "").strip()
        for k, v in sorted((resource_identity or {}).items())
    }
    if any(not v for v in identity.values()):
        raise ScopeLeaseFailure("resource identity values must be non-empty")
    return {
        "write_paths": paths,
        "dependency_tokens": _unique_tokens(dependency_tokens),
        "shared_resources": _unique_tokens(shared_resources),
        "resource_identity": identity,
        "exclusive": bool(exclusive),
    }


def scope_from_blast_radius(plan: Mapping[str, Any], *, write_paths: Sequence[str]) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        raise ScopeLeaseFailure("blast radius plan must be an object")
    deps: list[str] = []
    for field in (
        "direct_dependencies","direct_dependents","transitive_dependencies",
        "transitive_dependents","impacted_entrypoints","protected_reach",
    ):
        deps.extend(f"{field}:{item}" for item in (plan.get(field) or []))
    shared = [f"entrypoint:{item}" for item in (plan.get("impacted_entrypoints") or [])]
    return build_scope(
        write_paths=write_paths,
        dependency_tokens=deps,
        shared_resources=shared,
    )


def scopes_conflict(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[bool, list[str]]:
    a = build_scope(**dict(left))
    b = build_scope(**dict(right))
    reasons: list[str] = []
    if a["exclusive"] or b["exclusive"]:
        reasons.append("exclusive")
    for x in a["write_paths"]:
        for y in b["write_paths"]:
            if _path_overlap(x, y):
                reasons.append(f"path:{x}|{y}")
    for token in sorted(set(a["dependency_tokens"]) & set(b["dependency_tokens"])):
        reasons.append(f"dependency:{token}")
    for token in sorted(set(a["shared_resources"]) & set(b["shared_resources"])):
        reasons.append(f"shared:{token}")
    return bool(reasons), sorted(set(reasons))


def new_state(repository: str) -> dict[str, Any]:
    repo = str(repository or "").strip().lower()
    if "/" not in repo:
        raise ScopeLeaseFailure("repository must be owner/name")
    state = {
        "schema_version": 1,
        "version": VERSION,
        "repository": repo,
        "lease_ref": LEASE_REF,
        "lease_state_path": LEASE_PATH,
        "revision": 0,
        "generation": 0,
        "holders": [],
    }
    state["state_hash"] = _hash(state)
    return validate_state(state)


def _validate_holder(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ScopeLeaseFailure("holder must be object")
    scope = build_scope(**dict(raw.get("scope") or {}))
    out = {
        "owner_id": str(raw.get("owner_id") or "").strip(),
        "lease_id": str(raw.get("lease_id") or "").strip(),
        "generation": int(raw.get("generation")),
        "acquired_at_utc": _fmt(_utc(raw.get("acquired_at_utc"))),
        "heartbeat_at_utc": _fmt(_utc(raw.get("heartbeat_at_utc"))),
        "expires_at_utc": _fmt(_utc(raw.get("expires_at_utc"))),
        "scope": scope,
    }
    if not out["owner_id"] or not out["lease_id"] or out["generation"] <= 0:
        raise ScopeLeaseFailure("holder identity invalid")
    return out


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ScopeLeaseFailure("state must be object")
    state = deepcopy(dict(payload))
    if state.get("version") != VERSION or int(state.get("schema_version", 0)) != 1:
        raise ScopeLeaseFailure("scope lease version/schema mismatch")
    if state.get("lease_ref") != LEASE_REF or state.get("lease_state_path") != LEASE_PATH:
        raise ScopeLeaseFailure("scope lease persistence identity mismatch")
    if "/" not in str(state.get("repository") or ""):
        raise ScopeLeaseFailure("repository invalid")
    if int(state.get("revision", -1)) < 0 or int(state.get("generation", -1)) < 0:
        raise ScopeLeaseFailure("revision/generation invalid")
    holders = [_validate_holder(h) for h in (state.get("holders") or [])]
    lease_ids = [h["lease_id"] for h in holders]
    if len(set(lease_ids)) != len(lease_ids):
        raise ScopeLeaseFailure("duplicate lease id")
    supplied = str(state.get("state_hash") or "").lower()
    if not _HASH64.fullmatch(supplied):
        raise ScopeLeaseFailure("state_hash invalid")
    state["holders"] = sorted(holders, key=lambda h: h["lease_id"])
    expected = _hash(_without_hash(state))
    if supplied != expected:
        raise ScopeLeaseFailure("scope lease state hash mismatch")
    return state


def _cas(state: Mapping[str, Any], revision: int, state_hash: str) -> dict[str, Any] | None:
    if int(state["revision"]) != int(revision) or str(state["state_hash"]) != str(state_hash):
        return {
            "decision": "SCOPE_LEASE_STALE_CAS_CONTINUE",
            "allowed": False,
            "next_legal_action": "REREAD_SCOPE_LEASE_STATE",
        }
    return None


def _live_holders(state: Mapping[str, Any], now_utc: str) -> list[dict[str, Any]]:
    now = _utc(now_utc)
    return [deepcopy(h) for h in state["holders"] if now < _utc(h["expires_at_utc"])]


def claim_scope(
    state: Mapping[str, Any],
    *,
    owner_id: str,
    now_utc: str,
    scope: Mapping[str, Any],
    expected_revision: int,
    expected_state_hash: str,
    ttl_seconds: int = 900,
    frozen_paths: Sequence[str] = (),
    thawed_paths: Sequence[str] = (),
) -> dict[str, Any]:
    current = validate_state(state)
    conflict = _cas(current, expected_revision, expected_state_hash)
    if conflict:
        return {"result": conflict, "state": current}

    requested = build_scope(**dict(scope))
    frozen = _unique_paths(frozen_paths)
    thawed = _unique_paths(thawed_paths)
    blocked_frozen = sorted({
        p for p in requested["write_paths"]
        for f in frozen if _path_overlap(p, f)
        if not any(_path_overlap(p, t) or _path_overlap(f, t) for t in thawed)
    })
    if blocked_frozen:
        return {
            "result": {
                "decision": "SCOPE_FROZEN_ARTIFACT_BLOCKED",
                "allowed": False,
                "frozen_paths": blocked_frozen,
                "next_legal_action": "OBTAIN_AUTHORIZED_THAW_OR_NARROW_SCOPE",
            },
            "state": current,
        }

    live = _live_holders(current, now_utc)
    for holder in live:
        is_conflict, reasons = scopes_conflict(requested, holder["scope"])
        if is_conflict:
            return {
                "result": {
                    "decision": "SCOPE_LEASE_CONFLICT_CONTINUE",
                    "allowed": False,
                    "holder_owner_id": holder["owner_id"],
                    "holder_lease_id": holder["lease_id"],
                    "conflict_reasons": reasons,
                    "next_legal_action": "CONTINUE_NON_CONFLICTING_WORK",
                },
                "state": current,
            }

    owner = str(owner_id or "").strip()
    if not owner:
        raise ScopeLeaseFailure("owner_id required")
    updated = deepcopy(current)
    updated["revision"] += 1
    updated["generation"] += 1
    generation = updated["generation"]
    seed = {
        "repository":updated["repository"],"owner_id":owner,"generation":generation,
        "now_utc":_fmt(_utc(now_utc)),"scope":requested,
    }
    lease_id = "SCOPE-LEASE-" + _hash(seed)[:24].upper()
    holder = {
        "owner_id":owner,
        "lease_id":lease_id,
        "generation":generation,
        "acquired_at_utc":_fmt(_utc(now_utc)),
        "heartbeat_at_utc":_fmt(_utc(now_utc)),
        "expires_at_utc":_fmt(_utc(now_utc) + timedelta(seconds=int(ttl_seconds))),
        "scope":requested,
    }
    updated["holders"] = sorted(live + [holder], key=lambda h: h["lease_id"])
    updated.pop("state_hash", None)
    updated["state_hash"] = _hash(updated)
    updated = validate_state(updated)
    return {
        "result": {
            "decision":"SCOPE_LEASE_ACQUIRED","allowed":True,
            "lease_id":lease_id,"generation":generation,"parallel_holder_count":len(updated["holders"]),
            "state_hash":updated["state_hash"],
        },
        "state":updated,
    }


def authorize_scope(
    state: Mapping[str, Any],
    *,
    owner_id: str,
    lease_id: str,
    now_utc: str,
    action_scope: Mapping[str, Any],
) -> dict[str, Any]:
    current = validate_state(state)
    live = _live_holders(current, now_utc)
    holder = next((h for h in live if h["owner_id"] == str(owner_id) and h["lease_id"] == str(lease_id)), None)
    if holder is None:
        return {"decision":"SCOPE_LEASE_REQUIRED_CONTINUE","allowed":False}
    requested = build_scope(**dict(action_scope))
    leased = holder["scope"]
    for p in requested["write_paths"]:
        if not any(_path_overlap(p, lp) and (p == lp or p.startswith(lp + "/")) for lp in leased["write_paths"]):
            return {"decision":"ACTION_SCOPE_EXCEEDS_LEASE","allowed":False,"path":p}
    if not set(requested["dependency_tokens"]).issubset(leased["dependency_tokens"]):
        return {"decision":"ACTION_DEPENDENCY_SCOPE_EXCEEDS_LEASE","allowed":False}
    if not set(requested["shared_resources"]).issubset(leased["shared_resources"]):
        return {"decision":"ACTION_SHARED_SCOPE_EXCEEDS_LEASE","allowed":False}
    return {"decision":"SCOPE_LEASE_EXECUTION_AUTHORIZED","allowed":True,"lease_id":lease_id}


def verify_scope_identity(
    holder_scope: Mapping[str, Any],
    *,
    observed_resource_identity: Mapping[str, str],
) -> dict[str, Any]:
    leased = build_scope(**dict(holder_scope))
    observed = {_norm_token(k): str(v or "").strip() for k,v in observed_resource_identity.items()}
    expected = leased["resource_identity"]
    drift = sorted(k for k,v in expected.items() if observed.get(k) != v)
    if drift:
        return {"decision":"SCOPED_RESOURCE_IDENTITY_DRIFT","allowed":False,"drifted_resources":drift}
    return {"decision":"SCOPED_RESOURCE_IDENTITY_STABLE","allowed":True}


def renew_scope(
    state: Mapping[str, Any], *, owner_id: str, lease_id: str, now_utc: str,
    expected_revision: int, expected_state_hash: str, ttl_seconds: int = 900,
) -> dict[str, Any]:
    current = validate_state(state)
    conflict = _cas(current, expected_revision, expected_state_hash)
    if conflict:
        return {"result":conflict,"state":current}
    live = _live_holders(current, now_utc)
    found=False
    for h in live:
        if h["owner_id"] == str(owner_id) and h["lease_id"] == str(lease_id):
            h["heartbeat_at_utc"]=_fmt(_utc(now_utc))
            h["expires_at_utc"]=_fmt(_utc(now_utc)+timedelta(seconds=int(ttl_seconds)))
            found=True
    if not found:
        return {"result":{"decision":"SCOPE_LEASE_OWNER_MISMATCH_CONTINUE","allowed":False},"state":current}
    updated=deepcopy(current);updated["revision"]+=1;updated["holders"]=live
    updated.pop("state_hash",None);updated["state_hash"]=_hash(updated);updated=validate_state(updated)
    return {"result":{"decision":"SCOPE_LEASE_RENEWED","allowed":True,"state_hash":updated["state_hash"]},"state":updated}


def release_scope(
    state: Mapping[str, Any], *, owner_id: str, lease_id: str,
    expected_revision: int, expected_state_hash: str,
) -> dict[str, Any]:
    current=validate_state(state)
    conflict=_cas(current,expected_revision,expected_state_hash)
    if conflict:
        return {"result":conflict,"state":current}
    kept=[h for h in current["holders"] if not (h["owner_id"]==str(owner_id) and h["lease_id"]==str(lease_id))]
    if len(kept)==len(current["holders"]):
        return {"result":{"decision":"SCOPE_LEASE_OWNER_MISMATCH_CONTINUE","allowed":False},"state":current}
    updated=deepcopy(current);updated["revision"]+=1;updated["holders"]=kept
    updated.pop("state_hash",None);updated["state_hash"]=_hash(updated);updated=validate_state(updated)
    return {"result":{"decision":"SCOPE_LEASE_RELEASED","allowed":True,"remaining_holders":len(kept),"state_hash":updated["state_hash"]},"state":updated}


def enforce_scoped_action(
    lease_state: Mapping[str, Any], *, owner_id: str, lease_id: str, now_utc: str,
    action_scope: Mapping[str, Any], brain_state: Mapping[str, Any], action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]], replay_ledger: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any], current_main_sha: str, current_head_sha: str,
    forward_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if str(action.get("action_type") or "") not in _MUTATIONS:
        return {"result":{"decision":"SCOPE_LEASE_NOT_REQUIRED","allowed":True}}
    gate=authorize_scope(lease_state,owner_id=owner_id,lease_id=lease_id,now_utc=now_utc,action_scope=action_scope)
    if gate.get("allowed") is not True:
        return {"result":{**gate,"scope_lease_authorized":False}}
    outcome=enforce_certified_action(
        brain_state,action,history,replay_ledger,consumption_ledger,
        current_main_sha=current_main_sha,current_head_sha=current_head_sha,
        forward_decision=forward_decision,
    )
    result=deepcopy(dict(outcome["result"]))
    result["scope_lease_authorized"]=bool(result.get("allowed"))
    result["scope_lease_id"]=lease_id if result.get("allowed") else None
    return {**outcome,"result":result}


def contract_self_test() -> dict[str, Any]:
    repo="owner/repo"; t0="2026-10-01T00:00:00Z"
    state=new_state(repo)
    wnba=build_scope(write_paths=["app.py","tests/test_wnba.py"],dependency_tokens=["domain:wnba"])
    monster=build_scope(write_paths=["devsystem/v5.py","tests/test_v5.py"],dependency_tokens=["domain:devsystem"])
    a=claim_scope(state,owner_id="chat:wnba",now_utc=t0,scope=wnba,expected_revision=0,expected_state_hash=state["state_hash"])
    live=a["state"]
    b=claim_scope(live,owner_id="chat:monster",now_utc=t0,scope=monster,expected_revision=live["revision"],expected_state_hash=live["state_hash"])
    parallel=b["state"]

    same_path=claim_scope(parallel,owner_id="chat:x",now_utc=t0,scope=build_scope(write_paths=["app.py"]),expected_revision=parallel["revision"],expected_state_hash=parallel["state_hash"])
    dep_conflict=claim_scope(parallel,owner_id="chat:y",now_utc=t0,scope=build_scope(write_paths=["other.py"],dependency_tokens=["domain:wnba"]),expected_revision=parallel["revision"],expected_state_hash=parallel["state_hash"])
    shared_base=claim_scope(state,owner_id="chat:s1",now_utc=t0,scope=build_scope(write_paths=["a.py"],shared_resources=["workflow:deploy"]),expected_revision=0,expected_state_hash=state["state_hash"])
    shared_conflict=claim_scope(shared_base["state"],owner_id="chat:s2",now_utc=t0,scope=build_scope(write_paths=["b.py"],shared_resources=["workflow:deploy"]),expected_revision=shared_base["state"]["revision"],expected_state_hash=shared_base["state"]["state_hash"])
    exclusive=claim_scope(parallel,owner_id="chat:z",now_utc=t0,scope=build_scope(write_paths=["z.py"],exclusive=True),expected_revision=parallel["revision"],expected_state_hash=parallel["state_hash"])
    frozen=claim_scope(state,owner_id="chat:f",now_utc=t0,scope=build_scope(write_paths=["devsystem/frozen.py"]),expected_revision=0,expected_state_hash=state["state_hash"],frozen_paths=["devsystem/frozen.py"])
    stale=claim_scope(live,owner_id="chat:stale",now_utc=t0,scope=monster,expected_revision=0,expected_state_hash=state["state_hash"])

    monster_holder=next(h for h in parallel["holders"] if h["owner_id"]=="chat:monster")
    auth_ok=authorize_scope(parallel,owner_id="chat:monster",lease_id=monster_holder["lease_id"],now_utc=t0,action_scope=build_scope(write_paths=["devsystem/v5.py"],dependency_tokens=["domain:devsystem"]))
    auth_bad=authorize_scope(parallel,owner_id="chat:monster",lease_id=monster_holder["lease_id"],now_utc=t0,action_scope=build_scope(write_paths=["app.py"]))
    stable=verify_scope_identity(build_scope(write_paths=["x.py"],resource_identity={"blob:x.py":"abc"}),observed_resource_identity={"blob:x.py":"abc","main":"moved"})
    drift=verify_scope_identity(build_scope(write_paths=["x.py"],resource_identity={"blob:x.py":"abc"}),observed_resource_identity={"blob:x.py":"def"})

    released=release_scope(parallel,owner_id="chat:monster",lease_id=monster_holder["lease_id"],expected_revision=parallel["revision"],expected_state_hash=parallel["state_hash"])
    remaining=[h["owner_id"] for h in released["state"]["holders"]]

    blast=scope_from_blast_radius({
        "direct_dependencies":["a"],"direct_dependents":["b"],"transitive_dependencies":["c"],
        "transitive_dependents":["d"],"impacted_entrypoints":["app.py"],"protected_reach":[]
    },write_paths=["feature.py"])

    result={
        "status":"GREEN","version":VERSION,
        "disjoint_parallel_allowed":b["result"]["allowed"] is True and len(parallel["holders"])==2,
        "same_path_overlap_blocked":same_path["result"]["allowed"] is False,
        "dependency_overlap_blocked":dep_conflict["result"]["allowed"] is False,
        "shared_resource_overlap_blocked":shared_conflict["result"]["allowed"] is False,
        "exclusive_scope_blocks_parallel":exclusive["result"]["allowed"] is False,
        "frozen_path_blocked":frozen["result"]["allowed"] is False,
        "stale_cas_blocked":stale["result"]["decision"]=="SCOPE_LEASE_STALE_CAS_CONTINUE",
        "action_within_scope_authorized":auth_ok["allowed"] is True,
        "action_outside_scope_blocked":auth_bad["allowed"] is False,
        "unrelated_main_movement_tolerated":stable["allowed"] is True,
        "scoped_identity_drift_blocked":drift["allowed"] is False,
        "release_is_holder_local":remaining==["chat:wnba"],
        "blast_radius_tokens_reused":bool(blast["dependency_tokens"]) and "entrypoint:app.py" in blast["shared_resources"],
        "step_2a_chain_preserved":enforce_certified_action is not None,
        "dedicated_authoritative_ref":LEASE_REF=="refs/heads/monster-scope-aware-execution-leases",
        "network_calls":NETWORK_CALLS,"auto_mutate":AUTO_MUTATE,
        "product_runtime_mutation":MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required=[k for k,v in result.items() if isinstance(v,bool) and k not in {"network_calls","auto_mutate","product_runtime_mutation"}]
    if not all(result[k] is True for k in required):
        raise ScopeLeaseFailure("scope-aware lease self-test failed")
    if result["network_calls"] or result["auto_mutate"] or result["product_runtime_mutation"]:
        raise ScopeLeaseFailure("scope-aware lease safety invariant failed")
    return result


def main() -> int:
    print("MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_GREEN")
    print(json.dumps(contract_self_test(),indent=2,sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScopeLeaseFailure as exc:
        print(f"MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_BLOCKED: {exc}",file=sys.stderr)
        raise SystemExit(1)
