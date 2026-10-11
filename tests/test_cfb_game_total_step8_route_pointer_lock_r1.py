from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment
            return segment
    raise AssertionError(name)


def test_step8_serializes_shared_route_pointer_swaps() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    # Production evidence showed overlapping Streamlit sessions can observe the
    # shared Page-1/Page-2 module pointers while another render is swapping them.
    # The exact router must serialize every temporary pointer mutation.
    assert "from threading import RLock" in source
    assert "_ROUTE_POINTER_LOCK = RLock()" in source
    assert "with _ROUTE_POINTER_LOCK:" in source

    page1 = source.split("def _render_native_page1()", 1)[1].split("def _clear_auto_event_after_page1", 1)[0]
    page2 = source.split("def render_app()", 1)[1].split("__all__", 1)[0]

    assert "with _ROUTE_POINTER_LOCK:" in page1
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE1_NATIVE_ROUTE" in page1
    assert "cfb_router.GAME_TOTAL_PAGE = original_page1" in page1

    assert "with _ROUTE_POINTER_LOCK:" in page2
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in page2
    assert "live_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in page2
    assert "render_owner.ACTIVE_PAGE = PAGE2_RUNTIME" in page2
    assert "cfb_router.GAME_TOTAL_PAGE = original_cfb_page" in page2
    assert "live_owner.ACTIVE_PAGE = original_live_page" in page2
    assert "render_owner.ACTIVE_PAGE = original_render_page" in page2


def test_step8_real_tap_route_holds_lock_and_restores_shared_owners() -> None:
    source = ROUTER.read_text(encoding="utf-8")

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
    observed: dict[str, str] = {}

    def parent_render() -> str:
        observed.update({
            "cfb": str(cfb_router.GAME_TOTAL_PAGE),
            "live": str(live_owner.ACTIVE_PAGE),
            "render": str(render_owner.ACTIVE_PAGE),
        })
        return "PAGE2_RENDERED"

    def unexpected_page1(*args: Any, **kwargs: Any):
        del args, kwargs
        raise AssertionError("real card tap fell through to Page 1")

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
        "install_games_on_day_step2_visual": unexpected_page1,
        "install_games_on_day_step3_details": unexpected_page1,
        "install_games_on_day_step4_interaction_mobile": unexpected_page1,
        "_render_native_page1": unexpected_page1,
        "_clear_auto_event_after_page1": lambda: False,
    }
    for name in ("_query_value", "_selected_game_total", "render_app"):
        exec(_function_source(source, name), namespace)

    assert namespace["render_app"]() == "PAGE2_RENDERED"
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
