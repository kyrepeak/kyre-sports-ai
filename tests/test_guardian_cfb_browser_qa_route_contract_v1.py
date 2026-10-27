from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROWSER_QA = ROOT / "devsystem" / "cfb_game_total_browser_qa_v1.py"
ACTIVATION_QA = ROOT / "devsystem" / "cfb_game_total_v152_activation_qa.py"


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
