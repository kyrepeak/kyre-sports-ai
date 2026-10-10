import pytest

from devsystem.execution_heartbeat_deadman_recovery_v1 import (
    new_state as new_heartbeat_state,
    register_worker,
)
from devsystem.scope_aware_execution_lease_v1 import (
    build_scope,
    claim_scope,
    new_state as new_lease_state,
)
from devsystem.universal_live_status_board_recovery_v1 import (
    RecoveryResolutionFailure,
    bind_status_packet_to_recovered_owner,
    inspect_status_board_owner_liveness,
    issue_status_board_recovery,
)

PACKET = "a" * 64
WORKSTREAM = "universal-live-status-board-v1"
WRITE_PATH = "devsystem/universal_live_status_board_recovery_v1.py"
VALID_ACTIVE = {
    "completion_percent": 75,
    "status": "YELLOW",
    "live_active_chat": "THIS_CHAT",
    "frozen": False,
    "current_blocker": None,
    "next_legal_action": "continue authoritative execution",
}


def _lease(owner_id: str, *, now_utc: str, ttl_seconds: int):
    state = new_lease_state("kyrepeak/kyre-sports-ai")
    claimed = claim_scope(
        state,
        owner_id=owner_id,
        now_utc=now_utc,
        scope=build_scope(write_paths=[WRITE_PATH]),
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        ttl_seconds=ttl_seconds,
    )
    assert claimed["result"]["allowed"] is True
    return claimed["state"]


def _heartbeat(owner_id: str, scope_lease_id: str, *, now_utc: str, ttl_seconds: int):
    state = new_heartbeat_state("kyrepeak/kyre-sports-ai")
    registered = register_worker(
        state,
        workstream_id=WORKSTREAM,
        owner_id=owner_id,
        scope_lease_id=scope_lease_id,
        continuation_packet_hash=PACKET,
        authoritative_run_id=303,
        now_utc=now_utc,
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        heartbeat_ttl_seconds=ttl_seconds,
    )
    assert registered["result"]["allowed"] is True
    return registered["state"]


def test_live_owner_and_live_heartbeat_remain_authoritative():
    owner = "chatgpt:api2:universal-board-step3"
    lease = _lease(owner, now_utc="2026-10-10T04:00:00Z", ttl_seconds=900)
    scope_lease_id = lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(owner, scope_lease_id, now_utc="2026-10-10T04:00:00Z", ttl_seconds=900)

    decision = inspect_status_board_owner_liveness(
        lease,
        heartbeat,
        workstream_id=WORKSTREAM,
        continuation_packet_hash=PACKET,
        now_utc="2026-10-10T04:05:00Z",
        observed_run_state="in_progress",
    )

    assert decision["decision"] == "OWNER_HEARTBEAT_LIVE"
    assert decision["recovery_allowed"] is False
    assert decision["live_active_chat"] == "API_2"
    assert decision["authoritative_owner"] == owner


def test_stale_heartbeat_never_overrides_still_active_run():
    owner = "chatgpt:monster-v2:universal-board-step3"
    lease = _lease(owner, now_utc="2026-10-10T04:00:00Z", ttl_seconds=900)
    scope_lease_id = lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(owner, scope_lease_id, now_utc="2026-10-10T04:00:00Z", ttl_seconds=60)

    decision = inspect_status_board_owner_liveness(
        lease,
        heartbeat,
        workstream_id=WORKSTREAM,
        continuation_packet_hash=PACKET,
        now_utc="2026-10-10T04:01:01Z",
        observed_run_state="in_progress",
    )

    assert decision["decision"] == "OWNER_RUN_ACTIVE_HEARTBEAT_STALE"
    assert decision["recovery_allowed"] is False
    assert decision["next_legal_action"] == "WAIT_FOR_RUN_TERMINAL_EVENT"


def test_terminal_run_and_stale_heartbeat_cannot_recover_while_scope_lease_is_live():
    owner = "chatgpt:api2:universal-board-step3"
    lease = _lease(owner, now_utc="2026-10-10T04:00:00Z", ttl_seconds=900)
    scope_lease_id = lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(owner, scope_lease_id, now_utc="2026-10-10T04:00:00Z", ttl_seconds=60)

    decision = inspect_status_board_owner_liveness(
        lease,
        heartbeat,
        workstream_id=WORKSTREAM,
        continuation_packet_hash=PACKET,
        now_utc="2026-10-10T04:01:01Z",
        observed_run_state="failure",
    )

    assert decision["decision"] == "STALE_HEARTBEAT_LIVE_LEASE_BLOCKS_RECOVERY"
    assert decision["recovery_allowed"] is False
    assert decision["next_legal_action"] == "WAIT_FOR_SCOPE_LEASE_EXPIRY_OR_OWNER_RENEWAL"


def test_stale_owner_becomes_recoverable_only_after_heartbeat_and_lease_expire_and_run_is_terminal():
    owner = "chatgpt:api2:universal-board-step3"
    lease = _lease(owner, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)
    scope_lease_id = lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(owner, scope_lease_id, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)

    decision = inspect_status_board_owner_liveness(
        lease,
        heartbeat,
        workstream_id=WORKSTREAM,
        continuation_packet_hash=PACKET,
        now_utc="2026-10-10T04:00:00Z",
        observed_run_state="failure",
    )

    assert decision["decision"] == "STALE_OWNER_RECOVERY_ELIGIBLE"
    assert decision["recovery_allowed"] is True
    assert decision["requires_step_2a"] is True
    assert decision["requires_new_scope_lease"] is True
    assert decision["grants_mutation_authority"] is False


def test_unknown_run_state_fails_closed_after_owner_stales():
    owner = "chatgpt:api2:universal-board-step3"
    lease = _lease(owner, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)
    scope_lease_id = lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(owner, scope_lease_id, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)

    decision = inspect_status_board_owner_liveness(
        lease,
        heartbeat,
        workstream_id=WORKSTREAM,
        continuation_packet_hash=PACKET,
        now_utc="2026-10-10T04:00:00Z",
        observed_run_state="mystery",
    )

    assert decision["decision"] == "RUN_STATE_UNKNOWN_FAIL_CLOSED"
    assert decision["recovery_allowed"] is False


def test_continuation_drift_fails_closed():
    owner = "chatgpt:api2:universal-board-step3"
    lease = _lease(owner, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)
    scope_lease_id = lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(owner, scope_lease_id, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)

    decision = inspect_status_board_owner_liveness(
        lease,
        heartbeat,
        workstream_id=WORKSTREAM,
        continuation_packet_hash="b" * 64,
        now_utc="2026-10-10T04:00:00Z",
        observed_run_state="failure",
    )

    assert decision["decision"] == "CONTINUATION_DRIFT_BLOCKED"
    assert decision["recovery_allowed"] is False


def test_live_lease_identity_drift_against_heartbeat_fails_closed():
    lease = _lease("chatgpt:api2:lease-owner", now_utc="2026-10-10T04:00:00Z", ttl_seconds=900)
    scope_lease_id = lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(
        "chatgpt:monster-v2:heartbeat-owner",
        scope_lease_id,
        now_utc="2026-10-10T04:00:00Z",
        ttl_seconds=900,
    )

    with pytest.raises(RecoveryResolutionFailure, match="heartbeat owner does not match authoritative lease owner"):
        inspect_status_board_owner_liveness(
            lease,
            heartbeat,
            workstream_id=WORKSTREAM,
            continuation_packet_hash=PACKET,
            now_utc="2026-10-10T04:05:00Z",
            observed_run_state="in_progress",
        )


def test_recovery_receipt_preserves_step2a_and_never_grants_mutation_authority():
    old_owner = "chatgpt:api2:universal-board-step3"
    lease = _lease(old_owner, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)
    old_scope_lease_id = lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(old_owner, old_scope_lease_id, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)

    recovered = issue_status_board_recovery(
        lease,
        heartbeat,
        workstream_id=WORKSTREAM,
        continuation_packet_hash=PACKET,
        now_utc="2026-10-10T04:00:00Z",
        observed_run_state="failure",
        new_owner_id="chatgpt:monster-v2:universal-board-step3-recovery",
        new_scope_lease_id="SCOPE-LEASE-recovered-step3",
        expected_heartbeat_revision=heartbeat["revision"],
        expected_heartbeat_state_hash=heartbeat["state_hash"],
    )

    assert recovered["result"]["allowed"] is True
    assert recovered["result"]["requires_step_2a"] is True
    assert recovered["result"]["requires_scope_lease"] is True
    assert recovered["result"]["grants_mutation_authority"] is False


def test_recovered_owner_binds_only_when_new_authoritative_lease_matches_heartbeat_identity():
    old_owner = "chatgpt:api2:universal-board-step3"
    old_lease = _lease(old_owner, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)
    old_scope_lease_id = old_lease["holders"][0]["lease_id"]
    heartbeat = _heartbeat(old_owner, old_scope_lease_id, now_utc="2026-10-10T03:00:00Z", ttl_seconds=60)

    new_owner = "chatgpt:monster-v2:universal-board-step3-recovery"
    claimed = claim_scope(
        old_lease,
        owner_id=new_owner,
        now_utc="2026-10-10T04:00:00Z",
        scope=build_scope(write_paths=[WRITE_PATH]),
        expected_revision=old_lease["revision"],
        expected_state_hash=old_lease["state_hash"],
        ttl_seconds=900,
    )
    assert claimed["result"]["allowed"] is True
    recovered_lease = claimed["state"]
    new_scope_lease_id = next(
        holder["lease_id"] for holder in recovered_lease["holders"] if holder["owner_id"] == new_owner
    )

    takeover = issue_status_board_recovery(
        old_lease,
        heartbeat,
        workstream_id=WORKSTREAM,
        continuation_packet_hash=PACKET,
        now_utc="2026-10-10T04:00:00Z",
        observed_run_state="failure",
        new_owner_id=new_owner,
        new_scope_lease_id=new_scope_lease_id,
        expected_heartbeat_revision=heartbeat["revision"],
        expected_heartbeat_state_hash=heartbeat["state_hash"],
    )
    assert takeover["result"]["allowed"] is True

    bound = bind_status_packet_to_recovered_owner(
        VALID_ACTIVE,
        recovered_lease,
        takeover["state"],
        workstream_id=WORKSTREAM,
        continuation_packet_hash=PACKET,
        now_utc="2026-10-10T04:00:01Z",
    )

    assert bound["live_active_chat"] == "MONSTER"
    assert bound["authoritative_owner"] == new_owner
    assert bound["scope_lease_id"] == new_scope_lease_id


def test_recovered_binding_fails_if_lease_and_heartbeat_do_not_match():
    owner = "chatgpt:api2:universal-board-step3"
    lease = _lease(owner, now_utc="2026-10-10T04:00:00Z", ttl_seconds=900)
    heartbeat = _heartbeat(
        owner,
        "SCOPE-LEASE-wrong",
        now_utc="2026-10-10T04:00:00Z",
        ttl_seconds=900,
    )

    with pytest.raises(RecoveryResolutionFailure, match="heartbeat lease does not match authoritative scope lease"):
        bind_status_packet_to_recovered_owner(
            VALID_ACTIVE,
            lease,
            heartbeat,
            workstream_id=WORKSTREAM,
            continuation_packet_hash=PACKET,
            now_utc="2026-10-10T04:00:01Z",
        )


def test_step3_is_read_only_with_respect_to_product_runtime_and_does_not_create_parallel_authority():
    import devsystem.universal_live_status_board_recovery_v1 as module

    assert module.NETWORK_CALLS is False
    assert module.AUTO_MUTATE is False
    assert module.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert module.MUTATION_AUTHORITY_GRANTED is False
    assert module.GITHUB_ACTIONS_FALLBACK == 0
    assert module.CREATES_PARALLEL_OWNERSHIP_REGISTRY is False
