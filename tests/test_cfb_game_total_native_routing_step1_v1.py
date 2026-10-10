from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v36.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
LEGACY_NAV = ROOT / "cfb_game_total_clean_page_v33.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_step1_native_page_owner_exists_and_bypasses_legacy_jump_shell() -> None:
    assert PAGE.exists(), "Step 1 must add a dedicated native Page-1 owner"
    source = _read(PAGE)

    assert "import cfb_game_total_clean_page_v35 as prior" in source
    assert "import cfb_game_total_clean_page_v33 as legacy_nav" in source
    assert "import cfb_game_total_clean_page_v28 as frozen_content" in source
    assert "legacy_nav.render_game_total_hub = _native_content_hub" in source
    assert "legacy_nav.render_game_total_hub = original" in source
    assert "return callback(*args, **kwargs)" in source


def test_step1_native_page_preserves_current_page1_data_and_theme_chain() -> None:
    source = _read(PAGE)

    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v35"' in source
    assert "return _render_without_legacy_sport_jump(" in source
    assert "prior.render_game_total_hub" in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_step1_router_activates_native_owner_only_for_page1() -> None:
    source = _read(ROUTER)

    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v36"' in source
    assert "original_page1 = cfb_router.GAME_TOTAL_PAGE" in source
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE1_NATIVE_ROUTE" in source
    assert "cfb_router.GAME_TOTAL_PAGE = original_page1" in source
    assert "if not _selected_game_total():" in source
    assert "return _render_native_page1()" in source

    # Selected-event Page 2 must retain its frozen Step-8 owner.
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in source
    assert "live_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in source
    assert "render_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in source


def test_step1_does_not_edit_the_legacy_jump_owner_contract() -> None:
    legacy = _read(LEGACY_NAV)

    assert "Jump to a <em>Sport Page</em>" in legacy
    assert 'data-testid="gt233-sport-dropdown-nav"' in legacy
    assert 'SPORT_DROPDOWN_STEP3_MARKER = "CFB_GAME_TOTAL_SPORT_DROPDOWN_STEP3_FUNCTIONAL_ACTIVE"' in legacy
