from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v154.py"
PRIOR_ROUTER = ROOT / "streamlit_memory_lazy_router_v153.py"


def test_v154_routes_only_exact_cfb_over_under_to_v39() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert 'import streamlit_memory_lazy_router_v153 as prior' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v153"' in source
    assert 'OVER_UNDER_MARKET = "Over/Under"' in source
    assert 'ACTIVE_PAGE = "cfb_over_under_clean_page_v39"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_OVER_UNDER_V39_PRODUCTION_ACTIVE"' in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v153_remains_game_total_owner() -> None:
    source = PRIOR_ROUTER.read_text(encoding="utf-8")
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V153_CONNECTED_FLOW_ACTIVE"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v9"' in source


def test_production_entrypoint_boots_v154_router() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v154 import record_bootstrap_import_ms, render_app" in source
    assert "STREAMLIT_MAIN_V154_CFB_OVER_UNDER_COMPACT_EVIDENCE_2026-09-17" in source
