from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v153.py"


def test_v153_routes_only_exact_cfb_over_under_to_v39() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v152"' in source
    assert 'OVER_UNDER_MARKET = "Over/Under"' in source
    assert 'ACTIVE_PAGE = "cfb_over_under_clean_page_v39"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_OVER_UNDER_V39_PRODUCTION_ACTIVE"' in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_production_entrypoint_boots_v153_router() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v153 import record_bootstrap_import_ms, render_app" in source
    assert "CFB_OVER_UNDER_V39" in source
