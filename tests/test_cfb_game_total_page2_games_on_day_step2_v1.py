from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any


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


def _ast_function(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment
            return segment
    raise AssertionError(name)


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


def test_step2_selected_event_executes_parity_stack_then_shell_then_locked_page2() -> None:
    source = _source(ROUTER)

    class SpyLock:
        def __init__(self) -> None:
            self.entered = 0
            self.exited = 0

        def __enter__(self):
            self.entered += 1
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            self.exited += 1
            return False

    class LiveOwner:
        def __init__(self) -> None:
            self.ACTIVE_PAGE = "live-original"
            self.active = False

        def _game_total_route_active(self) -> bool:
            return self.active

        def _restore_game_total_route_from_query(self) -> bool:
            self.active = True
            return True

    event_id = "401858490"
    st = SimpleNamespace(query_params={
        "ks_cfb_game_total_event_id": event_id,
        "ks_cfb_game_total_selector_sync": event_id,
    })
    live_owner = LiveOwner()
    cfb_router = SimpleNamespace(GAME_TOTAL_PAGE="cfb-original")
    render_owner = SimpleNamespace(ACTIVE_PAGE="render-original")
    calls: list[str] = []
    observed: dict[str, str] = {}

    def installer(name: str):
        def _call() -> None:
            calls.append(name)
        return _call

    def shell() -> None:
        calls.append("shell")

    def parent_render() -> str:
        calls.append("page2")
        observed.update({
            "cfb": str(cfb_router.GAME_TOTAL_PAGE),
            "live": str(live_owner.ACTIVE_PAGE),
            "render": str(render_owner.ACTIVE_PAGE),
        })
        return "PAGE2_RENDERED"

    def unexpected_page1(*args: Any, **kwargs: Any):
        del args, kwargs
        raise AssertionError("real selected event fell through to Page 1")

    lock = SpyLock()
    namespace: dict[str, Any] = {
        "Any": Any,
        "st": st,
        "live_owner": live_owner,
        "cfb_router": cfb_router,
        "render_owner": render_owner,
        "frozen_parent": SimpleNamespace(render_app=parent_render),
        "EVENT_QUERY_KEY": "ks_cfb_game_total_event_id",
        "SELECTOR_SYNC_QUERY_KEY": "ks_cfb_game_total_selector_sync",
        "PAGE2_RUNTIME": "cfb_game_total_page2_step8_final_runtime_v1",
        "_ROUTE_POINTER_LOCK": lock,
        "install_games_on_day_step2_visual": installer("visual"),
        "install_games_on_day_step3_details": installer("details"),
        "install_games_on_day_step4_interaction_mobile": installer("mobile"),
        "_render_page1_navigation_shell": shell,
        "_render_native_page1": unexpected_page1,
        "_clear_auto_event_after_page1": lambda: False,
    }
    for name in ("_query_value", "_selected_game_total", "render_app"):
        exec(_ast_function(source, name), namespace)

    assert namespace["render_app"]() == "PAGE2_RENDERED"
    assert calls == ["visual", "details", "mobile", "shell", "page2"]
    assert observed == {
        "cfb": "cfb_game_total_page2_step8_final_runtime_v1",
        "live": "cfb_game_total_page2_step8_final_runtime_v1",
        "render": "cfb_game_total_page2_step8_final_runtime_v1",
    }
    assert lock.entered == 1
    assert lock.exited == 1
    assert cfb_router.GAME_TOTAL_PAGE == "cfb-original"
    assert live_owner.ACTIVE_PAGE == "live-original"
    assert render_owner.ACTIVE_PAGE == "render-original"


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
