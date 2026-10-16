from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
PAGE2_RUNTIME = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.index(marker)
    next_def = source.find("\ndef ", start + len(marker))
    return source[start:] if next_def < 0 else source[start:next_def]


def test_step2_selected_event_installs_page1_games_on_day_stack_before_page2() -> None:
    source = _source(ROUTER)
    render = _function(source, "render_app")
    selected_marker = 'shell_renderer = globals().get("_render_page1_navigation_shell")'
    page1_return = "        return rendered"
    selected = render[render.index(page1_return) + len(page1_return):]

    calls = (
        "install_games_on_day_step2_visual()",
        "install_games_on_day_step3_details()",
        "install_games_on_day_step4_interaction_mobile()",
    )
    for call in calls:
        assert call in selected
        assert selected.index(call) < selected.index(selected_marker)

    assert selected.index(selected_marker) < selected.index("with _ROUTE_POINTER_LOCK:")


def test_step2_keeps_page1_stack_and_exact_page2_pointer_contract() -> None:
    source = _source(ROUTER)
    render = _function(source, "render_app")
    page1_return = "        return rendered"
    split = render.index(page1_return) + len(page1_return)
    page1 = render[:split]
    selected = render[split:]

    for call in (
        "install_games_on_day_step2_visual()",
        "install_games_on_day_step3_details()",
        "install_games_on_day_step4_interaction_mobile()",
    ):
        assert call in page1

    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in selected
    assert "live_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in selected
    assert "render_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in selected
    assert "return frozen_parent.render_app()" in selected
    assert "cfb_router.GAME_TOTAL_PAGE = original_cfb_page" in selected
    assert "live_owner.ACTIVE_PAGE = original_live_page" in selected
    assert "render_owner.ACTIVE_PAGE = original_render_page" in selected


def test_step2_preserves_frozen_product_and_page2_runtime_boundaries() -> None:
    source = _source(ROUTER)
    page2 = _source(PAGE2_RUNTIME)

    for invariant in (
        "MAY_MODIFY_MODEL = False",
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_MARKET_OWNERSHIP = False",
        "MAY_MODIFY_OTHER_SPORTS = False",
        "NETWORK_CALLS_ADDED = 0",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ):
        assert invariant in source

    assert "MAY_MODIFY_PAGE1 = False" in page2
    assert "MAY_MODIFY_MODEL = False" in page2
    assert "MAY_MODIFY_PROJECTION = False" in page2
    assert "MAY_MODIFY_PROBABILITY = False" in page2
    assert "NETWORK_CALLS_ADDED = 0" in page2
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page2
