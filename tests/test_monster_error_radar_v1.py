from __future__ import annotations

from pathlib import Path

import sports_api.posthog_error_radar_v1 as radar

ROOT = Path(__file__).resolve().parents[1]


def _reset_client_state() -> None:
    radar._CLIENT = None
    radar._CLIENT_INITIALIZED = False


def test_radar_is_optional_when_posthog_is_not_configured(monkeypatch):
    monkeypatch.delenv("POSTHOG_PROJECT_API_KEY", raising=False)
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    _reset_client_state()

    assert radar.radar_status()["configured"] is False
    assert (
        radar.capture_runtime_exception(
            RuntimeError("expected test failure"),
            error_fingerprint="KYRE-TEST",
            surface="test",
        )
        is False
    )


def test_radar_preserves_kyre_fingerprint_and_deploy_context(monkeypatch):
    class FakePostHog:
        def __init__(self):
            self.calls = []

        def capture_exception(self, exc, **kwargs):
            self.calls.append((exc, kwargs))

    fake = FakePostHog()
    radar._CLIENT = fake
    radar._CLIENT_INITIALIZED = True
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    monkeypatch.setenv("RENDER_GIT_BRANCH", "main")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "kyre-sports-api")

    exc = ValueError("boom")
    accepted = radar.capture_runtime_exception(
        exc,
        error_fingerprint="KYRE-ABCDEF123456",
        surface="sports_api",
        request_id="req-123",
        path="/test",
        method="GET",
        properties={"duration_ms": 12.5},
    )

    assert accepted is True
    assert len(fake.calls) == 1
    captured_exc, kwargs = fake.calls[0]
    assert captured_exc is exc
    props = kwargs["properties"]
    assert props["error_fingerprint"] == "KYRE-ABCDEF123456"
    assert props["$exception_fingerprint"] == "KYRE-ABCDEF123456"
    assert props["monster_error_radar_version"] == radar.ERROR_RADAR_VERSION
    assert props["surface"] == "sports_api"
    assert props["request_id"] == "req-123"
    assert props["deploy_commit"] == "abc123"
    assert props["deploy_branch"] == "main"
    assert props["duration_ms"] == 12.5


def test_radar_fails_open_when_telemetry_capture_fails():
    class BrokenPostHog:
        def capture_exception(self, exc, **kwargs):
            raise RuntimeError("telemetry unavailable")

    radar._CLIENT = BrokenPostHog()
    radar._CLIENT_INITIALIZED = True

    assert (
        radar.capture_runtime_exception(
            ValueError("application failure"),
            error_fingerprint="KYRE-FAILOPEN",
            surface="streamlit",
        )
        is False
    )


def test_error_radar_is_wired_without_replacing_existing_contracts():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    observability_source = (ROOT / "sports_api" / "observability_v1.py").read_text(encoding="utf-8")
    radar_source = (ROOT / "sports_api" / "posthog_error_radar_v1.py").read_text(encoding="utf-8")

    assert "capture_runtime_exception(" in app_source
    assert "capture_runtime_exception(" in observability_source
    assert "$exception_fingerprint" in radar_source
    assert "capture_exception_code_variables=False" in radar_source
    assert "STREAMLIT_MAIN_V77_CFB_OU_COLD_START_FAST_ROUTE_2026-09-11" in app_source
    assert 'OBSERVABILITY_VERSION = "KYRE_OBSERVABILITY_V1"' in observability_source
