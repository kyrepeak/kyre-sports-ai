from __future__ import annotations

import pytest

from devsystem.atomic_wait_queue_lease_handoff_v1 import (
    QUEUE_PATH,
    QUEUE_REF,
    AtomicWaitQueueFailure,
    atomic_release_and_handoff,
    cancel_waiter,
    contract_self_test,
    enqueue_waiter,
    new_queue_state,
    queue_position,
    reconcile_queue_from_lease,
    validate_queue_state,
)
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    new_state as new_lease_state,
)
from devsystem.shared_resource_lease_sharding_v1 import shard_resource


PARENT = "workflow:devsystem-targeted-ci"
QUEUE_KEY = shard_resource(PARENT, {"domain": "cfb", "lane": "permanent"})
NOW = "2026-10-02T01:00:00Z"


def _holder():
    lease = new_lease_state("owner/repo")
    claimed = claim_scope(
        lease,
        owner_id="holder",
        now_utc=NOW,
        scope=build_scope(
            write_paths=["holder.py"],
            shared_resources=[QUEUE_KEY],
        ),
        expected_revision=0,
        expected_state_hash=lease["state_hash"],
        ttl_seconds=1800,
    )
    return claimed


def _enqueue(state, owner, blocker, path, **kwargs):
    return enqueue_waiter(
        state,
        owner_id=owner,
        queue_key=QUEUE_KEY,
        blocked_by_lease_id=blocker,
        scope=build_scope(
            write_paths=[path],
            shared_resources=[QUEUE_KEY],
        ),
        now_utc=kwargs.pop("now_utc", NOW),
        expected_revision=kwargs.pop("expected_revision", state["revision"]),
        expected_state_hash=kwargs.pop("expected_state_hash", state["state_hash"]),
        ttl_seconds=kwargs.pop("ttl_seconds", 1800),
        **kwargs,
    )


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["fifo_positions_preserved"] is True
    assert result["atomic_release_claim_committed"] is True
    assert result["head_blocked_prevents_leapfrog"] is True
    assert result["delayed_queue_ack_reconciles_from_lease"] is True


def test_new_queue_state_has_dedicated_persistence_identity():
    state = new_queue_state("owner/repo")
    assert state["queue_ref"] == QUEUE_REF
    assert state["queue_state_path"] == QUEUE_PATH
    assert state["revision"] == 0
    assert state["generation"] == 0
    assert state["tickets"] == []
    assert state["handoff_receipts"] == []


def test_fifo_ticket_positions_are_stable():
    holder = _holder()
    lease_id = holder["result"]["lease_id"]
    queue = new_queue_state("owner/repo")
    a = _enqueue(queue, "a", lease_id, "a.py")
    b = _enqueue(a["state"], "b", lease_id, "b.py")
    c = _enqueue(b["state"], "c", lease_id, "c.py")
    assert queue_position(
        c["state"], ticket_id=a["result"]["ticket_id"], now_utc=NOW
    )["position"] == 1
    assert queue_position(
        c["state"], ticket_id=b["result"]["ticket_id"], now_utc=NOW
    )["position"] == 2
    assert queue_position(
        c["state"], ticket_id=c["result"]["ticket_id"], now_utc=NOW
    )["position"] == 3


def test_duplicate_owner_queue_reservation_is_deduped_without_revision_change():
    holder = _holder()
    lease_id = holder["result"]["lease_id"]
    queue = new_queue_state("owner/repo")
    first = _enqueue(queue, "a", lease_id, "a.py")
    duplicate = _enqueue(first["state"], "a", lease_id, "a.py")
    assert duplicate["result"]["decision"] == "WAIT_TICKET_ALREADY_QUEUED"
    assert duplicate["result"]["ticket_id"] == first["result"]["ticket_id"]
    assert duplicate["state"]["revision"] == first["state"]["revision"]
    assert duplicate["state"]["state_hash"] == first["state"]["state_hash"]


def test_ticket_scope_carries_exact_queue_ticket_identity():
    holder = _holder()
    queue = new_queue_state("owner/repo")
    result = _enqueue(queue, "a", holder["result"]["lease_id"], "a.py")
    ticket = result["state"]["tickets"][0]
    assert ticket["scope"]["resource_identity"]["queue:ticket"] == (
        ticket["ticket_id"]
    )


def test_stale_queue_cas_fails_closed():
    holder = _holder()
    queue = new_queue_state("owner/repo")
    first = _enqueue(queue, "a", holder["result"]["lease_id"], "a.py")
    stale = _enqueue(
        first["state"],
        "b",
        holder["result"]["lease_id"],
        "b.py",
        expected_revision=0,
        expected_state_hash=queue["state_hash"],
    )
    assert stale["result"]["decision"] == "WAIT_QUEUE_STALE_CAS_CONTINUE"
    assert stale["result"]["allowed"] is False
    assert stale["state"]["state_hash"] == first["state"]["state_hash"]


def test_cancel_requires_ticket_owner_and_is_holder_local():
    holder = _holder()
    queue = new_queue_state("owner/repo")
    first = _enqueue(queue, "a", holder["result"]["lease_id"], "a.py")
    wrong = cancel_waiter(
        first["state"],
        owner_id="b",
        ticket_id=first["result"]["ticket_id"],
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )
    assert wrong["result"]["decision"] == "WAIT_TICKET_OWNER_MISMATCH_CONTINUE"
    assert wrong["state"]["state_hash"] == first["state"]["state_hash"]

    cancelled = cancel_waiter(
        first["state"],
        owner_id="a",
        ticket_id=first["result"]["ticket_id"],
        expected_revision=first["state"]["revision"],
        expected_state_hash=first["state"]["state_hash"],
    )
    assert cancelled["result"]["decision"] == "WAIT_TICKET_CANCELLED"
    assert cancelled["state"]["tickets"] == []


def test_atomic_handoff_moves_lease_to_fifo_head():
    holder = _holder()
    old = holder["state"]["holders"][0]
    queue = new_queue_state("owner/repo")
    a = _enqueue(queue, "a", old["lease_id"], "a.py")
    b = _enqueue(a["state"], "b", old["lease_id"], "b.py")
    result = atomic_release_and_handoff(
        holder["state"],
        b["state"],
        releasing_owner_id="holder",
        releasing_lease_id=old["lease_id"],
        queue_key=QUEUE_KEY,
        now_utc=NOW,
        expected_lease_revision=holder["state"]["revision"],
        expected_lease_state_hash=holder["state"]["state_hash"],
        expected_queue_revision=b["state"]["revision"],
        expected_queue_state_hash=b["state"]["state_hash"],
    )
    assert result["result"]["decision"] == "ATOMIC_LEASE_HANDOFF_COMMITTED"
    assert result["result"]["new_owner_id"] == "a"
    assert {h["owner_id"] for h in result["lease_state"]["holders"]} == {"a"}
    assert queue_position(
        result["queue_state"],
        ticket_id=b["result"]["ticket_id"],
        now_utc=NOW,
    )["position"] == 1


def test_atomic_handoff_lease_revision_span_is_two_logical_operations():
    holder = _holder()
    old = holder["state"]["holders"][0]
    queue = new_queue_state("owner/repo")
    a = _enqueue(queue, "a", old["lease_id"], "a.py")
    result = atomic_release_and_handoff(
        holder["state"],
        a["state"],
        releasing_owner_id="holder",
        releasing_lease_id=old["lease_id"],
        queue_key=QUEUE_KEY,
        now_utc=NOW,
        expected_lease_revision=holder["state"]["revision"],
        expected_lease_state_hash=holder["state"]["state_hash"],
        expected_queue_revision=a["state"]["revision"],
        expected_queue_state_hash=a["state"]["state_hash"],
    )
    assert result["result"]["logical_revision_span"] == 2
    assert result["lease_state"]["revision"] == holder["state"]["revision"] + 2


def test_handoff_receipt_records_exact_ticket_and_new_lease():
    holder = _holder()
    old = holder["state"]["holders"][0]
    queue = new_queue_state("owner/repo")
    a = _enqueue(queue, "a", old["lease_id"], "a.py")
    result = atomic_release_and_handoff(
        holder["state"],
        a["state"],
        releasing_owner_id="holder",
        releasing_lease_id=old["lease_id"],
        queue_key=QUEUE_KEY,
        now_utc=NOW,
        expected_lease_revision=holder["state"]["revision"],
        expected_lease_state_hash=holder["state"]["state_hash"],
        expected_queue_revision=a["state"]["revision"],
        expected_queue_state_hash=a["state"]["state_hash"],
    )
    receipt = result["queue_state"]["handoff_receipts"][0]
    assert receipt["ticket_id"] == a["result"]["ticket_id"]
    assert receipt["previous_lease_id"] == old["lease_id"]
    assert receipt["new_lease_id"] == result["result"]["new_lease_id"]
    assert receipt["lease_state_hash"] == result["lease_state"]["state_hash"]


def test_completed_ticket_reports_handed_off_position_zero():
    holder = _holder()
    old = holder["state"]["holders"][0]
    queue = new_queue_state("owner/repo")
    a = _enqueue(queue, "a", old["lease_id"], "a.py")
    result = atomic_release_and_handoff(
        holder["state"],
        a["state"],
        releasing_owner_id="holder",
        releasing_lease_id=old["lease_id"],
        queue_key=QUEUE_KEY,
        now_utc=NOW,
        expected_lease_revision=holder["state"]["revision"],
        expected_lease_state_hash=holder["state"]["state_hash"],
        expected_queue_revision=a["state"]["revision"],
        expected_queue_state_hash=a["state"]["state_hash"],
    )
    position = queue_position(
        result["queue_state"],
        ticket_id=a["result"]["ticket_id"],
        now_utc=NOW,
    )
    assert position["decision"] == "WAIT_TICKET_ALREADY_HANDED_OFF"
    assert position["position"] == 0


def test_delayed_queue_ack_is_reconciled_from_live_lease_ticket_identity():
    holder = _holder()
    old = holder["state"]["holders"][0]
    queue = new_queue_state("owner/repo")
    a = _enqueue(queue, "a", old["lease_id"], "a.py")
    result = atomic_release_and_handoff(
        holder["state"],
        a["state"],
        releasing_owner_id="holder",
        releasing_lease_id=old["lease_id"],
        queue_key=QUEUE_KEY,
        now_utc=NOW,
        expected_lease_revision=holder["state"]["revision"],
        expected_lease_state_hash=holder["state"]["state_hash"],
        expected_queue_revision=a["state"]["revision"],
        expected_queue_state_hash=a["state"]["state_hash"],
    )
    recovered = reconcile_queue_from_lease(
        a["state"],
        result["lease_state"],
        expected_queue_revision=a["state"]["revision"],
        expected_queue_state_hash=a["state"]["state_hash"],
        now_utc=NOW,
    )
    assert recovered["result"]["decision"] == "WAIT_QUEUE_HANDOFF_RECONCILED"
    assert recovered["result"]["ticket_id"] == a["result"]["ticket_id"]
    assert recovered["state"]["tickets"] == []


def test_reconcile_noop_when_no_live_lease_contains_wait_ticket():
    queue = new_queue_state("owner/repo")
    lease = new_lease_state("owner/repo")
    result = reconcile_queue_from_lease(
        queue,
        lease,
        expected_queue_revision=0,
        expected_queue_state_hash=queue["state_hash"],
        now_utc=NOW,
    )
    assert result["result"]["decision"] == "WAIT_QUEUE_RECONCILE_NOOP"
    assert result["state"]["state_hash"] == queue["state_hash"]


def test_head_blocked_rolls_back_release_and_prevents_leapfrog():
    lease = new_lease_state("owner/repo")
    primary = claim_scope(
        lease,
        owner_id="primary",
        now_utc=NOW,
        scope=build_scope(
            write_paths=["primary.py"],
            shared_resources=[QUEUE_KEY],
        ),
        expected_revision=0,
        expected_state_hash=lease["state_hash"],
    )
    dependency = claim_scope(
        primary["state"],
        owner_id="dependency",
        now_utc=NOW,
        scope=build_scope(
            write_paths=["dep.py"],
            dependency_tokens=["provider:shared"],
        ),
        expected_revision=primary["state"]["revision"],
        expected_state_hash=primary["state"]["state_hash"],
    )

    queue = new_queue_state("owner/repo")
    head = enqueue_waiter(
        queue,
        owner_id="head",
        queue_key=QUEUE_KEY,
        blocked_by_lease_id=primary["result"]["lease_id"],
        scope=build_scope(
            write_paths=["head.py"],
            dependency_tokens=["provider:shared"],
            shared_resources=[QUEUE_KEY],
        ),
        now_utc=NOW,
        expected_revision=0,
        expected_state_hash=queue["state_hash"],
    )
    second = _enqueue(
        head["state"],
        "second",
        primary["result"]["lease_id"],
        "second.py",
    )

    result = atomic_release_and_handoff(
        dependency["state"],
        second["state"],
        releasing_owner_id="primary",
        releasing_lease_id=primary["result"]["lease_id"],
        queue_key=QUEUE_KEY,
        now_utc=NOW,
        expected_lease_revision=dependency["state"]["revision"],
        expected_lease_state_hash=dependency["state"]["state_hash"],
        expected_queue_revision=second["state"]["revision"],
        expected_queue_state_hash=second["state"]["state_hash"],
    )
    assert result["result"]["decision"] == "ATOMIC_HANDOFF_HEAD_BLOCKED"
    assert result["result"]["original_holder_retained"] is True
    assert result["lease_state"]["state_hash"] == dependency["state"]["state_hash"]
    assert result["queue_state"]["state_hash"] == second["state"]["state_hash"]
    assert queue_position(
        result["queue_state"],
        ticket_id=head["result"]["ticket_id"],
        now_utc=NOW,
    )["position"] == 1
    assert queue_position(
        result["queue_state"],
        ticket_id=second["result"]["ticket_id"],
        now_utc=NOW,
    )["position"] == 2


def test_release_without_waiter_releases_normally():
    holder = _holder()
    old = holder["state"]["holders"][0]
    queue = new_queue_state("owner/repo")
    result = atomic_release_and_handoff(
        holder["state"],
        queue,
        releasing_owner_id="holder",
        releasing_lease_id=old["lease_id"],
        queue_key=QUEUE_KEY,
        now_utc=NOW,
        expected_lease_revision=holder["state"]["revision"],
        expected_lease_state_hash=holder["state"]["state_hash"],
        expected_queue_revision=0,
        expected_queue_state_hash=queue["state_hash"],
    )
    assert result["result"]["decision"] == "LEASE_RELEASED_NO_WAITER"
    assert result["lease_state"]["holders"] == []


def test_expired_head_is_skipped_as_not_live():
    holder = _holder()
    lease_id = holder["result"]["lease_id"]
    queue = new_queue_state("owner/repo")
    expired = _enqueue(
        queue,
        "expired",
        lease_id,
        "expired.py",
        ttl_seconds=60,
        now_utc="2026-10-02T01:00:00Z",
    )
    live = _enqueue(
        expired["state"],
        "live",
        lease_id,
        "live.py",
        now_utc="2026-10-02T01:02:00Z",
    )
    assert len(live["state"]["tickets"]) == 1
    assert live["state"]["tickets"][0]["owner_id"] == "live"
    assert queue_position(
        live["state"],
        ticket_id=live["result"]["ticket_id"],
        now_utc="2026-10-02T01:02:00Z",
    )["position"] == 1


def test_enqueue_requires_queue_key_in_shared_scope():
    queue = new_queue_state("owner/repo")
    with pytest.raises(
        AtomicWaitQueueFailure,
        match="queue_key must exist",
    ):
        enqueue_waiter(
            queue,
            owner_id="a",
            queue_key=QUEUE_KEY,
            blocked_by_lease_id="lease-x",
            scope=build_scope(
                write_paths=["a.py"],
                shared_resources=["deploy:pickvault"],
            ),
            now_utc=NOW,
            expected_revision=0,
            expected_state_hash=queue["state_hash"],
        )


def test_validate_queue_rejects_tampered_hash():
    queue = new_queue_state("owner/repo")
    queue["revision"] = 9
    with pytest.raises(AtomicWaitQueueFailure, match="state hash mismatch"):
        validate_queue_state(queue)


def test_engine_is_read_only_and_grants_no_mutation_authority():
    result = contract_self_test()
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False
    assert result["mutation_authority_granted"] is False
