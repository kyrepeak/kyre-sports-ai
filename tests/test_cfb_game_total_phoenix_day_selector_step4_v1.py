from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_step4_requires_additive_v41_phoenix_day_owner() -> None:
    page = _read("cfb_game_total_clean_page_v41.py")

    assert 'import cfb_game_total_clean_page_v40 as prior' in page
    assert 'import cfb_game_total_clean_page_v11 as legacy_day' in page
    assert 'PHOENIX_TZ = ZoneInfo("America/Phoenix")' in page
    assert 'DATE_QUERY_KEY = legacy_day.DATE_QUERY_KEY' in page
    assert 'datetime.now(PHOENIX_TZ).date()' in page
    assert 'start = selected - timedelta(days=2)' in page
    assert 'data-testid="gt241-phoenix-day-selector"' in page
    assert 'PHOENIX TIME' in page
    assert 'MST' in page
    assert 'st.query_params[DATE_QUERY_KEY] = selected.isoformat()' in page
    assert 'legacy_day._render_day_strip = _legacy_day_strip_passthrough' in page
    assert 'legacy_day._render_day_strip = original_day_strip' in page
    assert 'prior.PAGE1_SHELL_CSS' in page
    assert 'prior._page1_shell_html()' in page
    assert 'prior.prior.render_game_total_hub' in page


def test_step4_stays_presentation_only_and_defers_games_data_to_step5() -> None:
    page = _read("cfb_game_total_clean_page_v41.py")

    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in page
    assert 'MAY_MODIFY_MODEL = False' in page
    assert 'MAY_MODIFY_PROJECTION = False' in page
    assert 'MAY_MODIFY_PROBABILITY = False' in page
    assert 'MAY_MODIFY_MARKET_OWNERSHIP = False' in page
    assert 'MAY_MODIFY_OTHER_SPORTS = False' in page
    assert 'MAY_MODIFY_PAGE2 = False' in page
    assert 'NETWORK_CALLS_ADDED = 0' in page
    assert 'requests.' not in page
    assert '_load_games(' not in page
    assert 'SELECTOR_OWNS_GAME_LOADING = False' in page


def test_step4_router_advances_page1_only_and_preserves_page2() -> None:
    router = _read("streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py")

    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v41"' in router
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"' in router
    assert 'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0' in router
    assert 'MAY_MODIFY_PAGE2' not in router or 'MAY_MODIFY_PAGE2 = False' in router
