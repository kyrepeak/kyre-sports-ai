from pathlib import Path


BROWSER = Path("devsystem/cfb_game_total_browser_qa_v1.py")
PRODUCTION = Path("devsystem/production_verify_v3.py")


def test_refresh_uses_direct_game_total_frame_contract() -> None:
    source = BROWSER.read_text(encoding="utf-8")
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE"' in source
    assert "def _find_direct_game_total_frame" in source
    assert "frame_after_reload, reload_scans = _find_direct_game_total_frame(page)" in source


def test_production_freshness_uses_router_v155_heartbeat() -> None:
    source = PRODUCTION.read_text(encoding="utf-8")
    assert 'GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE"' in source
    assert 'GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB GAME TOTAL • CLEAN PAGE V160 ACTIVE"' not in source
