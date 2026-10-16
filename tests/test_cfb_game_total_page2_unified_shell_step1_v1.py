from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def _source() -> str:
    return ROUTER.read_text(encoding="utf-8")


def _function_or_empty(source: str, name: str, next_name: str | None = None) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    start = source.index(marker)
    if next_name is None:
        return source[start:]
    next_marker = f"def {next_name}("
    if next_marker not in source[start:]:
        return source[start:]
    end = source.index(next_marker, start)
    return source[start:end]


def test_step1_selected_event_reuses_exact_page1_navigation_shell() -> None:
    source = _source()
    helper = _function_or_empty(source, "_render_page1_navigation_shell")

    assert "import cfb_game_total_clean_page_v33 as page1_navigation" in source
    assert helper
    assert "page1_navigation.shell.SPORT_NAV_SHELL_CSS" in helper
    assert "page1_navigation.functional.SPORT_NAV_STEP2_CSS" in helper
    assert "page1_navigation.responsive.SPORT_NAV_STEP3_CSS" in helper
    assert "page1_navigation.dropdown.SPORT_DROPDOWN_STEP2_CSS" in helper
    assert "page1_navigation.SPORT_DROPDOWN_STEP3_CSS" in helper
    assert "page1_navigation._sport_dropdown_nav_html()" in helper


def test_step1_real_card_tap_mounts_shell_before_existing_page2_runtime() -> None:
    source = _source()
    render = _function_or_empty(source, "render_app")

    assert 'shell_renderer = globals().get("_render_page1_navigation_shell")' in render
    assert "if callable(shell_renderer):" in render
    assert "shell_renderer()" in render
    assert render.index("shell_renderer()") < render.index("with _ROUTE_POINTER_LOCK:")

    # Preserve the frozen exact-event Page-2 ownership/restoration contract.
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in render
    assert "live_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in render
    assert "render_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in render
    assert "return frozen_parent.render_app()" in render
    assert "cfb_router.GAME_TOTAL_PAGE = original_cfb_page" in render
    assert "live_owner.ACTIVE_PAGE = original_live_page" in render
    assert "render_owner.ACTIVE_PAGE = original_render_page" in render


def test_step1_keeps_page1_and_frozen_product_boundaries_unchanged() -> None:
    source = _source()
    page1 = _function_or_empty(source, "_render_page1_in_shared_shell", "_render_native_page1")

    assert "return root.render_app()" in page1
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_MARKET_OWNERSHIP = False" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
