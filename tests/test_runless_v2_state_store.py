import json

import httpx
import pytest

from runless_v2.config import Settings
from runless_v2.models import FailureClass, LeaseClaim, ProofRequest, ProofState
from runless_v2.state_store import (
    AuthorityConflict,
    DurableStateStore,
    IllegalTransition,
    StaleFence,
    WorkstreamBusy,
)

SHA = "a" * 40
MAIN = "b" * 40


def request() -> ProofRequest:
    return ProofRequest(
        task_id="task-1",
        workstream="ws-1",
        candidate_sha=SHA,
        lease_id="scope-1",
        authorization_id="auth-1",
        expected_main_sha=MAIN,
    )


def settings(**overrides) -> Settings:
    values = dict(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-secret",
        github_app_id="5204253",
        github_app_installation_id="99",
        github_app_private_key="private-key",
        proof_auth_token="proof-secret",
        repository="kyrepeak/kyre-sports-ai",
        receipt_ref="runless-proof-receipts",
        receipt_path="devsystem/runless_proof_receipts",
        authority_enabled=False,
    )
    values.update(overrides)
    return Settings(**values)


def store(handler) -> DurableStateStore:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return DurableStateStore(settings(), client=client)


def json_response(request, status, payload):
    return httpx.Response(status, json=payload, request=request)


def test_settings_fail_closed_when_required_secret_missing():
    env = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-secret",
        "GITHUB_APP_ID": "5204253",
        "GITHUB_APP_INSTALLATION_ID": "99",
        "GITHUB_APP_PRIVATE_KEY": "private-key",
        "RUNLESS_PROOF_AUTH_TOKEN": "",
    }
    with pytest.raises(RuntimeError, match="RUNLESS_V2_CONFIG_REQUIRED"):
        Settings.from_env(env)


def test_authority_defaults_disabled():
    env = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-secret",
        "GITHUB_APP_ID": "5204253",
        "GITHUB_APP_INSTALLATION_ID": "99",
        "GITHUB_APP_PRIVATE_KEY": "private-key",
        "RUNLESS_PROOF_AUTH_TOKEN": "proof-secret",
    }
    assert Settings.from_env(env).authority_enabled is False


def test_claim_calls_atomic_rpc_and_returns_idempotent_lease():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = json.loads(req.content)
        return json_response(req, 200, [{
            "proof_id": "proof-1",
            "lease_token": "11111111-1111-1111-1111-111111111111",
            "fencing_generation": 7,
            "expires_at": "2026-10-13T20:00:00+00:00",
            "state": "IDENTIFY",
            "reused": True,
        }])

    claim = store(handler).claim(request(), "fp-1", 900, proof_id="proof-1")
    assert isinstance(claim, LeaseClaim)
    assert claim.reused is True
    assert claim.fencing_generation == 7
    assert seen["url"].endswith("/rest/v1/rpc/claim_workstream")
    assert seen["auth"] == "Bearer service-secret"
    assert seen["body"] == {
        "p_workstream": "ws-1",
        "p_proof_id": "proof-1",
        "p_task_id": "task-1",
        "p_candidate_sha": SHA,
        "p_expected_main_sha": MAIN,
        "p_scope_lease_id": "scope-1",
        "p_authorization_id": "auth-1",
        "p_request_fingerprint": "fp-1",
        "p_ttl_seconds": 900,
    }


@pytest.mark.parametrize(
    "message,error_type",
    [
        ("RUNLESS_V2_WORKSTREAM_BUSY", WorkstreamBusy),
        ("RUNLESS_V2_AUTHORITY_CONFLICT", AuthorityConflict),
        ("RUNLESS_V2_STALE_FENCE", StaleFence),
        ("RUNLESS_V2_ILLEGAL_TRANSITION", IllegalTransition),
    ],
)
def test_rpc_conflicts_map_to_specific_exceptions(message, error_type):
    def handler(req):
        return json_response(req, 400, {"message": message})

    with pytest.raises(error_type):
        store(handler).claim(request(), "fp-1", 900, proof_id="proof-1")


def test_renew_uses_token_generation_and_maps_stale_fence():
    claim = LeaseClaim(
        proof_id="proof-1",
        workstream="ws-1",
        lease_token="11111111-1111-1111-1111-111111111111",
        fencing_generation=7,
        expires_at="2026-10-13T20:00:00+00:00",
        state=ProofState.IDENTIFY,
        reused=False,
    )
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return json_response(req, 409, {"message": "RUNLESS_V2_STALE_FENCE"})

    with pytest.raises(StaleFence):
        store(handler).renew(claim, 600)
    assert seen["body"]["p_fencing_generation"] == 7
    assert seen["body"]["p_lease_token"] == claim.lease_token


def test_advance_posts_expected_and_target_state():
    claim = LeaseClaim(
        proof_id="proof-1", workstream="ws-1",
        lease_token="11111111-1111-1111-1111-111111111111",
        fencing_generation=7, expires_at="2026-10-13T20:00:00+00:00",
        state=ProofState.IDENTIFY, reused=False,
    )
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return json_response(req, 200, {
            "proof_id": "proof-1", "task_id": "task-1", "workstream": "ws-1",
            "candidate_sha": SHA, "expected_main_sha": MAIN, "scope_lease_id": "scope-1",
            "authorization_id": "auth-1", "request_fingerprint": "fp-1",
            "state": "2A_LOCK", "failure_class": "NONE", "detail": "",
            "fencing_generation": 7,
        })

    status = store(handler).advance("proof-1", ProofState.IDENTIFY, ProofState.LOCK_2A, claim)
    assert status.state is ProofState.LOCK_2A
    assert seen["body"]["p_expected_state"] == "IDENTIFY"
    assert seen["body"]["p_target_state"] == "2A_LOCK"


def test_release_infra_does_not_record_failed_fingerprint():
    claim = LeaseClaim(
        proof_id="proof-1", workstream="ws-1",
        lease_token="11111111-1111-1111-1111-111111111111",
        fencing_generation=7, expires_at="2026-10-13T20:00:00+00:00",
        state=ProofState.REUSE_OR_PROVE, reused=False,
    )
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        return json_response(req, 200, {
            "proof_id": "proof-1", "task_id": "task-1", "workstream": "ws-1",
            "candidate_sha": SHA, "expected_main_sha": MAIN, "scope_lease_id": "scope-1",
            "authorization_id": "auth-1", "request_fingerprint": "fp-1",
            "state": "FAILED", "failure_class": "INFRA", "detail": "sandbox unavailable",
            "fencing_generation": 7,
        })

    status = store(handler).release_infra(claim, detail="sandbox unavailable")
    assert status.failure_class is FailureClass.INFRA
    assert seen["body"]["p_record_fingerprint"] is False


def test_status_and_receipt_mirror_are_durable_reads():
    calls = []

    def handler(req):
        calls.append(str(req.url))
        if "proof_runs" in req.url.path:
            return json_response(req, 200, [{
                "proof_id": "proof-1", "task_id": "task-1", "workstream": "ws-1",
                "candidate_sha": SHA, "expected_main_sha": MAIN, "scope_lease_id": "scope-1",
                "authorization_id": "auth-1", "request_fingerprint": "fp-1",
                "state": "MERGE_AUTHORIZED", "failure_class": "NONE", "detail": "",
                "fencing_generation": 7, "receipt_digest": "abc",
            }])
        return json_response(req, 200, [{"proof_id": "proof-1", "receipt_digest": "abc"}])

    s = store(handler)
    assert s.status("proof-1").state is ProofState.MERGE_AUTHORIZED
    assert s.receipt_mirror("proof-1")["receipt_digest"] == "abc"
    assert any("/rest/v1/proof_runs" in url for url in calls)
    assert any("/rest/v1/receipt_mirrors" in url for url in calls)


def test_new_supabase_secret_uses_apikey_without_bearer():
    s = DurableStateStore(settings(supabase_service_role_key="sb_secret_test"))
    assert s._headers["apikey"] == "sb_secret_test"
    assert "Authorization" not in s._headers


def test_health_rejects_supabase_auth_error():
    def handler(req):
        return json_response(req, 401, {"message": "Invalid API key"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    s = DurableStateStore(
        settings(supabase_service_role_key="sb_secret_test"), client=client
    )
    assert s.health() is False


def test_health_accepts_successful_supabase_read():
    def handler(req):
        return json_response(req, 200, [])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    s = DurableStateStore(
        settings(supabase_service_role_key="sb_secret_test"), client=client
    )
    assert s.health() is True
