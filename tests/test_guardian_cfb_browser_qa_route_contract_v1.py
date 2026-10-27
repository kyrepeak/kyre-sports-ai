from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROWSER_QA = ROOT / "devsystem" / "cfb_game_total_browser_qa_v1.py"
ACTIVATION_QA = ROOT / "devsystem" / "cfb_game_total_v152_activation_qa.py"
BROWSER_V4 = ROOT / "devsystem" / "cfb_game_total_browser_qa_v4.py"


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


def test_v163_browser_qa_seeds_terminal_universal_route_and_page_route_together() -> None:
    source = BROWSER_V4.read_text(encoding="utf-8")

    assert 'UNIVERSAL_ROUTE_SPORT = "sport"' in source
    assert 'UNIVERSAL_ROUTE_MARKET = "market"' in source
    assert 'UNIVERSAL_SPORT_ID = "cfb"' in source
    assert 'UNIVERSAL_MARKET_ID = "game-total"' in source
    assert "UNIVERSAL_ROUTE_SPORT: UNIVERSAL_SPORT_ID" in source
    assert "UNIVERSAL_ROUTE_MARKET: UNIVERSAL_MARKET_ID" in source
    assert "ROUTE_QUERY_SPORT: CFB_SPORT" in source
    assert "ROUTE_QUERY_MARKET: GAME_TOTAL_MARKET" in source
    assert "DATE_QUERY_KEY: CERT_DATE" in source
