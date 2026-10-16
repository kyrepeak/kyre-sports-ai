from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V45 = ROOT / "cfb_game_total_clean_page_v45.py"
BRIDGE = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1.py"
APP = ROOT / "app.py"
V36 = ROOT / "cfb_game_total_clean_page_v36.py"
V41 = ROOT / "cfb_game_total_clean_page_v41.py"
V14 = ROOT / "cfb_game_total_clean_page_v14.py"
STEP9 = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_ast(source: str, name: str) -> ast.Module:
    module = ast.parse(source)
    node = next(
        item
        for item in module.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.Module(body=[node], type_ignores=[])


def test_page1_unified_repair_owner_exists_before_green() -> None:
    assert V45.is_file(), "Unified Page-1 repair owner V45 is not implemented yet"
    assert BRIDGE.is_file(), "Unified Page-1 repair bridge is not implemented yet"


def test_v45_preserves_v41_day_owner_while_reusing_v36_kickoff_and_hero() -> None:
    source = _read(V45)
    assert "v36._render_with_step3_presentation = _render_v36_without_day_override" in source
    assert "v36.selector_owner._kickoff_text = v36._kickoff_text_v36" in source
    assert "v36.hero_owner._matchup_header_html_v25 = v36._matchup_header_html_v36" in source
    assert "v36._future_day_strip_v36" not in source
    assert "PHOENIX TIME • TOMORROW +" not in source

    day_sentinel = object()
    kickoff_original = object()
    hero_original = object()
    kickoff_repair = object()
    hero_repair = object()

    class _Lock:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    fake_v36 = SimpleNamespace(
        _LOCK=_Lock(),
        day_owner=SimpleNamespace(_render_day_strip=day_sentinel),
        selector_owner=SimpleNamespace(_kickoff_text=kickoff_original),
        hero_owner=SimpleNamespace(_matchup_header_html_v25=hero_original),
        _kickoff_text_v36=kickoff_repair,
        _matchup_header_html_v36=hero_repair,
    )
    namespace: dict[str, Any] = {"Any": Any, "v36": fake_v36}
    exec(
        compile(
            _function_ast(source, "_render_v36_without_day_override"),
            "<page1-v45-day-owner>",
            "exec",
        ),
        namespace,
    )

    observed: dict[str, Any] = {}

    def callback():
        observed["day"] = fake_v36.day_owner._render_day_strip
        observed["kickoff"] = fake_v36.selector_owner._kickoff_text
        observed["hero"] = fake_v36.hero_owner._matchup_header_html_v25
        return "rendered"

    assert namespace["_render_v36_without_day_override"](callback) == "rendered"
    assert observed["day"] is day_sentinel
    assert observed["kickoff"] is kickoff_repair
    assert observed["hero"] is hero_repair
    assert fake_v36.day_owner._render_day_strip is day_sentinel
    assert fake_v36.selector_owner._kickoff_text is kickoff_original
    assert fake_v36.hero_owner._matchup_header_html_v25 is hero_original


def test_v41_remains_the_only_visible_phoenix_day_owner_and_includes_today() -> None:
    source = _read(V41)
    assert 'ZoneInfo("America/Phoenix")' in source
    assert "return datetime.now(PHOENIX_TZ).date()" in source
    assert "if candidate == today:" in source
    assert 'label = f"TODAY\\n{candidate.strftime(' in source
    assert "legacy_day._render_day_strip = _legacy_day_strip_passthrough" in source
    assert "_render_phoenix_day_selector()" in source


def test_selected_day_loader_accepts_today_without_future_only_filtering() -> None:
    source = _read(V14)
    assert "schedule.load_with_diagnostics(selected_day)" in source
    load_start = source.index("def _load_games(selected_day")
    load_end = source.index("\ndef _sync_frozen_matchup_state", load_start)
    load_body = source[load_start:load_end]
    assert "timedelta(days=1)" not in load_body
    assert "selected_day >" not in load_body
    assert "selected_day >=" not in load_body


def test_page1_bridge_changes_only_native_page1_owner() -> None:
    source = _read(BRIDGE)
    assert 'PAGE1_REPAIR_ROUTE = "cfb_game_total_clean_page_v45"' in source
    assert "cfb_prior.PAGE1_NATIVE_ROUTE = PAGE1_REPAIR_ROUTE" in source
    assert "def render_with_page1_repair(" in source
    assert "PAGE2_RUNTIME =" not in source
    assert "cfb_prior.PAGE2_RUNTIME =" not in source
    assert "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1" not in source
    for marker in (
        "MAY_MODIFY_MODEL = False",
        "MAY_MODIFY_PROJECTION = False",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_OTHER_SPORTS = False",
        "NETWORK_CALLS_ADDED = 0",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
    ):
        assert marker in source


def test_step9_selected_page2_fast_path_stays_first_and_only_page1_fallback_is_wrapped() -> None:
    source = _read(STEP9)
    assert "import streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1 as page1_repair" in source
    render_start = source.index("def render_app()")
    render_end = source.index("\n\n__all__", render_start)
    render_body = source[render_start:render_end]
    assert "if _selected_game_total():" in render_body
    assert "return _render_selected_page_fast()" in render_body
    assert "return page1_repair.render_with_page1_repair(prior.render_app)" in render_body
    assert render_body.index("return _render_selected_page_fast()") < render_body.index("render_with_page1_repair")


def test_app_remains_on_frozen_step9_entrypoint() -> None:
    app = _read(APP)
    runtime = app[app.find("try:"):]
    assert (
        "from streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1 import "
        "record_bootstrap_import_ms, render_app"
    ) in runtime
