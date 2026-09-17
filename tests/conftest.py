from __future__ import annotations

from pathlib import Path
import py_compile


ROOT = Path(__file__).resolve().parents[1]


def pytest_collection_modifyitems(session, config, items):
    """Keep the permanent CFB lane aware of frozen V150–V154 + active V155."""
    if not any(item.path.name.startswith("test_cfb_") for item in items):
        return

    page = ROOT / "cfb_game_total_clean_page_v1.py"
    router = ROOT / "streamlit_memory_lazy_router_v150.py"
    activation = ROOT / "streamlit_memory_lazy_router_v149.py"
    frozen_router = ROOT / "streamlit_memory_lazy_router_v152.py"
    active_router = ROOT / "streamlit_memory_lazy_router_v153.py"
    successor_router = ROOT / "streamlit_memory_lazy_router_v154.py"
    game_total_router = ROOT / "streamlit_memory_lazy_router_v155.py"
    app_entry = ROOT / "app.py"
    browser = ROOT / "devsystem" / "cfb_game_total_browser_qa_v1.py"
    required = (
        page,
        router,
        activation,
        frozen_router,
        active_router,
        successor_router,
        game_total_router,
        app_entry,
        browser,
    )
    missing = [path.name for path in required if not path.exists()]
    assert not missing, "missing active CFB V155 contract files: " + ", ".join(missing)

    for path in required:
        py_compile.compile(str(path), doraise=True)

    page_source = page.read_text(encoding="utf-8")
    router_source = router.read_text(encoding="utf-8")
    activation_source = activation.read_text(encoding="utf-8")
    frozen_router_source = frozen_router.read_text(encoding="utf-8")
    active_router_source = active_router.read_text(encoding="utf-8")
    successor_router_source = successor_router.read_text(encoding="utf-8")
    game_total_router_source = game_total_router.read_text(encoding="utf-8")
    app_source = app_entry.read_text(encoding="utf-8")
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

    # Frozen V149 activation still preserves certified O/U V38 and the V151
    # Game Total handoff used underneath the frozen V152 production router.
    assert 'ACTIVE_PAGE = "cfb_over_under_clean_page_v38"' in activation_source
    assert 'OVER_UNDER_MARKET = "Over/Under"' in activation_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in activation_source
    assert "def _restore_game_total_v150_from_query" in activation_source
    assert "streamlit_memory_lazy_router_v151" in activation_source
    assert "_render_direct_cfb_game_total" in activation_source
    assert "cfb_route_base._persist_fast_route_query()" in activation_source

    # The frozen V148 Moneyline page uses V77's selector. V149 must wrap that
    # selector only while delegating so a Moneyline -> Game Total click survives
    # the rerun and restores the exact V150 route instead of falling to Moneyline.
    assert "def _persist_game_total_v150_query" in activation_source
    assert "def _selectbox_v150_handoff" in activation_source
    assert "_FROZEN_CFB_SELECTBOX" in activation_source
    assert "cfb_route_base._selectbox_v77 = _selectbox_v150_handoff" in activation_source
    assert "cfb_route_base._selectbox_v77 = original_cfb_selectbox" in activation_source
    assert "st.query_params[cfb_route_base.ROUTE_QUERY_MARKET] = GAME_TOTAL_MARKET" in activation_source

    # V152 stays frozen beneath the additive V153 Game Total successor.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v151"' in frozen_router_source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"' in frozen_router_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in frozen_router_source
    assert "MAY_MODIFY_PROJECTION = False" in frozen_router_source
    assert "return prior.render_app()" in frozen_router_source

    # V153 remains the frozen Game Total owner beneath additive V154.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v152"' in active_router_source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V153_CONNECTED_FLOW_ACTIVE"' in active_router_source
    assert 'LEGACY_PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"' in active_router_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in active_router_source
    assert "MAY_MODIFY_PROJECTION = False" in active_router_source
    assert "return prior.render_app()" in active_router_source

    # V154 remains frozen and advances only exact CFB Over/Under over V153.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v153"' in successor_router_source
    assert 'PRODUCTION_HEARTBEAT = "CFB_OVER_UNDER_V39_PRODUCTION_ACTIVE"' in successor_router_source
    assert 'ACTIVE_PAGE = "cfb_over_under_clean_page_v39"' in successor_router_source
    assert 'OVER_UNDER_MARKET = "Over/Under"' in successor_router_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in successor_router_source
    assert "MAY_MODIFY_PROJECTION = False" in successor_router_source
    assert "return prior.render_app()" in successor_router_source

    # V155 advances only exact CFB Game Total to V160 while preserving V154.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v154"' in game_total_router_source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE"' in game_total_router_source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v10"' in game_total_router_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in game_total_router_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in game_total_router_source
    assert "MAY_MODIFY_PROJECTION = False" in game_total_router_source
    assert "return page.render_cfb_hub(" in game_total_router_source
    assert "return prior.render_app()" in game_total_router_source

    # Production entrypoint must activate V155/V160 exactly.
    assert "from streamlit_memory_lazy_router_v155 import record_bootstrap_import_ms, render_app" in app_source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V155_CFB_GAME_TOTAL_V160_VISUAL_PARITY_2026-09-17"' in app_source

    # Real browser proof must certify the actual V160 visual-parity surface and
    # explicitly reject the legacy title visible in the old production page.
    assert 'GAME_TOTAL_MARKET = "Game Total"' in browser_source
    assert '"CFB GAME TOTAL • CLEAN PAGE V160 ACTIVE"' in browser_source
    assert '"GAME TOTAL ANALYSIS"' in browser_source
    assert '"TEAM EVIDENCE"' in browser_source
    assert '"GAME TOTAL EVIDENCE • STEPS 1–12"' in browser_source
    assert '"FINAL MODEL SUMMARY"' in browser_source
    assert '"TOP-5 SLATE SCANNER"' in browser_source
    assert '"College Football Game Total — Final"' in browser_source
    assert 'print("CFB_GAME_TOTAL_V160_BROWSER_GREEN")' in browser_source
    assert "FORBIDDEN_VISIBLE" in browser_source
