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
    frozen_v149 = ROOT / "streamlit_memory_lazy_router_v149.py"
    app = ROOT / "app.py"
    required = (page, router, frozen_v149, app)
    missing = [path.name for path in required if not path.exists()]
    assert not missing, "missing active CFB V150 contract files: " + ", ".join(missing)

    py_compile.compile(str(page), doraise=True)
    py_compile.compile(str(router), doraise=True)
    py_compile.compile(str(app), doraise=True)

    page_source = page.read_text(encoding="utf-8")
    router_source = router.read_text(encoding="utf-8")
    v149_source = frozen_v149.read_text(encoding="utf-8")
    app_source = app.read_text(encoding="utf-8")

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
    assert "cfb_route_base._persist_fast_route_query()" not in router_source
    assert "cfb_route_base._clear_fast_route_query()" in router_source

    # V149 is a frozen release. V150 must be additive above it, not injected into it.
    assert 'GAME_TOTAL_MARKET = "Game Total"' not in v149_source
    assert "_game_total_v150_route_active" not in v149_source
    assert "streamlit_memory_lazy_router_v150" not in v149_source

    # The Streamlit entrypoint must activate V150 explicitly.
    assert (
        'FROZEN_V149_DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V149_CFB_OVER_UNDER_MONSTER_COMPACT_DASHBOARD_2026-09-16"'
        in app_source
    )
    assert (
        'DEPLOYMENT_HEARTBEAT = '
        '"STREAMLIT_MAIN_V150_CFB_GAME_TOTAL_MONSTER_COMPACT_DASHBOARD_2026-09-16"'
        in app_source
    )
    assert "from streamlit_memory_lazy_router_v150 import record_bootstrap_import_ms, render_app" in app_source
