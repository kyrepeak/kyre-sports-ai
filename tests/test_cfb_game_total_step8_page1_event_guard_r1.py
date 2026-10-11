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


def test_step8_page1_event_guard_removes_auto_event_without_tap_marker():
    source = ROUTER.read_text(encoding="utf-8")
    assert 'SELECTOR_SYNC_QUERY_KEY = "ks_cfb_game_total_selector_sync"' in source
    assert "_clear_auto_event_after_page1()" in source

    class Query(dict):
        pass

    st = SimpleNamespace(query_params=Query())
    live_owner = SimpleNamespace(
        _game_total_route_active=lambda: False,
        _restore_game_total_route_from_query=lambda: True,
        ACTIVE_PAGE="live",
    )
    cfb_router = SimpleNamespace(GAME_TOTAL_PAGE="page1")
    render_owner = SimpleNamespace(ACTIVE_PAGE="render")
    frozen_parent = SimpleNamespace(render_app=lambda: None)
    namespace: dict[str, Any] = {
        "Any": Any,
        "st": st,
        "live_owner": live_owner,
        "cfb_router": cfb_router,
        "render_owner": render_owner,
        "frozen_parent": frozen_parent,
        "EVENT_QUERY_KEY": "ks_cfb_game_total_event_id",
        "SELECTOR_SYNC_QUERY_KEY": "ks_cfb_game_total_selector_sync",
        "PAGE1_NATIVE_ROUTE": "cfb_game_total_clean_page_v43",
        "PAGE2_RUNTIME": "cfb_game_total_page2_step8_final_runtime_v1",
        "install_games_on_day_step2_visual": lambda: None,
        "install_games_on_day_step3_details": lambda: None,
        "install_games_on_day_step4_interaction_mobile": lambda: None,
    }
    for name in ("_query_value", "_selected_game_total", "_clear_auto_event_after_page1"):
        exec(_function_source(source, name), namespace)

    def page1_render():
        st.query_params["ks_cfb_game_total_event_id"] = "401858490"
        return "PAGE1"

    namespace["_render_native_page1"] = page1_render
    exec(_function_source(source, "render_app"), namespace)
    assert namespace["render_app"]() == "PAGE1"
    assert "ks_cfb_game_total_event_id" not in st.query_params


def test_step8_page1_event_guard_preserves_real_card_tap_marker():
    source = ROUTER.read_text(encoding="utf-8")
    st = SimpleNamespace(query_params={
        "ks_cfb_game_total_event_id": "401858490",
        "ks_cfb_game_total_selector_sync": "401858490",
    })
    namespace: dict[str, Any] = {
        "Any": Any,
        "st": st,
        "EVENT_QUERY_KEY": "ks_cfb_game_total_event_id",
        "SELECTOR_SYNC_QUERY_KEY": "ks_cfb_game_total_selector_sync",
    }
    exec(_function_source(source, "_query_value"), namespace)
    exec(_function_source(source, "_clear_auto_event_after_page1"), namespace)
    assert namespace["_clear_auto_event_after_page1"]() is False
    assert st.query_params["ks_cfb_game_total_event_id"] == "401858490"


def test_step8_page2_rejects_auto_event_without_matching_tap_marker():
    source = ROUTER.read_text(encoding="utf-8")
    st = SimpleNamespace(query_params={
        "ks_cfb_game_total_event_id": "401858490",
    })
    live_owner = SimpleNamespace(
        _game_total_route_active=lambda: True,
        _restore_game_total_route_from_query=lambda: True,
    )
    namespace: dict[str, Any] = {
        "Any": Any,
        "st": st,
        "live_owner": live_owner,
        "EVENT_QUERY_KEY": "ks_cfb_game_total_event_id",
        "SELECTOR_SYNC_QUERY_KEY": "ks_cfb_game_total_selector_sync",
    }
    exec(_function_source(source, "_query_value"), namespace)
    exec(_function_source(source, "_selected_game_total"), namespace)
    assert namespace["_selected_game_total"]() is False


def test_step8_page2_accepts_exact_event_only_with_matching_tap_marker():
    source = ROUTER.read_text(encoding="utf-8")
    st = SimpleNamespace(query_params={
        "ks_cfb_game_total_event_id": "401858490",
        "ks_cfb_game_total_selector_sync": "401858490",
    })
    live_owner = SimpleNamespace(
        _game_total_route_active=lambda: True,
        _restore_game_total_route_from_query=lambda: True,
    )
    namespace: dict[str, Any] = {
        "Any": Any,
        "st": st,
        "live_owner": live_owner,
        "EVENT_QUERY_KEY": "ks_cfb_game_total_event_id",
        "SELECTOR_SYNC_QUERY_KEY": "ks_cfb_game_total_selector_sync",
    }
    exec(_function_source(source, "_query_value"), namespace)
    exec(_function_source(source, "_selected_game_total"), namespace)
    assert namespace["_selected_game_total"]() is True


def test_step8_page2_rejects_mismatched_tap_marker():
    source = ROUTER.read_text(encoding="utf-8")
    st = SimpleNamespace(query_params={
        "ks_cfb_game_total_event_id": "401858490",
        "ks_cfb_game_total_selector_sync": "401858491",
    })
    live_owner = SimpleNamespace(
        _game_total_route_active=lambda: True,
        _restore_game_total_route_from_query=lambda: True,
    )
    namespace: dict[str, Any] = {
        "Any": Any,
        "st": st,
        "live_owner": live_owner,
        "EVENT_QUERY_KEY": "ks_cfb_game_total_event_id",
        "SELECTOR_SYNC_QUERY_KEY": "ks_cfb_game_total_selector_sync",
    }
    exec(_function_source(source, "_query_value"), namespace)
    exec(_function_source(source, "_selected_game_total"), namespace)
    assert namespace["_selected_game_total"]() is False
