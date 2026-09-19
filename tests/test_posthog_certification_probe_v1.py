"""Contract tests for the temporary Monster A6 PostHog certification probe."""

import importlib

import pytest
from fastapi import HTTPException


MODULE_PATH = "sports_api.api.posthog_certification_probe_v1"
EVENT_NAME = "MONSTER_A6_POSTHOG_CERTIFICATION_PROBE"
FINGERPRINT = "KYRE-MONSTER-A6-POSTHOG-CERT"


def _module():
    return importlib.import_module(MODULE_PATH)


def test_posthog_cert_probe_refuses_when_disabled(monkeypatch):
    module = _module()
    monkeypatch.delenv("MONSTER_POSTHOG_CERT_PROBE_ENABLED", raising=False)

    calls = []

    def fake_capture(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr(module, "capture_runtime_exception", fake_capture)

    with pytest.raises(HTTPException) as exc_info:
        module.run_posthog_certification_probe()

    assert exc_info.value.status_code == 404
    assert calls == []


def test_posthog_cert_probe_emits_exactly_one_controlled_exception_when_enabled(monkeypatch):
    module = _module()
    monkeypatch.setenv("MONSTER_POSTHOG_CERT_PROBE_ENABLED", "1")

    calls = []

    def fake_capture(exc, **kwargs):
        calls.append((exc, kwargs))
        return True

    monkeypatch.setattr(module, "capture_runtime_exception", fake_capture)

    result = module.run_posthog_certification_probe()

    assert result["event"] == EVENT_NAME
    assert result["accepted"] is True
    assert result["marker"].startswith("monster-a6-")
    assert result["surface"] == "render_api_certification"
    assert len(calls) == 1

    exc, kwargs = calls[0]
    assert isinstance(exc, RuntimeError)
    assert result["marker"] in str(exc)
    assert kwargs["error_fingerprint"] == FINGERPRINT
    assert kwargs["surface"] == "render_api_certification"
    assert kwargs["request_id"] == result["marker"]
    assert kwargs["path"] == "/__monster/certification/posthog-a6"
    assert kwargs["method"] == "POST"
    assert kwargs["properties"]["certification_probe"] is True
    assert kwargs["properties"]["certification_marker"] == result["marker"]


def test_posthog_cert_probe_route_is_hidden_post_only():
    module = _module()
    route = next(
        route
        for route in module.router.routes
        if route.path == "/__monster/certification/posthog-a6"
    )

    assert route.methods == {"POST"}
    assert route.include_in_schema is False
