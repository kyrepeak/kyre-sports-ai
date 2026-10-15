import pytest

from runless_v2.transport_client import TransportError, project_transport_state


@pytest.mark.parametrize(
    ("native", "projected"),
    [
        ("IDENTIFY", "REQUESTED"),
        ("2A_LOCK", "QUEUED"),
        ("FINGERPRINT", "QUEUED"),
        ("REUSE_OR_PROVE", "RUNNING"),
        ("PUBLIC_CHECK_IF_REQUIRED", "RUNNING"),
        ("RECEIPT", "RUNNING"),
        ("RUNLESS_FINAL_GATE", "RUNNING"),
        ("MERGE_AUTHORIZED", "SUCCEEDED"),
        ("MERGED", "SUCCEEDED"),
        ("POST_MERGE_VERIFY", "SUCCEEDED"),
        ("FREEZE", "SUCCEEDED"),
        ("READ_BACK", "SUCCEEDED"),
        ("GREEN_FROZEN", "SUCCEEDED"),
        ("FAILED", "FAILED"),
    ],
)
def test_transport_state_projection(native, projected):
    assert project_transport_state(native) == projected


def test_transport_state_projection_rejects_unknown_state():
    with pytest.raises(TransportError, match="RUNLESS_TRANSPORT_UNKNOWN_STATE"):
        project_transport_state("WHATEVER")


import json
import httpx

from runless_v2.transport_client import TransportClient, normalize_transport_response


def _client_with_transport(handler):
    transport = httpx.MockTransport(handler)
    client = TransportClient(base_url="https://runless.example/", bearer_token="super-secret")
    client._client = httpx.Client(transport=transport, timeout=30.0)
    return client


def test_request_proof_posts_exact_payload_once_and_normalizes():
    seen = []
    payload = {
        "task_id": "task",
        "workstream": "ws",
        "candidate_sha": "a" * 40,
        "lease_id": "lease",
        "authorization_id": "auth",
        "expected_main_sha": "b" * 40,
    }

    def handler(request):
        seen.append(request)
        assert request.method == "POST"
        assert request.url == httpx.URL("https://runless.example/prove")
        assert request.headers["Authorization"] == "Bearer super-secret"
        assert json.loads(request.content) == payload
        return httpx.Response(200, json={
            "proof_id": "proof-1",
            "status": "MERGE_AUTHORIZED",
            "candidate_sha": "a" * 40,
            "receipt_digest": "sha256:" + "c" * 64,
        })

    result = _client_with_transport(handler).request_proof(payload)
    assert len(seen) == 1
    assert result["proof_id"] == "proof-1"
    assert result["state"] == "MERGE_AUTHORIZED"
    assert result["transport_state"] == "SUCCEEDED"
    assert result["execution_identity"] == "proof-1"
    assert result["candidate_sha"] == "a" * 40
    assert result["receipt_digest"] == "sha256:" + "c" * 64


def test_http_error_is_safe_and_redacted():
    def handler(request):
        return httpx.Response(409, json={"detail": "RUNLESS_V2_WORKSTREAM_BUSY super-secret https://runless.example"})

    client = _client_with_transport(handler)
    with pytest.raises(TransportError) as exc_info:
        client.request_proof({"x": 1})
    text = str(exc_info.value)
    assert "409" in text
    assert "RUNLESS_V2_WORKSTREAM_BUSY" in text
    assert "super-secret" not in text
    assert "https://runless.example" not in text


def test_malformed_success_body_fails_closed():
    def handler(request):
        return httpx.Response(200, content=b"not-json", headers={"content-type": "text/plain"})

    with pytest.raises(TransportError, match="RUNLESS_TRANSPORT_BAD_JSON"):
        _client_with_transport(handler).request_proof({"x": 1})


def test_normalize_status_projection_and_optional_fields():
    result = normalize_transport_response({
        "proof_id": "proof-2",
        "state": "RUNLESS_FINAL_GATE",
        "candidate_sha": "d" * 40,
        "fencing_generation": 7,
        "gate_check_run_id": 123,
    })
    assert result == {
        "proof_id": "proof-2",
        "candidate_sha": "d" * 40,
        "state": "RUNLESS_FINAL_GATE",
        "transport_state": "RUNNING",
        "fencing_generation": 7,
        "receipt_digest": None,
        "gate_check_run_id": 123,
        "execution_identity": "proof-2",
    }


def test_get_status_and_receipt_use_exact_paths():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/status/proof-3"):
            return httpx.Response(200, json={
                "proof_id": "proof-3",
                "state": "FAILED",
                "candidate_sha": "e" * 40,
                "fencing_generation": 2,
            })
        return httpx.Response(200, json={
            "proof_id": "proof-3",
            "receipt_digest": "sha256:" + "f" * 64,
            "candidate_sha": "e" * 40,
            "workstream": "ws",
            "receipt_json": {"digest": "sha256:" + "f" * 64},
        })

    client = _client_with_transport(handler)
    status = client.get_status("proof-3")
    receipt = client.get_receipt("proof-3")
    assert paths == ["/status/proof-3", "/receipts/proof-3"]
    assert status["transport_state"] == "FAILED"
    assert receipt["proof_id"] == "proof-3"
