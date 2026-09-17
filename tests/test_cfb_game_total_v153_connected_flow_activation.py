from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v153_router_targets_only_connected_game_total_page() -> None:
    router = ROOT / "streamlit_memory_lazy_router_v153.py"
    assert router.exists(), "V153 connected-flow router does not exist yet"
    source = router.read_text(encoding="utf-8")

    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v152"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v9"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V153_CONNECTED_FLOW_ACTIVE"' in source
    assert 'LEGACY_PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v153_delegates_frozen_navigation_but_imports_v9_directly_for_exact_game_total() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v153.py").read_text(encoding="utf-8")

    assert "import streamlit_memory_lazy_router_v152 as prior" in source
    assert "_FROZEN_GAME_TOTAL_RENDER = prior._render_cfb_game_total_v152" in source
    assert "if sport != CFB_SPORT_LABEL or market != GAME_TOTAL_MARKET:" in source
    assert "return _FROZEN_GAME_TOTAL_RENDER(market)" in source
    assert "prior._latch_game_total_route()" in source
    assert "prior._persist_game_total_route_query()" in source
    assert "page = prior.root._import(ACTIVE_PAGE)" in source
    assert "return page.render_cfb_hub(" in source
    assert "prior._render_cfb_game_total_v152 = _render_cfb_game_total_v153" in source
    assert "return prior.render_app()" in source
    assert "prior.ACTIVE_PAGE = ACTIVE_PAGE" not in source
    assert "analyze_game(" not in source


def test_v153_keeps_v152_production_heartbeat_compatibility() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v153.py").read_text(encoding="utf-8")

    assert "{PRODUCTION_HEARTBEAT}" in source
    assert "{LEGACY_PRODUCTION_HEARTBEAT}" in source


def test_v153_restores_v152_renderer_after_render() -> None:
    source = (ROOT / "streamlit_memory_lazy_router_v153.py").read_text(encoding="utf-8")

    assert "finally:" in source
    assert "prior._render_cfb_game_total_v152 = original_renderer" in source
