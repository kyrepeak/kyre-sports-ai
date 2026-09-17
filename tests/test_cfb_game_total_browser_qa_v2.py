from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem" / "cfb_game_total_browser_qa_v3.py"
WORKFLOW = ROOT / ".github" / "workflows" / "cfb-game-total-v161-browser.yml"


def _source() -> str:
    assert CERT.exists(), "V161 tablet browser cert must exist"
    return CERT.read_text(encoding="utf-8")


def test_v161_browser_cert_targets_real_ipad_surface():
    source = _source()
    assert '"width": 1067' in source
    assert '"height": 1536' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"' in source
    assert 'DATE_QUERY_KEY = "ks_cfb_game_total_date"' in source


def test_v161_browser_cert_proves_day_navigation_and_reload_persistence():
    source = _source()
    assert '"GAME DAY"' in source
    assert "day_buttons" in source
    assert "page.reload(" in source
    assert "date_after_click" in source
    assert "date_after_reload" in source
    assert "date_after_reload != date_after_click" in source


def test_v161_browser_cert_accepts_valid_empty_slate_after_reload():
    from devsystem import cfb_game_total_browser_qa_v3 as cert

    body = (
        f"{cert.PRODUCTION_HEARTBEAT}\n"
        "📅 GAME DAY\n"
        "Select a day to load that CFB slate\n"
        "No verified FBS-scoped games were returned for this date. "
        "V159 fails closed—no Game Total forecast is invented."
    )
    assert cert._is_direct_v161_surface(body)
    cert._assert_visible_contract(body)


def test_v161_browser_cert_rejects_removed_masthead_and_old_shells():
    source = _source()
    assert '"MONSTER SPORTS INTELLIGENCE"' in source
    assert '"College Football Game Total — Final"' in source
    assert '"CFB OVER / UNDER • MONSTER DASHBOARD"' in source
    assert 'print("CFB_GAME_TOTAL_V161_BROWSER_GREEN")' in source


def test_v161_has_its_own_additive_browser_workflow():
    assert WORKFLOW.exists(), "V161 browser workflow must be additive, not overwrite frozen lanes"
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "CFB Game Total V161 browser certification" in source
    assert "devsystem/cfb_game_total_browser_qa_v3.py" in source
    assert "tests/test_cfb_game_total_browser_qa_v2.py" in source
    assert "python -m devsystem.cfb_game_total_browser_qa_v3" in source


def test_v156_persists_game_total_query_without_requiring_cached_v155_helper():
    source = (ROOT / "streamlit_memory_lazy_router_v156.py").read_text(encoding="utf-8")
    helper = source.split("def _persist_game_total_route_query() -> None:", 1)[1].split(
        "def _query_requests_game_total()", 1
    )[0]
    assert "prior._persist_game_total_route_query" not in helper
    assert "cfb_route_base.ROUTE_QUERY_SPORT" in helper
    assert "cfb_route_base.ROUTE_QUERY_MARKET" in helper
    assert "st.query_params" in helper


def test_v161_cache_bust_activates_new_router_v157_module():
    router = ROOT / "streamlit_memory_lazy_router_v157.py"
    assert router.exists(), "production cache bust requires a new Router V157 module name"
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v157 import record_bootstrap_import_ms, render_app" in app_source
    source = router.read_text(encoding="utf-8")
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"' in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v156"' in source
    assert "prior._persist_game_total_route_query" not in source
