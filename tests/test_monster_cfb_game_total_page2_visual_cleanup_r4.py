from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R4 = ROOT / "cfb_game_total_page2_visual_cleanup_r4.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"
R4_MODULE = "cfb_game_total_page2_visual_cleanup_r4"


def _load_r4():
    assert R4.is_file(), "R4 purge-safe successor must exist before activation"
    importlib.invalidate_caches()
    return importlib.import_module(R4_MODULE)


def test_r4_exists_and_active_router_points_to_purge_safe_successor() -> None:
    assert R4.is_file(), "R4 purge-safe successor must exist before activation"
    router = ROUTER.read_text(encoding="utf-8")
    assert f'CFB_PAGE2_RUNTIME = "{R4_MODULE}"' in router


def test_r4_stage7_builder_is_non_recursive_and_removes_legacy_header() -> None:
    page = _load_r4()
    identity = {
        "away_team": "Mississippi St.",
        "home_team": "LSU",
        "away_record": "4-1",
        "home_record": "4-2",
    }
    away = {
        "team": "Mississippi St.",
        "record": "4-1",
        "ppg": 39.0,
        "allowed_pg": 28.0,
        "recent_form": "WWWWL",
    }
    home = {
        "team": "LSU",
        "record": "4-2",
        "ppg": 42.0,
        "allowed_pg": 18.5,
        "recent_form": "WLWWL",
    }
    html = page.build_stage7_clean_html(identity, away, home)
    assert 'data-testid="gtp2r4-team-evidence"' in html
    assert 'class="gt204-sectionhead"' not in html
    assert "width:46px" in html
    assert "height:46px" in html


def test_r4_shared_shell_routes_to_r4_itself_and_restores_pointer(monkeypatch) -> None:
    page = _load_r4()
    original = page.cfb_router.PAGE1_NATIVE_ROUTE
    seen: dict[str, str] = {}

    def fake_shared_shell():
        seen["route"] = page.cfb_router.PAGE1_NATIVE_ROUTE
        imported = importlib.import_module(seen["route"])
        return imported.__name__

    monkeypatch.setattr(page.cfb_router, "_render_page1_in_shared_shell", fake_shared_shell)
    try:
        assert page.render_selected_in_shared_shell() == R4_MODULE
        assert seen["route"] == R4_MODULE
    finally:
        assert page.cfb_router.PAGE1_NATIVE_ROUTE == original


def test_r4_preserves_frozen_model_and_scope_contract() -> None:
    page = _load_r4()
    assert page.MAY_MODIFY_PAGE1 is False
    assert page.MAY_MODIFY_MODEL is False
    assert page.MAY_MODIFY_PROJECTION is False
    assert page.MAY_MODIFY_PROBABILITY is False
    assert page.MAY_MODIFY_RANKING is False
    assert page.MAY_MODIFY_SELECTION is False
    assert page.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert page.MAY_MODIFY_OTHER_SPORTS is False
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.NETWORK_CALLS_ADDED == 0
