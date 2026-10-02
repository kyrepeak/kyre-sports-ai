"""MONSTER V7 Step 4 — Shared Resource Lease Sharding V1.

Adds shard-aware conflict detection in front of the frozen V5 scope-aware lease
engine without modifying that engine.

V5 shared-resource conflicts are exact-token based. This module compiles a
coarse shared resource into deterministic child shard tokens such as:

    workflow:devsystem-targeted-ci#shard[domain=cfb,lane=permanent-contract]

and provides a shard-aware claim wrapper with these rules:

- an unsharded parent is GLOBAL and conflicts with every child shard;
- identical shards conflict;
- child shards are disjoint only when at least one shared dimension explicitly
  differs (domain=cfb vs domain=wnba, lane=a vs lane=b);
- incomparable/ambiguous dimensions fail closed and conflict;
- path/dependency/exclusive conflicts continue to use the V5 engine;
- CAS, frozen-path checks, TTL handling, and actual lease mutation are delegated
  to the frozen V5 claim_scope implementation.

The module performs no network calls and grants no mutation authority itself.
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.scope_aware_execution_lease_v1 import (
    VERSION as SCOPE_LEASE_VERSION,
    build_scope,
    claim_scope,
    scopes_conflict,
    validate_state,
)
from devsystem.monotonic_state_ownership_guard_v1 import (
    VERSION as OWNERSHIP_GUARD_VERSION,
)

VERSION = "MONSTER_V7_SHARED_RESOURCE_LEASE_SHARDING_V1"
REQUIRED_SCOPE_LEASE_VERSION = "MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_V1"
REQUIRED_OWNERSHIP_VERSION = "MONSTER_V7_MONOTONIC_STATE_OWNERSHIP_GUARD_V1"

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False

_SHARD_RE = re.compile(r"^(?P<parent>.+)#shard\[(?P<body>[^\]]+)\]$")
_PART_RE = re.compile(r"^[a-z0-9._/-]+$")


class SharedResourceLeaseShardingFailure(RuntimeError):
    pass


def _token(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not out:
        raise SharedResourceLeaseShardingFailure(f"{field} is required")
    return out


def _part(value: Any, field: str) -> str:
    out = _token(value, field)
    if not _PART_RE.fullmatch(out):
        raise SharedResourceLeaseShardingFailure(
            f"{field} contains unsupported shard characters"
        )
    return out


def shard_resource(
    parent_resource: str,
    dimensions: Mapping[str, Any],
) -> str:
    parent = _token(parent_resource, "parent_resource")
    if "#shard[" in parent:
        raise SharedResourceLeaseShardingFailure(
            "parent_resource must be unsharded"
        )
    if not isinstance(dimensions, Mapping) or not dimensions:
        raise SharedResourceLeaseShardingFailure(
            "shard dimensions must be a non-empty object"
        )
    normalized: dict[str, str] = {}
    for raw_key, raw_value in dimensions.items():
        key = _part(raw_key, "shard dimension key")
        value = _part(raw_value, f"shard dimension {key}")
        if key in normalized:
            raise SharedResourceLeaseShardingFailure(
                f"duplicate shard dimension: {key}"
            )
        normalized[key] = value
    body = ",".join(f"{key}={normalized[key]}" for key in sorted(normalized))
    return f"{parent}#shard[{body}]"


def parse_resource(resource: str) -> dict[str, Any]:
    token = _token(resource, "shared resource")
    match = _SHARD_RE.fullmatch(token)
    if not match:
        if "#shard[" in token or token.endswith("]"):
            raise SharedResourceLeaseShardingFailure(
                f"malformed shard token: {token}"
            )
        return {
            "resource": token,
            "parent": token,
            "is_sharded": False,
            "dimensions": {},
        }

    parent = _token(match.group("parent"), "shard parent")
    body = match.group("body")
    dimensions: dict[str, str] = {}
    for item in body.split(","):
        if "=" not in item:
            raise SharedResourceLeaseShardingFailure(
                f"malformed shard dimension: {item}"
            )
        key_raw, value_raw = item.split("=", 1)
        key = _part(key_raw, "shard dimension key")
        value = _part(value_raw, f"shard dimension {key}")
        if key in dimensions:
            raise SharedResourceLeaseShardingFailure(
                f"duplicate shard dimension: {key}"
            )
        dimensions[key] = value
    if not dimensions:
        raise SharedResourceLeaseShardingFailure(
            "shard token requires dimensions"
        )
    canonical = shard_resource(parent, dimensions)
    if canonical != token:
        raise SharedResourceLeaseShardingFailure(
            "shard token is not canonical"
        )
    return {
        "resource": token,
        "parent": parent,
        "is_sharded": True,
        "dimensions": dimensions,
    }


def resource_pair_conflict(
    left_resource: str,
    right_resource: str,
) -> dict[str, Any]:
    left = parse_resource(left_resource)
    right = parse_resource(right_resource)

    if left["parent"] != right["parent"]:
        return {
            "conflict": False,
            "reason": "DIFFERENT_PARENT_RESOURCES",
            "parent": None,
        }

    parent = left["parent"]
    if not left["is_sharded"] or not right["is_sharded"]:
        return {
            "conflict": True,
            "reason": "GLOBAL_PARENT_OVERLAP",
            "parent": parent,
        }

    if left["resource"] == right["resource"]:
        return {
            "conflict": True,
            "reason": "IDENTICAL_SHARD",
            "parent": parent,
        }

    left_dims = left["dimensions"]
    right_dims = right["dimensions"]
    shared_keys = sorted(set(left_dims) & set(right_dims))
    contradictions = [
        key for key in shared_keys if left_dims[key] != right_dims[key]
    ]
    if contradictions:
        return {
            "conflict": False,
            "reason": "PROVABLY_DISJOINT_SHARDS",
            "parent": parent,
            "contradictory_dimensions": contradictions,
        }

    return {
        "conflict": True,
        "reason": "AMBIGUOUS_SHARD_OVERLAP",
        "parent": parent,
        "shared_dimensions": shared_keys,
    }


def shard_aware_scopes_conflict(
    left_scope: Mapping[str, Any],
    right_scope: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    left = build_scope(**dict(left_scope))
    right = build_scope(**dict(right_scope))

    base_conflict, base_reasons = scopes_conflict(left, right)
    reasons = set(base_reasons)

    for left_resource in left["shared_resources"]:
        for right_resource in right["shared_resources"]:
            pair = resource_pair_conflict(left_resource, right_resource)
            if not pair["conflict"]:
                continue
            parent = pair.get("parent")
            if not parent:
                continue
            reason = pair["reason"].lower()
            reasons.add(f"shared-shard:{parent}:{reason}")

    return bool(reasons), sorted(reasons)


def compile_sharded_scope(
    scope: Mapping[str, Any],
    shard_dimensions_by_parent: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(shard_dimensions_by_parent, Mapping):
        raise SharedResourceLeaseShardingFailure(
            "shard_dimensions_by_parent must be an object"
        )
    base = build_scope(**dict(scope))
    replacements = {
        _token(parent, "shard parent"): dims
        for parent, dims in shard_dimensions_by_parent.items()
    }
    unknown = sorted(set(replacements) - set(base["shared_resources"]))
    if unknown:
        raise SharedResourceLeaseShardingFailure(
            "cannot shard resources not present in scope: " + ", ".join(unknown)
        )

    shared: list[str] = []
    for resource in base["shared_resources"]:
        if resource in replacements:
            shared.append(shard_resource(resource, replacements[resource]))
        else:
            shared.append(resource)

    return build_scope(
        write_paths=base["write_paths"],
        dependency_tokens=base["dependency_tokens"],
        shared_resources=shared,
        resource_identity=base["resource_identity"],
        exclusive=base["exclusive"],
    )


def _utc(value: str) -> datetime:
    text = _token(value, "timestamp")
    if text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SharedResourceLeaseShardingFailure(
            f"invalid ISO timestamp: {value}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _live_holders(
    state: Mapping[str, Any],
    now_utc: str,
) -> list[dict[str, Any]]:
    current = validate_state(state)
    now = _utc(now_utc)
    return [
        deepcopy(holder)
        for holder in current["holders"]
        if now < _utc(holder["expires_at_utc"])
    ]


def claim_sharded_scope(
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
    """Shard-aware preflight, then delegate the actual mutation to V5."""
    current = validate_state(state)

    # Preserve V5 CAS semantics exactly. If caller is stale, delegate directly
    # so the authoritative V5 decision is returned before any shard diagnosis.
    if (
        int(expected_revision) != int(current["revision"])
        or str(expected_state_hash) != str(current["state_hash"])
    ):
        return claim_scope(
            current,
            owner_id=owner_id,
            now_utc=now_utc,
            scope=scope,
            expected_revision=expected_revision,
            expected_state_hash=expected_state_hash,
            ttl_seconds=ttl_seconds,
            frozen_paths=frozen_paths,
            thawed_paths=thawed_paths,
        )

    requested = build_scope(**dict(scope))
    for holder in _live_holders(current, now_utc):
        is_conflict, reasons = shard_aware_scopes_conflict(
            requested,
            holder["scope"],
        )
        if is_conflict:
            return {
                "result": {
                    "decision": "SHARDED_SCOPE_LEASE_CONFLICT_CONTINUE",
                    "allowed": False,
                    "holder_owner_id": holder["owner_id"],
                    "holder_lease_id": holder["lease_id"],
                    "conflict_reasons": reasons,
                    "next_legal_action": "CONTINUE_NON_CONFLICTING_SHARD",
                },
                "state": current,
            }

    return claim_scope(
        current,
        owner_id=owner_id,
        now_utc=now_utc,
        scope=requested,
        expected_revision=expected_revision,
        expected_state_hash=expected_state_hash,
        ttl_seconds=ttl_seconds,
        frozen_paths=frozen_paths,
        thawed_paths=thawed_paths,
    )


def migration_preview(
    holders: Sequence[Mapping[str, Any]],
    *,
    parent_resource: str,
    dimensions_by_owner: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    parent = _token(parent_resource, "parent_resource")
    if not isinstance(dimensions_by_owner, Mapping):
        raise SharedResourceLeaseShardingFailure(
            "dimensions_by_owner must be an object"
        )
    rows: list[dict[str, Any]] = []
    for holder in holders:
        owner = _text_owner(holder)
        scope = build_scope(**dict(holder.get("scope") or {}))
        if parent not in scope["shared_resources"]:
            continue
        dims = dimensions_by_owner.get(owner)
        if not dims:
            rows.append(
                {
                    "owner_id": owner,
                    "decision": "KEEP_GLOBAL_FAIL_CLOSED",
                    "parent_resource": parent,
                    "reason": "MISSING_OWNER_SHARD_DIMENSIONS",
                }
            )
            continue
        rows.append(
            {
                "owner_id": owner,
                "decision": "MIGRATE_TO_SHARD",
                "parent_resource": parent,
                "shard_resource": shard_resource(parent, dims),
            }
        )
    return {
        "version": VERSION,
        "parent_resource": parent,
        "holders_examined": len(holders),
        "migration_rows": rows,
        "auto_mutate": False,
        "mutation_authority": False,
    }


def _text_owner(holder: Mapping[str, Any]) -> str:
    if not isinstance(holder, Mapping):
        raise SharedResourceLeaseShardingFailure("holder must be an object")
    return _token(holder.get("owner_id"), "holder owner_id")


def contract_self_test() -> dict[str, Any]:
    from devsystem.scope_aware_execution_lease_v1 import new_state, release_scope

    if SCOPE_LEASE_VERSION != REQUIRED_SCOPE_LEASE_VERSION:
        raise SharedResourceLeaseShardingFailure("V5 lease version mismatch")
    if OWNERSHIP_GUARD_VERSION != REQUIRED_OWNERSHIP_VERSION:
        raise SharedResourceLeaseShardingFailure(
            "Step-3 ownership version mismatch"
        )

    parent = "workflow:devsystem-targeted-ci"
    cfb = shard_resource(parent, {"domain": "cfb", "lane": "permanent"})
    wnba = shard_resource(parent, {"domain": "wnba", "lane": "permanent"})
    cfb_fast = shard_resource(parent, {"domain": "cfb", "lane": "fast"})
    cfb_domain_only = shard_resource(parent, {"domain": "cfb"})
    lane_only = shard_resource(parent, {"lane": "permanent"})

    pair_disjoint = resource_pair_conflict(cfb, wnba)
    pair_same_domain_diff_lane = resource_pair_conflict(cfb, cfb_fast)
    pair_ambiguous = resource_pair_conflict(cfb_domain_only, lane_only)
    pair_global = resource_pair_conflict(parent, cfb)

    base = new_state("owner/repo")
    now = "2026-10-02T01:00:00Z"

    global_claim = claim_scope(
        base,
        owner_id="global-holder",
        now_utc=now,
        scope=build_scope(
            write_paths=["global.py"],
            shared_resources=[parent],
        ),
        expected_revision=base["revision"],
        expected_state_hash=base["state_hash"],
        ttl_seconds=1800,
    )
    global_blocks_child = claim_sharded_scope(
        global_claim["state"],
        owner_id="cfb",
        now_utc=now,
        scope=build_scope(
            write_paths=["cfb.py"],
            shared_resources=[cfb],
        ),
        expected_revision=global_claim["state"]["revision"],
        expected_state_hash=global_claim["state"]["state_hash"],
    )

    global_holder = global_claim["state"]["holders"][0]
    released = release_scope(
        global_claim["state"],
        owner_id="global-holder",
        lease_id=global_holder["lease_id"],
        expected_revision=global_claim["state"]["revision"],
        expected_state_hash=global_claim["state"]["state_hash"],
    )

    cfb_claim = claim_sharded_scope(
        released["state"],
        owner_id="cfb",
        now_utc=now,
        scope=build_scope(
            write_paths=["cfb.py"],
            shared_resources=[cfb],
        ),
        expected_revision=released["state"]["revision"],
        expected_state_hash=released["state"]["state_hash"],
    )
    wnba_claim = claim_sharded_scope(
        cfb_claim["state"],
        owner_id="wnba",
        now_utc=now,
        scope=build_scope(
            write_paths=["wnba.py"],
            shared_resources=[wnba],
        ),
        expected_revision=cfb_claim["state"]["revision"],
        expected_state_hash=cfb_claim["state"]["state_hash"],
    )
    same_shard = claim_sharded_scope(
        wnba_claim["state"],
        owner_id="cfb-2",
        now_utc=now,
        scope=build_scope(
            write_paths=["cfb2.py"],
            shared_resources=[cfb],
        ),
        expected_revision=wnba_claim["state"]["revision"],
        expected_state_hash=wnba_claim["state"]["state_hash"],
    )
    cfb_fast_claim = claim_sharded_scope(
        wnba_claim["state"],
        owner_id="cfb-fast",
        now_utc=now,
        scope=build_scope(
            write_paths=["cfb-fast.py"],
            shared_resources=[cfb_fast],
        ),
        expected_revision=wnba_claim["state"]["revision"],
        expected_state_hash=wnba_claim["state"]["state_hash"],
    )

    ambiguous_state = new_state("owner/repo")
    domain_claim = claim_sharded_scope(
        ambiguous_state,
        owner_id="domain",
        now_utc=now,
        scope=build_scope(
            write_paths=["domain.py"],
            shared_resources=[cfb_domain_only],
        ),
        expected_revision=ambiguous_state["revision"],
        expected_state_hash=ambiguous_state["state_hash"],
    )
    ambiguous_claim = claim_sharded_scope(
        domain_claim["state"],
        owner_id="lane",
        now_utc=now,
        scope=build_scope(
            write_paths=["lane.py"],
            shared_resources=[lane_only],
        ),
        expected_revision=domain_claim["state"]["revision"],
        expected_state_hash=domain_claim["state"]["state_hash"],
    )

    stale = claim_sharded_scope(
        wnba_claim["state"],
        owner_id="stale",
        now_utc=now,
        scope=build_scope(
            write_paths=["stale.py"],
            shared_resources=[shard_resource(parent, {"domain": "mlb"})],
        ),
        expected_revision=0,
        expected_state_hash=base["state_hash"],
    )

    frozen = claim_sharded_scope(
        new_state("owner/repo"),
        owner_id="frozen",
        now_utc=now,
        scope=build_scope(
            write_paths=["devsystem/frozen.py"],
            shared_resources=[shard_resource(parent, {"domain": "nfl"})],
        ),
        expected_revision=0,
        expected_state_hash=new_state("owner/repo")["state_hash"],
        frozen_paths=["devsystem/frozen.py"],
    )

    compiled = compile_sharded_scope(
        build_scope(
            write_paths=["x.py"],
            shared_resources=[parent, "deploy:pickvault"],
        ),
        {parent: {"domain": "cfb", "lane": "pr"}},
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "v5_scope_lease_version_bound": (
            SCOPE_LEASE_VERSION == REQUIRED_SCOPE_LEASE_VERSION
        ),
        "step3_ownership_version_bound": (
            OWNERSHIP_GUARD_VERSION == REQUIRED_OWNERSHIP_VERSION
        ),
        "different_domain_shards_disjoint": (
            pair_disjoint["conflict"] is False
            and pair_disjoint["reason"] == "PROVABLY_DISJOINT_SHARDS"
        ),
        "same_domain_different_lane_disjoint": (
            pair_same_domain_diff_lane["conflict"] is False
        ),
        "ambiguous_dimensions_fail_closed": (
            pair_ambiguous["conflict"] is True
            and pair_ambiguous["reason"] == "AMBIGUOUS_SHARD_OVERLAP"
        ),
        "global_parent_conflicts_with_child": (
            pair_global["conflict"] is True
            and pair_global["reason"] == "GLOBAL_PARENT_OVERLAP"
        ),
        "live_global_holder_blocks_child_shard": (
            global_blocks_child["result"]["allowed"] is False
            and global_blocks_child["result"]["decision"]
            == "SHARDED_SCOPE_LEASE_CONFLICT_CONTINUE"
        ),
        "disjoint_cfb_wnba_claims_parallel": (
            cfb_claim["result"]["allowed"] is True
            and wnba_claim["result"]["allowed"] is True
            and len(wnba_claim["state"]["holders"]) == 2
        ),
        "identical_shard_blocks": (
            same_shard["result"]["allowed"] is False
        ),
        "same_domain_different_lane_claims_parallel": (
            cfb_fast_claim["result"]["allowed"] is True
        ),
        "ambiguous_claim_blocks": (
            ambiguous_claim["result"]["allowed"] is False
        ),
        "v5_stale_cas_preserved": (
            stale["result"]["decision"] == "SCOPE_LEASE_STALE_CAS_CONTINUE"
        ),
        "v5_frozen_path_guard_preserved": (
            frozen["result"]["decision"] == "SCOPE_FROZEN_ARTIFACT_BLOCKED"
        ),
        "scope_compiler_replaces_only_selected_parent": (
            cfb not in compiled["shared_resources"]
            and shard_resource(parent, {"domain": "cfb", "lane": "pr"})
            in compiled["shared_resources"]
            and "deploy:pickvault" in compiled["shared_resources"]
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }

    required = (
        "v5_scope_lease_version_bound",
        "step3_ownership_version_bound",
        "different_domain_shards_disjoint",
        "same_domain_different_lane_disjoint",
        "ambiguous_dimensions_fail_closed",
        "global_parent_conflicts_with_child",
        "live_global_holder_blocks_child_shard",
        "disjoint_cfb_wnba_claims_parallel",
        "identical_shard_blocks",
        "same_domain_different_lane_claims_parallel",
        "ambiguous_claim_blocks",
        "v5_stale_cas_preserved",
        "v5_frozen_path_guard_preserved",
        "scope_compiler_replaces_only_selected_parent",
    )
    if not all(result[name] is True for name in required):
        raise SharedResourceLeaseShardingFailure(
            "shared resource lease sharding self-test failed"
        )
    if (
        result["network_calls"]
        or result["auto_mutate"]
        or result["may_modify_product_runtime"]
        or result["mutation_authority_granted"]
    ):
        raise SharedResourceLeaseShardingFailure(
            "read-only safety invariant failed"
        )
    return result


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V7_STEP4_SHARED_RESOURCE_LEASE_SHARDING_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SharedResourceLeaseShardingFailure as exc:
        print(
            "MONSTER_V7_STEP4_SHARED_RESOURCE_LEASE_SHARDING_BLOCKED: "
            + str(exc)
        )
        raise SystemExit(1)
