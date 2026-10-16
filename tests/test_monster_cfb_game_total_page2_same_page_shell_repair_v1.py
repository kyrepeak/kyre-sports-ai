from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP9 = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"
SAME_PAGE = ROOT / "cfb_game_total_page2_same_page_shell_repair_v1.py"
PAGE1 = ROOT / "cfb_game_total_clean_page_v45.py"
PAGE2 = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_slice(source: str, name: str, next_name: str) -> str:
    start = source.index(f"def {name}(")
    end = source.index(f"\ndef {next_name}(", start)
    return source[start:end]


def test_same_page_runtime_exists_before_green() -> None:
    assert SAME_PAGE.is_file(), "same-page Page-2 bridge is not implemented yet"


def test_selected_event_fast_path_does_not_render_legacy_jump_shell() -> None:
    source = _read(STEP9)
    body = _function_slice(source, "_render_selected_page_fast", "render_app")
    assert "_render_page1_navigation_shell()" not in body
    assert 'SAME_PAGE_RUNTIME = "cfb_game_total_page2_same_page_shell_repair_v1"' in source
    assert "importlib.import_module(SAME_PAGE_RUNTIME)" in body


def test_same_page_runtime_uses_current_v45_page1_as_the_render_base() -> None:
    source = _read(SAME_PAGE)
    assert "import cfb_game_total_clean_page_v45 as page1" in source
    assert "import cfb_game_total_page2_step8_final_runtime_v1 as page2" in source
    assert "page2._render_selected_page(" in source
    assert "page1.render_game_total_hub" in source
    assert "Jump to a Sport Page" not in source
    assert "page1_navigation" not in source
    assert "cfb_game_total_clean_page_v38 as" not in source


def test_same_page_runtime_preserves_product_and_data_invariants() -> None:
    source = _read(SAME_PAGE)
    for marker in (
        "MAY_MODIFY_MODEL = False",
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_SELECTION = False",
        "MAY_MODIFY_OTHER_SPORTS = False",
        "NETWORK_CALLS_ADDED = 0",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ):
        assert marker in source


def test_existing_page1_and_page2_owners_remain_unchanged_inputs() -> None:
    assert "UNIFIED_REPAIR_MARKER" in _read(PAGE1)
    assert "STEP8_MARKER" in _read(PAGE2)
