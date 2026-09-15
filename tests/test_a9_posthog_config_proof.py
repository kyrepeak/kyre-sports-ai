from __future__ import annotations

import sys
from types import SimpleNamespace

import sports_api.posthog_error_radar_v1 as radar


def test_streamlit_probe_ping_reports_safe_posthog_configuration_bit(monkeypatch) -> None:
    requested_urls: list[str] = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_urlopen(request, timeout: float):
        requested_urls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr(radar, "urlopen", fake_urlopen)

    assert radar._streamlit_probe_ping(
        "monster-a9-configured",
        {"POSTHOG_PROJECT_API_KEY": "test-only"},
    ) is True
    assert radar._streamlit_probe_ping("monster-a9-unconfigured", {}) is True

    assert "posthog_configured=1" in requested_urls[0]
    assert "posthog_configured=0" in requested_urls[1]
    assert "test-only" not in "".join(requested_urls)


def test_streamlit_probe_ping_uses_streamlit_secret_without_leaking_it(monkeypatch) -> None:
    requested_urls: list[str] = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_urlopen(request, timeout: float):
        requested_urls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr(radar, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        radar,
        "_streamlit_secret_mapping",
        lambda: {"POSTHOG_PROJECT_API_KEY": "streamlit-secret-only"},
    )

    assert radar._streamlit_probe_ping("monster-a9-streamlit-secret", {}) is True
    assert "posthog_configured=1" in requested_urls[0]
    assert "streamlit-secret-only" not in requested_urls[0]


def test_streamlit_activation_probe_records_non_secret_session_evidence(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setattr(radar, "_STREAMLIT_PROBE_RAN", False, raising=False)
    monkeypatch.setattr(
        radar,
        "_streamlit_secret_mapping",
        lambda: {"POSTHOG_PROJECT_API_KEY": "never-store-this"},
        raising=False,
    )

    result = radar.run_streamlit_activation_probe(
        argv=["streamlit", "run", "app.py"],
        environ={},
        ping_fn=lambda marker: True,
        capture_fn=lambda *args, **kwargs: True,
        flush_fn=lambda: True,
        marker_factory=lambda: "monster-a9-session-proof",
    )

    evidence = fake_streamlit.session_state["monster_a9_streamlit_probe_v1"]
    assert evidence == {
        "status": "flushed",
        "eligible": True,
        "runtime_pinged": True,
        "accepted": True,
        "flushed": True,
        "marker": "monster-a9-session-proof",
        "fingerprint": "MONSTER-A8-STREAMLIT-PROBE-V1",
        "posthog_configured": True,
    }
    assert result["status"] == "flushed"
    assert "never-store-this" not in repr(evidence)
