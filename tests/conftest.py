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
    browser = ROOT / "devsystem" / "cfb_game_total_browser_qa_v1.py"
    required = (page, router, activation, browser)
    missing = [path.name for path in required if not path.exists()]
    assert not missing, "missing active CFB V150 contract files: " + ", ".join(missing)

    for path in required:
        py_compile.compile(str(path), doraise=True)

    page_source = page.read_text(encoding="utf-8")
    router_source = router.read_text(encoding="utf-8")
    activation_source = activation.read_text(encoding="utf-8")
    browser_source = browser.read_text(encoding="utf-8")

    # Presentation-only Game Total page over the frozen Step-12 hub.
    assert 'FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"' in page_source
    assert 'MARKET = "Game Total"' in page_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page_source
    assert "MAY_MODIFY_PROJECTION = False" in page_source
    assert "frozen_page.slate.analyze_game" in page_source
    assert "frozen_page.slate.scan_slate" in page_source
    assert "frozen_page.final_model.rank_slate" in page_source
    assert 'ZoneInfo("America/Phoenix")' in page_source
    assert "logo_v3.resolve_visuals" in page_source
    assert "⚡ QUICK READ" in page_source
    assert 'with st.expander("Deep evidence • certified team audit"' in page_source
    assert "frozen_page.render_game_total_hub(" not in page_source

    # V150 targets only exact CFB -> Game Total and delegates everything else.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v149"' in router_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in router_source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v1"' in router_source
    assert "return prior.render_app()" in router_source
    assert "finally:" in router_source
    assert "root.st.selectbox = original_selectbox" in router_source
    assert "root._render_nfl = original_render_nfl" in router_source

    # Critical anti-drift rule: V77's persistence helper is O/U-only. V150 must
    # persist and restore Game Total using its own exact query contract.
    assert "cfb_route_base._persist_fast_route_query()" not in router_source
    assert "def _persist_game_total_route_query" in router_source
    assert "def _restore_game_total_route_from_query" in router_source
    assert "st.query_params[cfb_route_base.ROUTE_QUERY_MARKET] = GAME_TOTAL_MARKET" in router_source

    # app.py still boots V149. The additive activation shim must preserve V149's
    # certified O/U V38 path while handing only exact Game Total to V150.
    assert 'ACTIVE_PAGE = "cfb_over_under_clean_page_v38"' in activation_source
    assert 'OVER_UNDER_MARKET = "Over/Under"' in activation_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in activation_source
    assert "def _restore_game_total_v150_from_query" in activation_source
    assert "streamlit_memory_lazy_router_v150" in activation_source
    assert "_render_direct_cfb_game_total" in activation_source
    assert "cfb_route_base._persist_fast_route_query()" in activation_source

    # Real browser proof must certify the actual Game Total page and explicitly
    # reject the legacy title visible in the user's production screenshot.
    assert 'GAME_TOTAL_MARKET = "Game Total"' in browser_source
    assert '"CFB GAME TOTAL • MONSTER DASHBOARD"' in browser_source
    assert '"College Football Game Total — Final"' in browser_source
    assert "FORBIDDEN_VISIBLE" in browser_source
