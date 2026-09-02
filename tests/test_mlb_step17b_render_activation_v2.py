from __future__ import annotations

import pytest

from sports_api.tools import mlb_step17b_render_activation as base
from sports_api.tools import mlb_step17b_render_activation_v2 as v2


def _deployment_payload() -> dict:
    return {
        "data_type": "wnba_deployment_and_smoke_readiness",
        "deployment_ready": False,
        "configuration_fingerprint_sha256": "a" * 64,
        "semantics": {
            "deployment_gate_does_not_call_sportsbook": True,
            "deployment_gate_does_not_run_monte_carlo": True,
            "live_smoke_is_read_only": True,
        },
    }


def test_network_free_wnba_gate_uses_only_internal_endpoints(monkeypatch) -> None:
    called: list[str] = []

    def fake_get(path: str, **kwargs):
        called.append(path)
        if path == "/health":
            return {"status": "ok"}
        if path == "/api/v1/wnba/runtime/deployment":
            return _deployment_payload()
        raise AssertionError(path)

    monkeypatch.setattr(base, "_get_json", fake_get)
    result = v2.verify_wnba_network_free()
    assert called == ["/health", "/api/v1/wnba/runtime/deployment"]
    assert result["health"] == "ok"
    assert result["network_free_contract_checked"] is True
    assert result["deployment_ready"] is False


def test_network_free_gate_rejects_sportsbook_boundary_drift(monkeypatch) -> None:
    payload = _deployment_payload()
    payload["semantics"]["deployment_gate_does_not_call_sportsbook"] = False

    def fake_get(path: str, **kwargs):
        return {"status": "ok"} if path == "/health" else payload

    monkeypatch.setattr(base, "_get_json", fake_get)
    with pytest.raises(base.Step17BRenderActivationError):
        v2.verify_wnba_network_free()


def test_network_free_gate_rejects_monte_carlo_boundary_drift(monkeypatch) -> None:
    payload = _deployment_payload()
    payload["semantics"]["deployment_gate_does_not_run_monte_carlo"] = False

    def fake_get(path: str, **kwargs):
        return {"status": "ok"} if path == "/health" else payload

    monkeypatch.setattr(base, "_get_json", fake_get)
    with pytest.raises(base.Step17BRenderActivationError):
        v2.verify_wnba_network_free()


def test_network_free_gate_rejects_non_read_only_contract(monkeypatch) -> None:
    payload = _deployment_payload()
    payload["semantics"]["live_smoke_is_read_only"] = False

    def fake_get(path: str, **kwargs):
        return {"status": "ok"} if path == "/health" else payload

    monkeypatch.setattr(base, "_get_json", fake_get)
    with pytest.raises(base.Step17BRenderActivationError):
        v2.verify_wnba_network_free()


def test_v2_wraps_v1_activation_and_restores_original_smoke(monkeypatch) -> None:
    original = base._verify_wnba
    seen = {}

    def fake_activate(*, env=None):
        seen["patched"] = base._verify_wnba is v2.verify_wnba_network_free
        return {
            "model_version": "v1",
            "wnba": {},
            "safety": {},
        }

    monkeypatch.setattr(base, "activate", fake_activate)
    evidence = v2.activate(env={})
    assert seen["patched"] is True
    assert base._verify_wnba is original
    assert evidence["model_version"] == v2.MODEL_VERSION
    assert evidence["wnba"]["upstream_schedule_called"] is False
    assert evidence["safety"]["upstream_wnba_schedule_called"] is False
