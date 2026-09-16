from __future__ import annotations

from pathlib import Path
import py_compile


ROOT = Path(__file__).resolve().parents[1]


def pytest_collection_modifyitems(session, config, items):
    """Keep the permanent CFB lane aware of the active V150 Game Total route."""
    if not any(item.path.name.startswith("test_cfb_") for item in items):
        return

    page = ROOT / "cfb_game_total_clean_page_v1.py"
    router = ROOT / "streamlit_memory_lazy_router_v150.py"
    activation = ROOT / "streamlit_memory_lazy_router_v149.py"
    required = (page, router, activation)
    missing = [path.name for path in required if not path.exists()]
    assert not missing, "missing active CFB V150 contract files: " + ", ".join(missing)

    py_compile.compile(str(page), doraise=True)
    py_compile.compile(str(router), doraise=True)

    page_source = page.read_text(encoding="utf-8")
    router_source = router.read_text(encoding="utf-8")
    activation_source = activation.read_text(encoding="utf-8")

    assert 'FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"' in page_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page_source
    assert "frozen_page.slate.analyze_game" in page_source
    assert "frozen_page.slate.scan_slate" in page_source
    assert "frozen_page.final_model.rank_slate" in page_source
    assert 'ZoneInfo("America/Phoenix")' in page_source
    assert "logo_v3.resolve_visuals" in page_source
    assert "⚡ QUICK READ" in page_source
    assert 'with st.expander("Deep evidence • certified team audit"' in page_source

    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v149"' in router_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in router_source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v1"' in router_source
    assert "return prior.render_app()" in router_source
    assert "finally:" in router_source

    # app.py still boots V149; V149 must hand off only exact CFB Game Total.
    assert "_game_total_v150_route_active" in activation_source
    assert "streamlit_memory_lazy_router_v150" in activation_source
    assert "_render_direct_cfb_game_total" in activation_source
