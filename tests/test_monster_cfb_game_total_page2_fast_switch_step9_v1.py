from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"
APP = ROOT / "app.py"


def _overlay_source() -> str:
    assert OVERLAY.exists(), "Step-9 fast-switch overlay is not implemented yet"
    return OVERLAY.read_text(encoding="utf-8")


def _ast_function(source: str, name: str) -> ast.Module:
    module = ast.parse(source)
    node = next(item for item in module.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name)
    return ast.Module(body=[node], type_ignores=[])


def test_step9_selected_page2_uses_direct_fast_path_without_page1_installers() -> None:
    source = _overlay_source()
    assert 'PRIOR_RUNTIME = "streamlit_memory_lazy_router_nba_spread_step2_activation_v1"' in source
    assert 'CFB_ROUTE_OWNER = "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1"' in source
    assert "cfb_prior._render_page1_navigation_shell()" in source
    assert "importlib.import_module(cfb_prior.PAGE2_RUNTIME)" in source
    assert ".render_cfb_hub(" in source
    assert "install_games_on_day_step2_visual()" not in source
    assert "install_game_cards_step6_visual()" not in source
    assert "install_native_page1_shell_step3_visual()" not in source
    assert "st.cache" not in source
    assert "session_state" not in source


def test_step9_render_app_bypasses_prior_only_for_exact_selected_cfb_total() -> None:
    source = _overlay_source()
    calls: list[str] = []
    namespace: dict[str, Any] = {
        "Any": Any,
        "_selected_game_total": lambda: True,
        "_render_selected_page_fast": lambda: calls.append("fast") or "FAST",
        "prior": SimpleNamespace(render_app=lambda: calls.append("prior") or "PRIOR"),
    }
    exec(compile(_ast_function(source, "render_app"), "<step9-render-app>", "exec"), namespace)
    assert namespace["render_app"]() == "FAST"
    assert calls == ["fast"]

    calls.clear()
    namespace["_selected_game_total"] = lambda: False
    assert namespace["render_app"]() == "PRIOR"
    assert calls == ["prior"]


def test_step9_event_identity_is_re_read_each_render_so_matchup_switches_cannot_go_stale() -> None:
    source = _overlay_source()
    current = {"event": "401760001"}
    cfb_prior = SimpleNamespace(
        EVENT_QUERY_KEY="ks_cfb_game_total_event_id",
        _query_value=lambda key: current["event"] if key == "ks_cfb_game_total_event_id" else None,
    )
    namespace: dict[str, Any] = {"cfb_prior": cfb_prior}
    exec(compile(_ast_function(source, "_current_event_id"), "<step9-current-event>", "exec"), namespace)
    assert namespace["_current_event_id"]() == "401760001"
    current["event"] = "401760002"
    assert namespace["_current_event_id"]() == "401760002"


def test_step9_production_entrypoint_activates_only_new_overlay() -> None:
    _overlay_source()
    app = APP.read_text(encoding="utf-8")
    runtime = app[app.find("try:"):]
    assert (
        "from streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1 import "
        "record_bootstrap_import_ms, render_app"
    ) in runtime


def test_step9_is_routing_only_and_preserves_frozen_model_truth() -> None:
    source = _overlay_source()
    for marker in (
        "MAY_MODIFY_MODEL = False",
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_SELECTION = False",
        "NETWORK_CALLS_ADDED = 0",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ):
        assert marker in source
