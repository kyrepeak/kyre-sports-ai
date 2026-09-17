from __future__ import annotations

from pathlib import Path
import py_compile


ROOT = Path(__file__).resolve().parents[1]


def pytest_collection_modifyitems(session, config, items):
    """Keep the permanent CFB lane aware of frozen V150–V160 + active V161."""
    if not any(item.path.name.startswith("test_cfb_") for item in items):
        return

    page = ROOT / "cfb_game_total_clean_page_v1.py"
    visual_page = ROOT / "cfb_game_total_clean_page_v10.py"
    v161_page = ROOT / "cfb_game_total_clean_page_v12.py"
    router = ROOT / "streamlit_memory_lazy_router_v150.py"
    activation = ROOT / "streamlit_memory_lazy_router_v149.py"
    frozen_router = ROOT / "streamlit_memory_lazy_router_v152.py"
    active_router = ROOT / "streamlit_memory_lazy_router_v153.py"
    successor_router = ROOT / "streamlit_memory_lazy_router_v154.py"
    game_total_router = ROOT / "streamlit_memory_lazy_router_v155.py"
    v161_router = ROOT / "streamlit_memory_lazy_router_v156.py"
    app_entry = ROOT / "app.py"
    browser = ROOT / "devsystem" / "cfb_game_total_browser_qa_v1.py"
    required = (
        page,
        visual_page,
        v161_page,
        router,
        activation,
        frozen_router,
        active_router,
        successor_router,
        game_total_router,
        v161_router,
        app_entry,
        browser,
    )
    missing = [path.name for path in required if not path.exists()]
    assert not missing, "missing active CFB V161 contract files: " + ", ".join(missing)

    for path in required:
        py_compile.compile(str(path), doraise=True)

    page_source = page.read_text(encoding="utf-8")
    visual_page_source = visual_page.read_text(encoding="utf-8")
    v161_page_source = v161_page.read_text(encoding="utf-8")
    router_source = router.read_text(encoding="utf-8")
    activation_source = activation.read_text(encoding="utf-8")
    frozen_router_source = frozen_router.read_text(encoding="utf-8")
    active_router_source = active_router.read_text(encoding="utf-8")
    successor_router_source = successor_router.read_text(encoding="utf-8")
    game_total_router_source = game_total_router.read_text(encoding="utf-8")
    v161_router_source = v161_router.read_text(encoding="utf-8")
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

    # V160 stays frozen as the visual foundation beneath V161.
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v9"' in visual_page_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in visual_page_source
    assert "MAY_MODIFY_PROJECTION = False" in visual_page_source
    assert "MONSTER SPORTS INTELLIGENCE" in visual_page_source
    assert 'data-testid="cfb-game-total-monster-masthead"' in visual_page_source
    assert ".gt159-gamefacts{grid-template-columns:repeat(4,minmax(0,1fr))" in visual_page_source
    assert ".gt159-totalgrid{grid-template-columns:repeat(4,minmax(0,1fr))" in visual_page_source
    assert ".gt159-badges{grid-template-columns:repeat(3,minmax(0,1fr))" in visual_page_source
    assert ".gt159-teamgrid{grid-template-columns:repeat(2,minmax(0,1fr))" in visual_page_source
    assert ".gt159-stepgrid{grid-template-columns:repeat(2,minmax(0,1fr))" in visual_page_source
    assert ".gt159-finalgrid{grid-template-columns:repeat(5,minmax(0,1fr))" in visual_page_source
    assert ".gt159-notes{grid-template-columns:repeat(2,minmax(0,1fr))" in visual_page_source
    assert ".gt159-teamgrid{grid-template-columns:1fr}" not in visual_page_source
    assert ".gt159-badges{grid-template-columns:1fr}" not in visual_page_source
    assert ".gt159-notes{grid-template-columns:1fr}" not in visual_page_source
    assert ".gt159-stepgrid{grid-template-columns:1fr}" not in visual_page_source
    assert ".gt159-finalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}" not in visual_page_source
    assert "prior.st.date_input = st.sidebar.date_input" in visual_page_source
    assert "prior.st.selectbox = st.sidebar.selectbox" in visual_page_source
    assert "prior.st.expander = st.sidebar.expander" in visual_page_source
    assert "gt160-evidence-logo" in visual_page_source

    # V161 V12 is additive over V11 and changes only official ESPN identity extraction.
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v11"' in v161_page_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in v161_page_source
    assert "MAY_MODIFY_PROJECTION = False" in v161_page_source
    assert '"espn_event_id"' in v161_page_source
    assert 'f"{side}_espn_team_id"' in v161_page_source
    assert "prior._game_id = _game_id" in v161_page_source
    assert "prior._team_id = _team_id" in v161_page_source
    assert "prior._game_id = original_game_id" in v161_page_source
    assert "prior._team_id = original_team_id" in v161_page_source

    # V150 targets only exact CFB -> Game Total and delegates everything else.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v149"' in router_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in router_source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v1"' in router_source
    assert "return prior.render_app()" in router_source
    assert "finally:" in router_source
    assert "root.st.selectbox = original_selectbox" in router_source
    assert "root._render_nfl = original_render_nfl" in router_source

    # Critical anti-drift rule: V77 persistence is O/U-only.
    assert "cfb_route_base._persist_fast_route_query()" not in router_source
    assert "def _persist_game_total_route_query" in router_source
    assert "def _restore_game_total_route_from_query" in router_source
    assert "st.query_params[cfb_route_base.ROUTE_QUERY_MARKET] = GAME_TOTAL_MARKET" in router_source

    # Frozen V149 activation still preserves certified O/U V38 and V151 Game Total handoff.
    assert 'ACTIVE_PAGE = "cfb_over_under_clean_page_v38"' in activation_source
    assert 'OVER_UNDER_MARKET = "Over/Under"' in activation_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in activation_source
    assert "def _restore_game_total_v150_from_query" in activation_source
    assert "streamlit_memory_lazy_router_v151" in activation_source
    assert "_render_direct_cfb_game_total" in activation_source
    assert "cfb_route_base._persist_fast_route_query()" in activation_source
    assert "def _persist_game_total_v150_query" in activation_source
    assert "def _selectbox_v150_handoff" in activation_source
    assert "_FROZEN_CFB_SELECTBOX" in activation_source
    assert "cfb_route_base._selectbox_v77 = _selectbox_v150_handoff" in activation_source
    assert "cfb_route_base._selectbox_v77 = original_cfb_selectbox" in activation_source
    assert "st.query_params[cfb_route_base.ROUTE_QUERY_MARKET] = GAME_TOTAL_MARKET" in activation_source

    # V152 stays frozen beneath additive V153.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v151"' in frozen_router_source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"' in frozen_router_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in frozen_router_source
    assert "MAY_MODIFY_PROJECTION = False" in frozen_router_source
    assert "return prior.render_app()" in frozen_router_source

    # V153 remains frozen beneath additive V154.
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

    # V155 remains frozen as the V160 Game Total owner beneath V156.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v154"' in game_total_router_source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE"' in game_total_router_source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v10"' in game_total_router_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in game_total_router_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in game_total_router_source
    assert "MAY_MODIFY_PROJECTION = False" in game_total_router_source
    assert "cfb_route_base._persist_fast_route_query()" not in game_total_router_source
    assert "def _persist_game_total_route_query" in game_total_router_source
    assert "st.query_params[cfb_route_base.ROUTE_QUERY_MARKET] = GAME_TOTAL_MARKET" in game_total_router_source
    assert "def _render_exact_game_total_surface" in game_total_router_source
    assert 'page_title="Monster Sports Intelligence • CFB Game Total"' in game_total_router_source
    assert "return page.render_cfb_hub(" in game_total_router_source
    assert "return prior.render_app()" in game_total_router_source

    # V156 advances only exact CFB Game Total to V161/V12 while preserving V155.
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v155"' in v161_router_source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"' in v161_router_source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v12"' in v161_router_source
    assert 'GAME_TOTAL_MARKET = "Game Total"' in v161_router_source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in v161_router_source
    assert "MAY_MODIFY_PROJECTION = False" in v161_router_source
    assert "def _render_exact_game_total_surface" in v161_router_source
    assert 'page_title="Kyre Sports AI • CFB Game Total"' in v161_router_source
    assert "return page.render_cfb_hub(" in v161_router_source
    assert "return prior.render_app()" in v161_router_source

    # Production entrypoint must activate V156/V161 exactly.
    assert "from streamlit_memory_lazy_router_v156 import record_bootstrap_import_ms, render_app" in app_source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V156_CFB_GAME_TOTAL_V161_GAME_DAY_NAV_2026-09-17"' in app_source

    # Frozen V160 browser proof remains part of the inherited tablet regression contract.
    assert 'GAME_TOTAL_MARKET = "Game Total"' in browser_source
    assert 'ROUTE_QUERY_MARKET = "ks_cfb_market"' in browser_source
    assert 'FULL_RENDER_MARKER = "VIEW TOP 5 →"' in browser_source
    assert '"GAME TOTAL ANALYSIS"' in browser_source
    assert '"TEAM EVIDENCE"' in browser_source
    assert '"GAME TOTAL EVIDENCE • STEPS 1–12"' in browser_source
    assert '"FINAL MODEL SUMMARY"' in browser_source
    assert '"TOP-5 SLATE SCANNER"' in browser_source
    assert '"College Football Game Total — Final"' in browser_source
    assert '"CFB OVER / UNDER • MONSTER DASHBOARD"' in browser_source
    assert '"KYRE SPORTS AI"' in browser_source
    assert 'page.reload(' in browser_source
    assert '"width": 1067' in browser_source
    assert '"height": 1536' in browser_source
    assert 'print("CFB_GAME_TOTAL_V160_BROWSER_GREEN")' in browser_source
    assert "FORBIDDEN_VISIBLE" in browser_source
