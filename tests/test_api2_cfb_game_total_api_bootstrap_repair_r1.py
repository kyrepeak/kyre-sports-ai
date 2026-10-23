from __future__ import annotations

import importlib


DEFAULT_GATEWAY = "https://kyre-sports-api.vercel.app"


def _page():
    return importlib.import_module("cfb_game_total_page1_stier_v1")


def test_game_total_resolves_canonical_kyre_gateway_without_streamlit_config(monkeypatch):
    page = _page()
    monkeypatch.delenv("KYRE_SPORTS_API_BASE_URL", raising=False)
    monkeypatch.setattr(page.st, "secrets", {}, raising=False)

    assert page._api_base() == DEFAULT_GATEWAY


def test_game_total_explicit_gateway_override_still_wins(monkeypatch):
    page = _page()
    monkeypatch.setenv("KYRE_SPORTS_API_BASE_URL", "https://example-kyre-gateway.invalid/")
    monkeypatch.setattr(page.st, "secrets", {}, raising=False)

    assert page._api_base() == "https://example-kyre-gateway.invalid"


def test_game_total_remains_kyre_api_only_application_handoff():
    page = _page()
    assert page.PAGE1_ENDPOINT == "/api/v1/cfb/game-total/page1"
    assert page.KYRE_SPORTS_API_BASE_URL == "KYRE_SPORTS_API_BASE_URL"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_MODEL is False
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_PROBABILITY is False
