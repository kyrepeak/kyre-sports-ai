from __future__ import annotations

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
