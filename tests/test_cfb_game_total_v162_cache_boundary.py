from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v13.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v158.py"
APP = ROOT / "app.py"


def _read(path: Path) -> str:
    assert path.exists(), f"missing required V162 file: {path.name}"
    return path.read_text(encoding="utf-8")


def test_v162_uses_fresh_page_successor_without_touching_frozen_v161():
    source = _read(PAGE)
    assert "cfb_game_total_clean_page_v12" in source
    assert "CFB GAME TOTAL • CLEAN PAGE V162 ACTIVE" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_v162_router_unconditionally_evicts_cached_game_total_page_modules():
    source = _read(ROUTER)
    assert 'GAME_TOTAL_PAGE_PREFIX = "cfb_game_total_clean_page_"' in source
    assert "sys.modules.pop(name, None)" in source
    assert "importlib.invalidate_caches()" in source
    assert "_purge_game_total_page_modules()" in source
    assert source.index("_purge_game_total_page_modules()") < source.index("root._import(ACTIVE_PAGE)")


def test_v162_router_uses_new_page_and_new_production_heartbeat():
    source = _read(ROUTER)
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v13"' in source
    assert 'PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V162_PRODUCTION_ACTIVE"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_app_activates_router_v158():
    source = APP.read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_v158" in source
