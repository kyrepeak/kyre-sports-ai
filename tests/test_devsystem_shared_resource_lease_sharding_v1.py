from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.shared_resource_lease_sharding_v1 import (
    OWNERSHIP_GUARD_VERSION,
    SCOPE_LEASE_VERSION,
    SharedResourceLeaseShardingFailure,
    claim_sharded_scope,
    compile_sharded_scope,
    contract_self_test,
    migration_preview,
    parse_resource,
    resource_pair_conflict,
    shard_aware_scopes_conflict,
    shard_resource,
)
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    new_state,
    release_scope,
)


PARENT = "workflow:devsystem-targeted-ci"


def _shard(**dims):
    return shard_resource(PARENT, dims)


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["different_domain_shards_disjoint"] is True
    assert result["global_parent_conflicts_with_child"] is True
    assert result["v5_stale_cas_preserved"] is True
    assert result["v5_frozen_path_guard_preserved"] is True


def test_shard_token_is_canonical_and_sorted():
    token = shard_resource(PARENT, {"lane": "fast", "domain": "cfb"})
    assert token == (
        "workflow:devsystem-targeted-ci#shard[domain=cfb,lane=fast]"
    )
    parsed = parse_resource(token)
    assert parsed["parent"] == PARENT
    assert parsed["dimensions"] == {"domain": "cfb", "lane": "fast"}


def test_different_domain_shards_are_provably_disjoint():
    result = resource_pair_conflict(
        _shard(domain="cfb", lane="permanent"),
        _shard(domain="wnba", lane="permanent"),
    )
    assert result["conflict"] is False
    assert result["reason"] == "PROVABLY_DISJOINT_SHARDS"
    assert result["contradictory_dimensions"] == ["domain"]


def test_same_domain_different_lane_is_disjoint():
    result = resource_pair_conflict(
        _shard(domain="cfb", lane="permanent"),
        _shard(domain="cfb", lane="fast"),
    )
    assert result["conflict"] is False
    assert result["contradictory_dimensions"] == ["lane"]


def test_identical_shards_conflict():
    token = _shard(domain="cfb", lane="fast")
    result = resource_pair_conflict(token, token)
    assert result["conflict"] is True
    assert result["reason"] == "IDENTICAL_SHARD"


def test_global_parent_conflicts_with_every_child():
    result = resource_pair_conflict(
        PARENT,
        _shard(domain="wnba", lane="fast"),
    )
    assert result["conflict"] is True
    assert result["reason"] == "GLOBAL_PARENT_OVERLAP"


def test_incomparable_dimensions_fail_closed():
    result = resource_pair_conflict(
        _shard(domain="cfb"),
        _shard(lane="permanent"),
    )
    assert result["conflict"] is True
    assert result["reason"] == "AMBIGUOUS_SHARD_OVERLAP"
    assert result["shared_dimensions"] == []


def test_more_specific_same_values_still_overlap():
    result = resource_pair_conflict(
        _shard(domain="cfb"),
        _shard(domain="cfb", lane="fast"),
    )
    assert result["conflict"] is True
    assert result["reason"] == "AMBIGUOUS_SHARD_OVERLAP"
    assert result["shared_dimensions"] == ["domain"]


def test_different_parent_resources_do_not_conflict():
    result = resource_pair_conflict(
        _shard(domain="cfb"),
        shard_resource("deploy:pickvault", {"domain": "cfb"}),
    )
    assert result["conflict"] is False
    assert result["reason"] == "DIFFERENT_PARENT_RESOURCES"


def test_shard_aware_scope_keeps_path_and_dependency_conflicts():
    left = build_scope(
        write_paths=["devsystem/a.py"],
        dependency_tokens=["domain:cfb"],
        shared_resources=[_shard(domain="cfb")],
    )
    right = build_scope(
        write_paths=["devsystem/a.py"],
        dependency_tokens=["domain:cfb"],
        shared_resources=[_shard(domain="wnba")],
    )
    conflict, reasons = shard_aware_scopes_conflict(left, right)
    assert conflict is True
    assert any(reason.startswith("path:") for reason in reasons)
    assert "dependency:domain:cfb" in reasons


def test_live_global_holder_blocks_child_shard():
    state = new_state("owner/repo")
    global_claim = claim_scope(
        state,
        owner_id="global",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["global.py"],
            shared_resources=[PARENT],
        ),
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=1800,
    )
    result = claim_sharded_scope(
        global_claim["state"],
        owner_id="cfb",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["cfb.py"],
            shared_resources=[_shard(domain="cfb")],
        ),
        expected_revision=global_claim["state"]["revision"],
        expected_state_hash=global_claim["state"]["state_hash"],
    )
    assert result["result"]["allowed"] is False
    assert result["result"]["decision"] == (
        "SHARDED_SCOPE_LEASE_CONFLICT_CONTINUE"
    )
    assert any(
        "global_parent_overlap" in reason
        for reason in result["result"]["conflict_reasons"]
    )


def test_distinct_domain_shards_claim_in_parallel_after_global_release():
    state = new_state("owner/repo")
    global_claim = claim_scope(
        state,
        owner_id="global",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["global.py"],
            shared_resources=[PARENT],
        ),
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    holder = global_claim["state"]["holders"][0]
    released = release_scope(
        global_claim["state"],
        owner_id="global",
        lease_id=holder["lease_id"],
        expected_revision=global_claim["state"]["revision"],
        expected_state_hash=global_claim["state"]["state_hash"],
    )

    cfb = claim_sharded_scope(
        released["state"],
        owner_id="cfb",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["cfb.py"],
            shared_resources=[_shard(domain="cfb", lane="permanent")],
        ),
        expected_revision=released["state"]["revision"],
        expected_state_hash=released["state"]["state_hash"],
    )
    wnba = claim_sharded_scope(
        cfb["state"],
        owner_id="wnba",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["wnba.py"],
            shared_resources=[_shard(domain="wnba", lane="permanent")],
        ),
        expected_revision=cfb["state"]["revision"],
        expected_state_hash=cfb["state"]["state_hash"],
    )
    assert cfb["result"]["allowed"] is True
    assert wnba["result"]["allowed"] is True
    assert {h["owner_id"] for h in wnba["state"]["holders"]} == {
        "cfb",
        "wnba",
    }


def test_same_shard_claim_is_serialized():
    state = new_state("owner/repo")
    first = claim_sharded_scope(
        state,
        owner_id="a",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["a.py"],
            shared_resources=[_shard(domain="cfb", lane="fast")],
        ),
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    second = claim_sharded_scope(
        first["state"],
        owner_id="b",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["b.py"],
            shared_resources=[_shard(domain="cfb", lane="fast")],
        ),
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )
    assert second["result"]["allowed"] is False


def test_expired_global_holder_no_longer_blocks_child():
    state = new_state("owner/repo")
    old = claim_scope(
        state,
        owner_id="old-global",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["old.py"],
            shared_resources=[PARENT],
        ),
        expected_revision=0,
        expected_state_hash=state["state_hash"],
        ttl_seconds=60,
    )
    child = claim_sharded_scope(
        old["state"],
        owner_id="child",
        now_utc="2026-10-02T01:02:00Z",
        scope=build_scope(
            write_paths=["child.py"],
            shared_resources=[_shard(domain="cfb")],
        ),
        expected_revision=old["state"]["revision"],
        expected_state_hash=old["state"]["state_hash"],
    )
    assert child["result"]["allowed"] is True


def test_stale_cas_is_delegated_to_v5():
    state = new_state("owner/repo")
    advanced = claim_sharded_scope(
        state,
        owner_id="a",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["a.py"],
            shared_resources=[_shard(domain="cfb")],
        ),
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    stale = claim_sharded_scope(
        advanced["state"],
        owner_id="b",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["b.py"],
            shared_resources=[_shard(domain="wnba")],
        ),
        expected_revision=0,
        expected_state_hash=state["state_hash"],
    )
    assert stale["result"]["decision"] == "SCOPE_LEASE_STALE_CAS_CONTINUE"


def test_frozen_path_guard_is_delegated_to_v5():
    state = new_state("owner/repo")
    result = claim_sharded_scope(
        state,
        owner_id="a",
        now_utc="2026-10-02T01:00:00Z",
        scope=build_scope(
            write_paths=["devsystem/frozen.py"],
            shared_resources=[_shard(domain="cfb")],
        ),
        expected_revision=0,
        expected_state_hash=state["state_hash"],
        frozen_paths=["devsystem/frozen.py"],
    )
    assert result["result"]["decision"] == "SCOPE_FROZEN_ARTIFACT_BLOCKED"


def test_compile_sharded_scope_only_replaces_named_parents():
    source = build_scope(
        write_paths=["x.py"],
        shared_resources=[PARENT, "deploy:pickvault"],
        resource_identity={"main:base": "abc"},
    )
    compiled = compile_sharded_scope(
        source,
        {PARENT: {"domain": "cfb", "lane": "pr"}},
    )
    assert _shard(domain="cfb", lane="pr") in compiled["shared_resources"]
    assert "deploy:pickvault" in compiled["shared_resources"]
    assert PARENT not in compiled["shared_resources"]
    assert compiled["resource_identity"] == {"main:base": "abc"}


def test_compile_unknown_parent_fails_closed():
    with pytest.raises(
        SharedResourceLeaseShardingFailure,
        match="not present in scope",
    ):
        compile_sharded_scope(
            build_scope(write_paths=["x.py"], shared_resources=[PARENT]),
            {"deploy:not-present": {"domain": "cfb"}},
        )


def test_malformed_and_noncanonical_shards_fail_closed():
    with pytest.raises(SharedResourceLeaseShardingFailure):
        parse_resource(PARENT + "#shard[domain]")
    with pytest.raises(
        SharedResourceLeaseShardingFailure,
        match="not canonical",
    ):
        parse_resource(PARENT + "#shard[lane=fast,domain=cfb]")


def test_empty_dimensions_fail_closed():
    with pytest.raises(
        SharedResourceLeaseShardingFailure,
        match="non-empty",
    ):
        shard_resource(PARENT, {})


def test_migration_preview_never_mutates_and_keeps_unknown_global():
    holders = [
        {
            "owner_id": "cfb",
            "scope": build_scope(
                write_paths=["cfb.py"],
                shared_resources=[PARENT],
            ),
        },
        {
            "owner_id": "unknown",
            "scope": build_scope(
                write_paths=["unknown.py"],
                shared_resources=[PARENT],
            ),
        },
    ]
    original = deepcopy(holders)
    result = migration_preview(
        holders,
        parent_resource=PARENT,
        dimensions_by_owner={"cfb": {"domain": "cfb"}},
    )
    assert holders == original
    assert result["auto_mutate"] is False
    assert result["mutation_authority"] is False
    assert result["migration_rows"][0]["decision"] == "MIGRATE_TO_SHARD"
    assert result["migration_rows"][1]["decision"] == "KEEP_GLOBAL_FAIL_CLOSED"


def test_frozen_dependency_versions_are_bound():
    result = contract_self_test()
    assert SCOPE_LEASE_VERSION == "MONSTER_V5_SCOPE_AWARE_EXECUTION_LEASE_V1"
    assert OWNERSHIP_GUARD_VERSION == (
        "MONSTER_V7_MONOTONIC_STATE_OWNERSHIP_GUARD_V1"
    )
    assert result["v5_scope_lease_version_bound"] is True
    assert result["step3_ownership_version_bound"] is True


def test_engine_is_read_only_and_grants_no_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
