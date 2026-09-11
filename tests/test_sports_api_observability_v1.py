from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api import observability_v1 as obs
from sports_api.api import health


def test_error_fingerprint_is_stable_and_route_specific():
    exc = ValueError("different messages must not change identity")
    first = obs.error_fingerprint(exc, path="/api/v1/example")
    second = obs.error_fingerprint(ValueError("another payload"), path="/api/v1/example")
    other_route = obs.error_fingerprint(ValueError("another payload"), path="/api/v1/other")

    assert first == second
    assert first.startswith("KYRE-")
    assert len(first) == 17
    assert other_route != first


def test_error_message_redacts_common_secret_shapes():
    message = "token=abc123 password:hello api_key=xyz authorization=BearerThing"
    cleaned = obs.sanitize_error_message(message)

    assert "abc123" not in cleaned
    assert "hello" not in cleaned
    assert "xyz" not in cleaned
    assert "BearerThing" not in cleaned
    assert cleaned.count("<redacted>") == 4


def test_request_id_reuses_only_safe_values():
    assert obs.request_id_from_header("abc-123_X") == "abc-123_X"
    generated = obs.request_id_from_header("bad request id with spaces")
    assert generated != "bad request id with spaces"
    assert len(generated) == 32


def test_runtime_metadata_surfaces_deployment_identity_without_secrets(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "kyre-sports-api")
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-test")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://example.test")
    monkeypatch.setenv("HOSTNAME", "instance-test")
    monkeypatch.setenv("API_KEY", "must-never-appear")

    payload = obs.runtime_metadata()
    flattened = repr(payload)

    assert payload["environment"] == "render"
    assert payload["deploy_branch"] == "main"
    assert payload["deploy_commit"] == "abc123"
    assert payload["branch_aligned"] is True
    assert "must-never-appear" not in flattened
    assert "API_KEY" not in flattened


def test_health_endpoints_expose_liveness_readiness_and_diagnostics(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "deadbeef")

    live = health.health_check()
    ready = health.readiness_check()
    details = health.health_details()

    assert live["status"] == "ok"
    assert live["deployment"]["commit"] == "deadbeef"
    assert ready["status"] == "ready"
    assert ready["deployment"]["aligned"] is True
    assert details["observability_version"] == "KYRE_OBSERVABILITY_V1"
    assert details["debug_contract"]["request_id_header"] == "X-Request-ID"
    assert details["debug_contract"]["error_fingerprint_field"] == "error_fingerprint"


def test_real_fastapi_middleware_stamps_ids_headers_and_crash_fingerprint(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "feedface1234")

    app = FastAPI()
    obs.install_observability(app)
    app.include_router(health.router)

    @app.get("/boom")
    def boom():
        raise ValueError("token=should-not-escape")

    with TestClient(app, raise_server_exceptions=False) as client:
        healthy = client.get("/health/details", headers={"X-Request-ID": "req-123"})
        assert healthy.status_code == 200
        assert healthy.headers["X-Request-ID"] == "req-123"
        assert healthy.headers["X-Kyre-Deploy-Commit"] == "feedface1234"
        assert healthy.headers["X-Kyre-Deploy-Branch"] == "main"
        assert float(healthy.headers["X-Kyre-Duration-Ms"]) >= 0.0

        failed = client.get("/boom", headers={"X-Request-ID": "req-crash"})
        payload = failed.json()
        assert failed.status_code == 500
        assert payload["request_id"] == "req-crash"
        assert payload["error_fingerprint"].startswith("KYRE-")
        assert "should-not-escape" not in repr(payload)
        assert failed.headers["X-Request-ID"] == "req-crash"
