from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V88 = ROOT / "nfl_passing_yards_hub_v88.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v239.py"


def _source(path: Path) -> str:
    assert path.exists(), f"missing required repair artifact: {path.name}"
    return path.read_text(encoding="utf-8")


def _load_v88():
    assert V88.exists(), "Passing Yards V88 fast picker has not been implemented yet"
    spec = importlib.util.spec_from_file_location("nfl_passing_yards_hub_v88_test", V88)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v88_is_presentation_only_and_keeps_v87_as_selected_qb_owner():
    src = _source(V88)
    assert 'FROZEN_SELECTED_OWNER = "nfl_passing_yards_hub_v87"' in src
    assert "PRESENTATION_ONLY = True" in src
    assert "FAST_PICKER_ONLY = True" in src
    for flag in (
        "MAY_MODIFY_PROJECTION",
        "MAY_MODIFY_CONTEXT_MATH",
        "MAY_MODIFY_PROBABILITY",
        "MAY_MODIFY_MARKET_MATH",
        "MAY_MODIFY_DATA_PROVIDER_BEHAVIOR",
        "MAY_MODIFY_WIDGET_KEYS",
    ):
        assert f"{flag} = False" in src
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in src
    assert "STAKE_SIZING_ENABLED = False" in src


def test_v88_module_import_is_lightweight_and_does_not_pull_the_deep_chain():
    tree = ast.parse(_source(V88))
    imported: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert "streamlit" not in imported
    assert "pandas" not in imported
    assert not any(name.startswith("nfl_passing_yards_hub_v") for name in imported)
    assert "nfl_passing_yards_identity_v1" not in imported


def test_picker_slot_parser_is_fail_closed_and_selected_qb_is_explicit():
    hub = _load_v88()
    assert hub._selected_qb_slot({}) is None
    assert hub._selected_qb_slot({"ks_qb_slot": ""}) is None
    assert hub._selected_qb_slot({"ks_qb_slot": "1"}) == 1
    assert hub._selected_qb_slot({"ks_qb_slot": ["2"]}) == 2
    assert hub._selected_qb_slot({"ks_qb_slot": "3"}) is None
    assert hub._selected_qb_slot({"ks_qb_slot": "garbage"}) is None


def test_compact_picker_card_hard_bounds_images_and_keeps_lazy_async_loading():
    hub = _load_v88()
    ctx = {
        "abbr": "HOU",
        "team": "Houston Texans",
        "team_id": "34",
        "identity_verified": True,
        "qb1": {"name": "C.J. Stroud", "athlete_id": "4432577", "injury_status": "No listed injury"},
    }
    html = hub._compact_qb_card_html(ctx, "@", "JAX", 1, "?ks_qb_slot=1")
    assert 'data-passing-yards-fast-card="1"' in html
    assert 'class="ks-py88-headshot"' in html
    assert 'width="112" height="112"' in html
    assert 'class="ks-py88-logo"' in html
    assert 'width="56" height="56"' in html
    assert html.count('loading="lazy"') >= 2
    assert html.count('decoding="async"') >= 2
    assert 'fetchpriority="low"' in html
    assert "C.J. Stroud" in html and "Houston Texans" in html


def test_render_flow_defers_v87_until_a_qb_slot_is_selected():
    src = _source(V88)
    assert "slot = _selected_qb_slot(st.query_params)" in src
    assert "if slot in (1, 2):" in src
    assert "return _render_selected_qb()" in src
    assert "return _render_fast_picker(st)" in src
    assert src.index("if slot in (1, 2):") < src.index("return _render_fast_picker(st)")


def test_v239_routes_only_passing_yards_to_v88_successor():
    src = _source(ROUTER)
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v88"' in src
    assert 'data-passing-yards-route-handoff="v225-guard-v188-v88"' in src
    assert "return prior.render_app()" in src
