from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATEWAY = "https://kyre-sports-api.vercel.app"
APP = ROOT / "app.py"
LOADER = ROOT / "universal_runtime_v5_loader_cfb_game_total_bootstrap_repair_r1.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_bootstrap_repair_r1.py"
FROZEN_PAGE = ROOT / "cfb_game_total_page1_stier_v1.py"


def _page():
    return importlib.import_module("cfb_game_total_page1_api_bootstrap_repair_r1")


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


def test_successor_keeps_kyre_api_only_and_model_ownership_unchanged():
    page = _page()
    assert page.PAGE1_ENDPOINT == "/api/v1/cfb/game-total/page1"
    assert page.KYRE_SPORTS_API_BASE_URL == "KYRE_SPORTS_API_BASE_URL"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_MODEL is False
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_PROBABILITY is False
    assert page.MAY_MODIFY_RANKING is False
    assert page.MAY_MODIFY_SELECTION is False


def test_frozen_page_remains_original_fail_closed_ancestor():
    source = FROZEN_PAGE.read_text(encoding="utf-8")
    assert 'raise RuntimeError("Kyre Sports API gateway is not configured.")' in source
    assert DEFAULT_GATEWAY not in source


def test_loader_successor_changes_only_cfb_game_total_page1_owner():
    source = LOADER.read_text(encoding="utf-8")
    assert 'import universal_runtime_v5_loader_nba_pra_page1_v1 as upstream' in source
    assert 'route.sport_id == "cfb" and route.market_id == "game-total"' in source
    assert 'importlib.import_module("cfb_game_total_page1_api_bootstrap_repair_r1")' in source
    assert 'importlib.import_module("cfb_game_total_page2_market_completeness_r1")' in source
    assert "return upstream.resolve_destination(route)" in source


def test_terminal_preserves_server_authoritative_loading_runtime():
    source = TERMINAL.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_loading_progress_repair_r1 as prior" in source
    assert "render_page_experience_app_v5" in source
    assert "frozen_runtime.resolve_destination = resolve_destination" in source


def test_production_entrypoint_activates_cfb_game_total_successor():
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_game_total_bootstrap_repair_r1" in source
    assert '_STREAMLIT_DEPLOYMENT_HEARTBEAT = "api2-cfb-game-total-api-bootstrap-repair-r1-20261023"' in source
