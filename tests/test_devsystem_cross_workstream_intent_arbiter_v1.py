from __future__ import annotations

from copy import deepcopy

import pytest

from devsystem.cross_workstream_intent_arbiter_v1 import (
    CrossWorkstreamIntentFailure,
    build_intent_candidate,
    complete_intent,
    contract_self_test,
    new_state,
    reconcile_expired_intents,
    submit_intent,
    validate_state,
)
from devsystem.scope_aware_execution_lease_v1 import build_scope
from devsystem.shared_resource_lease_sharding_v1 import shard_resource


HEAD = "a" * 40
NOW = "2026-10-02T04:00:00Z"


def _scope(path="app.py", *, token="domain:app", resource="workflow:ci"):
    return build_scope(
        write_paths=[path],
        dependency_tokens=[token],
        shared_resources=[resource],
        resource_identity={"main:base": HEAD},
    )


def _candidate(
    owner,
    workstream,
    mission,
    scope=None,
    base=HEAD,
    ttl=1800,
):
    return build_intent_candidate(
        owner_id=owner,
        workstream_id=workstream,
        mission=mission,
        base_sha=base,
        scope=scope or _scope(),
        ttl_seconds=ttl,
    )


def _submit(state, candidate, now=NOW, current=HEAD, revision=None, state_hash=None):
    return submit_intent(
        state,
        candidate=candidate,
        current_main_sha=current,
        now_utc=now,
        expected_revision=state["revision"] if revision is None else revision,
        expected_state_hash=state["state_hash"] if state_hash is None else state_hash,
    )


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["semantic_duplicate_joins"] is True
    assert result["completion_promotes_waiter"] is True


def test_first_intent_is_allowed_before_branch_creation():
    state = new_state("owner/repo")
    result = _submit(
        state,
        _candidate("chat:a", "ws:a", "Build new feature"),
    )
    assert result["result"]["decision"] == "ALLOW_NEW_INTENT"
    assert result["result"]["branch_creation_allowed"] is True
    assert result["result"]["pr_creation_allowed"] is True
    assert result["result"]["lease_request_allowed"] is True
    assert result["result"]["next_legal_action"] == "RUN_PRE_MUTATION_BLAST_RADIUS_SIMULATION"


def test_semantic_duplicate_different_chat_joins_existing():
    state = new_state("owner/repo")
    first = _submit(
        state,
        _candidate("chat:a", "ws:a", "Repair CFB Top Picks"),
    )
    second = _submit(
        first["state"],
        _candidate("chat:b", "ws:b", "repair--cfb top picks!!!"),
        now="2026-10-02T04:00:10Z",
    )
    assert second["result"]["decision"] == "JOIN_EXISTING_INTENT"
    assert second["result"]["canonical_intent_id"] == first["result"]["intent_id"]
    assert second["result"]["canonical_workstream_id"] == "ws:a"
    assert second["result"]["branch_creation_allowed"] is False
    assert second["result"]["lease_request_allowed"] is False
    assert second["result"]["join_existing_continuation"] is True


def test_same_participant_resubmit_is_idempotent():
    state = new_state("owner/repo")
    candidate = _candidate("chat:a", "ws:a", "Repair page")
    first = _submit(state, candidate)
    second = _submit(
        first["state"],
        candidate,
        now="2026-10-02T04:00:10Z",
    )
    assert second["result"]["decision"] == "INTENT_ALREADY_REGISTERED"
    assert second["state"]["state_hash"] == first["state"]["state_hash"]


def test_same_mission_different_scope_is_not_semantic_duplicate():
    state = new_state("owner/repo")
    first = _submit(
        state,
        _candidate("chat:a", "ws:a", "Repair page", _scope("a.py")),
    )
    second = _submit(
        first["state"],
        _candidate("chat:b", "ws:b", "Repair page", _scope("b.py", token="domain:b", resource="workflow:b")),
        now="2026-10-02T04:00:10Z",
    )
    assert second["result"]["decision"] == "ALLOW_NEW_INTENT"


def test_conflicting_different_intent_waits_before_branch_or_lease():
    state = new_state("owner/repo")
    first = _submit(
        state,
        _candidate("chat:a", "ws:a", "Mission A"),
    )
    second = _submit(
        first["state"],
        _candidate("chat:b", "ws:b", "Mission B"),
        now="2026-10-02T04:00:10Z",
    )
    assert second["result"]["decision"] == "WAIT_ON_CONFLICTING_INTENT"
    assert second["result"]["branch_creation_allowed"] is False
    assert second["result"]["pr_creation_allowed"] is False
    assert second["result"]["lease_request_allowed"] is False
    assert second["result"]["blocked_by"][0]["intent_id"] == first["result"]["intent_id"]


def test_disjoint_shards_can_start_in_parallel():
    state = new_state("owner/repo")
    cfb = _scope(
        "cfb/page.py",
        token="sport:cfb",
        resource=shard_resource("workflow:shared-ci", {"domain": "cfb"}),
    )
    wnba = _scope(
        "wnba/page.py",
        token="sport:wnba",
        resource=shard_resource("workflow:shared-ci", {"domain": "wnba"}),
    )
    first = _submit(state, _candidate("chat:cfb", "ws:cfb", "CFB repair", cfb))
    second = _submit(
        first["state"],
        _candidate("chat:wnba", "ws:wnba", "WNBA repair", wnba),
        now="2026-10-02T04:00:10Z",
    )
    assert second["result"]["decision"] == "ALLOW_NEW_INTENT"


def test_global_parent_conflicts_with_child_shard():
    state = new_state("owner/repo")
    parent = _scope(
        "global.py",
        token="global",
        resource="workflow:shared-ci",
    )
    child = _scope(
        "cfb/page.py",
        token="sport:cfb",
        resource=shard_resource("workflow:shared-ci", {"domain": "cfb"}),
    )
    first = _submit(state, _candidate("chat:a", "ws:a", "Global CI work", parent))
    second = _submit(
        first["state"],
        _candidate("chat:b", "ws:b", "CFB CI work", child),
        now="2026-10-02T04:00:10Z",
    )
    assert second["result"]["decision"] == "WAIT_ON_CONFLICTING_INTENT"


def test_stale_base_blocks_without_registry_mutation():
    state = new_state("owner/repo")
    result = _submit(
        state,
        _candidate("chat:a", "ws:a", "Stale task", base="b" * 40),
        current=HEAD,
    )
    assert result["result"]["decision"] == "BLOCK_STALE_INTENT_BASE"
    assert result["state"]["state_hash"] == state["state_hash"]
    assert result["result"]["branch_creation_allowed"] is False


def test_stale_cas_fails_closed():
    state = new_state("owner/repo")
    result = _submit(
        state,
        _candidate("chat:a", "ws:a", "Task"),
        revision=99,
    )
    assert result["result"]["decision"] == "INTENT_REGISTRY_STALE_CAS"
    assert result["state"]["state_hash"] == state["state_hash"]


def test_only_leader_can_complete_canonical_intent():
    state = new_state("owner/repo")
    first = _submit(state, _candidate("chat:a", "ws:a", "Task"))
    joined = _submit(
        first["state"],
        _candidate("chat:b", "ws:b", "Task"),
        now="2026-10-02T04:00:10Z",
    )
    result = complete_intent(
        joined["state"],
        intent_id=first["result"]["intent_id"],
        owner_id="chat:b",
        now_utc="2026-10-02T04:00:20Z",
        expected_revision=joined["state"]["revision"],
        expected_state_hash=joined["state"]["state_hash"],
    )
    assert result["result"]["decision"] == "INTENT_COMPLETION_OWNER_MISMATCH"
    assert result["state"]["state_hash"] == joined["state"]["state_hash"]


def test_completion_promotes_oldest_waiter():
    state = new_state("owner/repo")
    first = _submit(state, _candidate("chat:a", "ws:a", "Mission A"))
    wait1 = _submit(
        first["state"],
        _candidate("chat:b", "ws:b", "Mission B"),
        now="2026-10-02T04:00:10Z",
    )
    wait2 = _submit(
        wait1["state"],
        _candidate("chat:c", "ws:c", "Mission C"),
        now="2026-10-02T04:00:20Z",
    )
    done = complete_intent(
        wait2["state"],
        intent_id=first["result"]["intent_id"],
        owner_id="chat:a",
        now_utc="2026-10-02T04:00:30Z",
        expected_revision=wait2["state"]["revision"],
        expected_state_hash=wait2["state"]["state_hash"],
    )
    assert wait1["result"]["intent_id"] in done["result"]["promoted_intent_ids"]
    rows={x["intent_id"]:x for x in done["state"]["intents"]}
    assert rows[wait1["result"]["intent_id"]]["status"] == "ACTIVE"
    assert rows[wait2["result"]["intent_id"]]["status"] == "WAITING"


def test_completion_can_promote_multiple_disjoint_waiters():
    state = new_state("owner/repo")
    global_scope=build_scope(
        write_paths=["root"],
        shared_resources=["workflow:shared-ci"],
        resource_identity={"main:base": HEAD},
    )
    cfb=_scope(
        "cfb/page.py",
        token="sport:cfb",
        resource=shard_resource("workflow:shared-ci", {"domain":"cfb"}),
    )
    wnba=_scope(
        "wnba/page.py",
        token="sport:wnba",
        resource=shard_resource("workflow:shared-ci", {"domain":"wnba"}),
    )
    first=_submit(state,_candidate("chat:g","ws:g","Global work",global_scope))
    a=_submit(first["state"],_candidate("chat:c","ws:c","CFB work",cfb),now="2026-10-02T04:00:10Z")
    b=_submit(a["state"],_candidate("chat:w","ws:w","WNBA work",wnba),now="2026-10-02T04:00:20Z")
    done=complete_intent(
        b["state"],
        intent_id=first["result"]["intent_id"],
        owner_id="chat:g",
        now_utc="2026-10-02T04:00:30Z",
        expected_revision=b["state"]["revision"],
        expected_state_hash=b["state"]["state_hash"],
    )
    assert set(done["result"]["promoted_intent_ids"]) == {
        a["result"]["intent_id"], b["result"]["intent_id"]
    }


def test_expired_active_intent_no_longer_blocks():
    state = new_state("owner/repo")
    short = _candidate("chat:a", "ws:a", "Mission A", ttl=60)
    first = _submit(state, short)
    second = _submit(
        first["state"],
        _candidate("chat:b", "ws:b", "Mission B"),
        now="2026-10-02T04:01:01Z",
    )
    assert second["result"]["decision"] == "ALLOW_NEW_INTENT"
    rows={x["intent_id"]:x for x in second["state"]["intents"]}
    assert rows[first["result"]["intent_id"]]["status"] == "EXPIRED"


def test_reconcile_expiry_promotes_waiter_without_polling_loop():
    state = new_state("owner/repo")
    first = _submit(state, _candidate("chat:a", "ws:a", "Mission A", ttl=60))
    wait = _submit(
        first["state"],
        _candidate("chat:b", "ws:b", "Mission B", ttl=1800),
        now="2026-10-02T04:00:10Z",
    )
    result = reconcile_expired_intents(
        wait["state"],
        now_utc="2026-10-02T04:01:01Z",
        expected_revision=wait["state"]["revision"],
        expected_state_hash=wait["state"]["state_hash"],
    )
    assert first["result"]["intent_id"] in result["result"]["expired_intent_ids"]
    assert wait["result"]["intent_id"] in result["result"]["promoted_intent_ids"]


def test_duplicate_of_waiting_intent_joins_waiting_without_new_queue_entry():
    state = new_state("owner/repo")
    first = _submit(state, _candidate("chat:a", "ws:a", "Mission A"))
    waiting_candidate = _candidate("chat:b", "ws:b", "Mission B")
    waiting = _submit(first["state"], waiting_candidate, now="2026-10-02T04:00:10Z")
    duplicate = _submit(
        waiting["state"],
        _candidate("chat:c", "ws:c", "mission---b"),
        now="2026-10-02T04:00:20Z",
    )
    assert duplicate["result"]["decision"] == "JOIN_WAITING_INTENT"
    assert duplicate["result"]["canonical_intent_id"] == waiting["result"]["intent_id"]
    assert len(duplicate["state"]["intents"]) == 2


def test_candidate_fingerprint_tamper_fails_closed():
    state = new_state("owner/repo")
    candidate = _candidate("chat:a", "ws:a", "Mission A")
    candidate["semantic_fingerprint"] = "0" * 64
    with pytest.raises(
        CrossWorkstreamIntentFailure,
        match="semantic fingerprint mismatch",
    ):
        _submit(state, candidate)


def test_state_tamper_fails_closed():
    state = new_state("owner/repo")
    first = _submit(state, _candidate("chat:a", "ws:a", "Mission A"))
    tampered = deepcopy(first["state"])
    tampered["revision"] += 1
    with pytest.raises(
        CrossWorkstreamIntentFailure,
        match="state hash mismatch",
    ):
        validate_state(tampered)


def test_intent_arbiter_is_read_only_and_grants_no_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
