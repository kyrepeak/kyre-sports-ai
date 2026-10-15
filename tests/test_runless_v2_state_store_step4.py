from runless_v2.config import Settings
from runless_v2.models import ProofState
from runless_v2.state_store import DurableStateStore, RunlessV2StateError


SHA = "a" * 40
MAIN = "b" * 40
DIGEST = "c" * 64
FREEZE = "RUNLESS_DYNAMIC_FINALIZATION_AUTHORITY_V1_STEP4_FROZEN"
MANIFEST = "d" * 64


def settings():
    return Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="secret",
        github_app_id="5204253",
        github_app_installation_id="1",
        github_app_private_key="key",
        proof_auth_token="token",
        authority_enabled=True,
    )


def row(state):
    return {
        "proof_id": "proof-1",
        "task_id": "task-1",
        "workstream": "ws-1",
        "candidate_sha": SHA,
        "expected_main_sha": "e" * 40,
        "scope_lease_id": "scope-1",
        "authorization_id": "auth-1",
        "request_fingerprint": "fp-1",
        "proof_fingerprint": "pf-1",
        "state": state,
        "failure_class": "NONE",
        "detail": "",
        "fencing_generation": 1,
        "receipt_digest": DIGEST,
        "gate_check_run_id": 77,
        "merged_main_sha": MAIN if state != "MERGE_AUTHORIZED" else None,
        "freeze_token": FREEZE if state in {"FREEZE", "READ_BACK", "GREEN_FROZEN"} else None,
        "manifest_state_hash": MANIFEST if state in {"READ_BACK", "GREEN_FROZEN"} else None,
        "terminal_at": "2026-10-15T18:00:00+00:00" if state == "GREEN_FROZEN" else None,
    }


def call(store):
    return store.closeout_green_frozen(
        "proof-1",
        candidate_sha=SHA,
        merged_main_sha=MAIN,
        freeze_token=FREEZE,
        proof_digest=DIGEST,
        manifest_state_hash=MANIFEST,
    )


def test_closeout_resumes_one_durable_checkpoint_at_a_time_until_terminal(monkeypatch):
    store = DurableStateStore(settings())
    states = iter(["MERGED", "POST_MERGE_VERIFY", "FREEZE", "READ_BACK", "GREEN_FROZEN"])
    calls = []

    def rpc(name, payload):
        calls.append((name, payload))
        return row(next(states))

    monkeypatch.setattr(store, "_rpc", rpc)
    result = call(store)

    assert result.state is ProofState.GREEN_FROZEN
    assert len(calls) == 5
    assert all(name == "resume_closeout_green_frozen" for name, _ in calls)
    assert all(payload["p_candidate_sha"] == SHA for _, payload in calls)
    assert all(payload["p_merged_main_sha"] == MAIN for _, payload in calls)
    assert all(payload["p_freeze_token"] == FREEZE for _, payload in calls)
    assert all(payload["p_proof_digest"] == DIGEST for _, payload in calls)
    assert all(payload["p_manifest_state_hash"] == MANIFEST for _, payload in calls)


def test_closeout_terminal_latch_returns_existing_green_frozen_without_replaying(monkeypatch):
    store = DurableStateStore(settings())
    calls = []

    def rpc(name, payload):
        calls.append((name, payload))
        return row("GREEN_FROZEN")

    monkeypatch.setattr(store, "_rpc", rpc)
    result = call(store)

    assert result.state is ProofState.GREEN_FROZEN
    assert len(calls) == 1


def test_closeout_fails_closed_on_non_resumable_state(monkeypatch):
    store = DurableStateStore(settings())
    monkeypatch.setattr(store, "_rpc", lambda name, payload: row("FAILED"))

    try:
        call(store)
    except RunlessV2StateError as exc:
        assert str(exc) == "RUNLESS_V2_CLOSEOUT_NON_RESUMABLE_STATE"
    else:
        raise AssertionError("expected closeout to fail closed")
