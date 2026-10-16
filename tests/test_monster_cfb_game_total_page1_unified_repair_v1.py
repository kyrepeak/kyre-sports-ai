from __future__ import annotations

import ast
from datetime import date
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
V44 = ROOT / "cfb_game_total_clean_page_v44.py"
STEP8 = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
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


def _nested_function(source: str, outer_name: str, inner_name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    outer = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == outer_name
    )
    return next(
        node
        for node in ast.walk(outer)
        if isinstance(node, ast.FunctionDef) and node is not outer and node.name == inner_name
    )


def test_page1_unified_repair_owner_exists_before_green() -> None:
    assert V45.is_file(), "Unified Page-1 repair owner V45 is not implemented yet"
    assert BRIDGE.is_file(), "Unified Page-1 repair bridge is not implemented yet"


def test_v45_preserves_v41_day_owner_and_forwards_full_v36_call_signature() -> None:
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

    def callback(*args: Any, **kwargs: Any):
        observed["day"] = fake_v36.day_owner._render_day_strip
        observed["kickoff"] = fake_v36.selector_owner._kickoff_text
        observed["hero"] = fake_v36.hero_owner._matchup_header_html_v25
        observed["args"] = args
        observed["kwargs"] = kwargs
        return "rendered"

    positional = ("section", "status", "logo", "heading")
    assert namespace["_render_v36_without_day_override"](
        callback,
        *positional,
        proof_token="signature-preserved",
    ) == "rendered"
    assert observed["day"] is day_sentinel
    assert observed["kickoff"] is kickoff_repair
    assert observed["hero"] is hero_repair
    assert observed["args"] == positional
    assert observed["kwargs"] == {"proof_token": "signature-preserved"}
    assert fake_v36.day_owner._render_day_strip is day_sentinel
    assert fake_v36.selector_owner._kickoff_text is kickoff_original
    assert fake_v36.hero_owner._matchup_header_html_v25 is hero_original


def test_v45_render_path_keeps_one_selector_and_preserves_v44_stale_date_fail_soft() -> None:
    v45_source = _read(V45)
    v44_source = _read(V44)
    router8 = _read(STEP8)

    loader_node = _nested_function(
        v44_source,
        "_render_snapshot_without_stale_date_runtimeerror",
        "snapshot_loader",
    )
    selected_day = date(2026, 10, 16)
    stale_downstream_day = date(2026, 10, 17)
    snapshot = ({"event_id": "today-game", "away_team": "Away", "home_team": "Home"},)
    loader_module = ast.Module(body=[loader_node], type_ignores=[])
    ast.fix_missing_locations(loader_module)
    loader_ns: dict[str, Any] = {"selected_day": selected_day, "snapshot": snapshot}
    exec(compile(loader_module, str(V44), "exec"), loader_ns)
    snapshot_loader = loader_ns["snapshot_loader"]

    counters = {"phoenix_selector": 0, "legacy_strip": 0}

    class _Lock:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def legacy_strip(*_args: Any, **_kwargs: Any):
        counters["legacy_strip"] += 1
        return selected_day

    original_wrapper = object()
    fake_v36 = SimpleNamespace(
        _LOCK=_Lock(),
        _render_with_step3_presentation=original_wrapper,
        day_owner=SimpleNamespace(_render_day_strip=legacy_strip),
        selector_owner=SimpleNamespace(_kickoff_text=object()),
        hero_owner=SimpleNamespace(_matchup_header_html_v25=object()),
        _kickoff_text_v36=object(),
        _matchup_header_html_v36=object(),
    )

    namespace: dict[str, Any] = {
        "Any": Any,
        "v36": fake_v36,
        "_OWNER_LOCK": _Lock(),
    }
    exec(
        compile(
            _function_ast(v45_source, "_render_v36_without_day_override"),
            "<page1-v45-wrapper>",
            "exec",
        ),
        namespace,
    )

    def prior_render(*args: Any, **kwargs: Any):
        counters["phoenix_selector"] += 1
        return fake_v36._render_with_step3_presentation(
            lambda *_a, **_k: snapshot_loader(stale_downstream_day),
            *args,
            **kwargs,
        )

    namespace["prior"] = SimpleNamespace(render_game_total_hub=prior_render)
    exec(
        compile(
            _function_ast(v45_source, "render_game_total_hub"),
            "<page1-v45-render>",
            "exec",
        ),
        namespace,
    )

    result = namespace["render_game_total_hub"]("section", "status", "logo", "heading")
    assert result == list(snapshot)
    assert counters == {"phoenix_selector": 1, "legacy_strip": 0}
    assert fake_v36._render_with_step3_presentation is original_wrapper
    assert "requested_day = selected_day" in v44_source
    assert "raise RuntimeError" not in ast.get_source_segment(v44_source, loader_node)
    assert "import cfb_game_total_clean_page_v44 as runtime_repair" in router8
    assert (
        "snapshot_owner.render_game_total_hub = "
        "runtime_repair._render_snapshot_without_stale_date_runtimeerror"
    ) in router8


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


def test_step9_selected_page2_fast_path_stays_first_and_page1_bridge_is_fail_safe() -> None:
    source = _read(STEP9)
    assert "import streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1 as page1_repair" in source
    render_start = source.index("def render_app()")
    render_end = source.index("\n\n__all__", render_start)
    render_body = source[render_start:render_end]
    assert "if _selected_game_total():" in render_body
    assert "return _render_selected_page_fast()" in render_body
    assert 'bridge = globals().get("page1_repair")' in render_body
    assert "if bridge is None:" in render_body
    assert "return prior.render_app()" in render_body
    assert "return bridge.render_with_page1_repair(prior.render_app)" in render_body
    assert render_body.index("return _render_selected_page_fast()") < render_body.index("render_with_page1_repair")


def test_executable_activation_chain_is_app_to_step9_to_page1_bridge() -> None:
    app_tree = ast.parse(_read(APP))
    app_imports = [
        node
        for node in ast.walk(app_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1"
    ]
    assert any(
        {alias.name for alias in node.names} >= {"record_bootstrap_import_ms", "render_app"}
        for node in app_imports
    )

    step9_tree = ast.parse(_read(STEP9))
    bridge_imports = [
        node
        for node in ast.walk(step9_tree)
        if isinstance(node, ast.Import)
    ]
    assert any(
        any(
            alias.name == "streamlit_memory_lazy_router_cfb_game_total_page1_unified_repair_v1"
            and alias.asname == "page1_repair"
            for alias in node.names
        )
        for node in bridge_imports
    )
