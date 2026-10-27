from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_QA = ROOT / "devsystem" / "browser_qa_v1.py"
BROWSER_QA = ROOT / "devsystem" / "cfb_game_total_browser_qa_v1.py"
ACTIVATION_QA = ROOT / "devsystem" / "cfb_game_total_v152_activation_qa.py"
BROWSER_V4 = ROOT / "devsystem" / "cfb_game_total_browser_qa_v4.py"
STEP6_V184 = ROOT / "devsystem" / "cfb_game_total_step6_browser_qa_v184.py"


def test_game_total_browser_qa_uses_canonical_query_route_not_stale_root_selectors() -> None:
    source = BROWSER_QA.read_text(encoding="utf-8")

    assert "base._cfb_game_total_url(base_url)" in source
    assert "_find_direct_game_total_frame(page)" in source
    assert "base._read_sport_options(page, frame)" not in source
    assert "base._choose(page, frame, 0, CFB_SPORT)" not in source
    assert "base._choose(page, frame, 1, GAME_TOTAL_MARKET)" not in source


def test_v152_activation_qa_uses_canonical_query_route_and_heartbeat_frame() -> None:
    source = ACTIVATION_QA.read_text(encoding="utf-8")

    assert "base._cfb_game_total_url(base_url)" in source
    assert "def _find_game_total_heartbeat_frame(" in source
    assert "_find_game_total_heartbeat_frame(page)" in source
    assert "base._read_sport_options(page, frame)" not in source
    assert "base._choose(page, frame, 0, CFB_SPORT)" not in source
    assert "base._choose(page, frame, 1, GAME_TOTAL_MARKET)" not in source


def test_shared_game_total_url_helper_uses_only_terminal_canonical_keys() -> None:
    source = BASE_QA.read_text(encoding="utf-8")
    helper = source.split("def _cfb_game_total_url", 1)[1].split("def _wait_for_game_total_step5", 1)[0]

    assert '("sport", "cfb")' in helper
    assert '("market", "game-total")' in helper
    assert '("date", CFB_GAME_TOTAL_DATE)' in helper
    assert '("game_id", CFB_GAME_TOTAL_EVENT_ID)' in helper
    assert "ks_sport" not in helper
    assert "ks_cfb_market" not in helper
    assert "ks_cfb_game_total_date" not in helper
    assert "ks_cfb_game_total_event_id" not in helper


def test_v163_browser_qa_seeds_terminal_canonical_route_and_page_params_only() -> None:
    source = BROWSER_V4.read_text(encoding="utf-8")

    assert 'UNIVERSAL_ROUTE_SPORT = "sport"' in source
    assert 'UNIVERSAL_ROUTE_MARKET = "market"' in source
    assert 'CFB_SPORT = "cfb"' in source
    assert 'GAME_TOTAL_MARKET = "game-total"' in source
    assert 'UNIVERSAL_SPORT_ID = CFB_SPORT' in source
    assert 'UNIVERSAL_MARKET_ID = GAME_TOTAL_MARKET' in source
    assert 'ROUTE_QUERY_SPORT = UNIVERSAL_ROUTE_SPORT' in source
    assert 'ROUTE_QUERY_MARKET = UNIVERSAL_ROUTE_MARKET' in source
    assert 'DATE_QUERY_KEY = "date"' in source
    assert 'EVENT_QUERY_KEY = "game_id"' in source
    assert "UNIVERSAL_ROUTE_SPORT: UNIVERSAL_SPORT_ID" in source
    assert "UNIVERSAL_ROUTE_MARKET: UNIVERSAL_MARKET_ID" in source
    assert "DATE_QUERY_KEY: CERT_DATE" in source
    seeded = source.split("direct_query = urlencode", 1)[1].split("with sync_playwright", 1)[0]
    assert "ROUTE_QUERY_SPORT: CFB_SPORT" not in seeded
    assert "ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET" not in seeded


def test_v184_browser_qa_reuses_v163_terminal_canonical_route() -> None:
    source = STEP6_V184.read_text(encoding="utf-8")

    assert "selector_qa.UNIVERSAL_ROUTE_SPORT: selector_qa.UNIVERSAL_SPORT_ID" in source
    assert "selector_qa.UNIVERSAL_ROUTE_MARKET: selector_qa.UNIVERSAL_MARKET_ID" in source
    assert "DATE_QUERY_KEY: CERT_DATE" in source
    assert "ROUTE_QUERY_SPORT: CFB_SPORT" not in source
    assert "ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET" not in source
